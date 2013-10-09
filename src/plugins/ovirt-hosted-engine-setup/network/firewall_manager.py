#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2013 Red Hat, Inc.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#


"""
Firewall manager selection plugin.
"""


import os
import gettext


import libxml2


from otopi import util
from otopi import plugin
from otopi import constants as otopicons
from otopi import filetransaction


from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import util as ohostedutil


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    Firewall manager selection plugin.
    """

    def _parseFirewalld(self, format):
        ret = ''
        for content in [
            content
            for key, content in self.environment.items()
            if key.startswith(
                otopicons.NetEnv.FIREWALLD_SERVICE_PREFIX
            )
        ]:
            doc = None
            ctx = None
            try:
                doc = libxml2.parseDoc(content)
                ctx = doc.xpathNewContext()
                nodes = ctx.xpathEval("/service/port")
                for node in nodes:
                    ret += format.format(
                        protocol=node.prop('protocol'),
                        port=node.prop('port'),
                    )
            finally:
                if doc is not None:
                    doc.freeDoc()
                if ctx is not None:
                    ctx.xpathFreeContext()

        return ret

    def _createIptablesConfig(self):
        return ohostedutil.processTemplate(
            ohostedcons.FileLocations.HOSTED_ENGINE_IPTABLES_TEMPLATE,
            subst={
                '@CUSTOM_RULES@': self._parseFirewalld(
                    format=(
                        '-A INPUT -p {protocol} -m state --state NEW '
                        '-m {protocol} --dport {port} -j ACCEPT\n'
                    )
                )
            }
        )

    def _createHumanConfig(self):
        return '\n'.join(
            sorted(
                self._parseFirewalld(
                    format='{protocol}:{port}\n',
                ).splitlines()
            )
        ) + '\n'

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.NetworkEnv.FIREWALL_MANAGER,
            None
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.FIREWALLD_SERVICES,
            []
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.FIREWALLD_SUBST,
            {}
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.NET_FIREWALL_MANAGER_AVAILABLE,
        condition=lambda self: not self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_NETWORK,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_NETWORK,
        ),
    )
    def _customization(self):
        # TODO: remove the following line when FirewallD will be supported
        # by ovirt-engine. Actually the engine is not able to configure
        # FirewallD while it's adding an host
        # It has to be done here and not at init stage because it's assigned
        # at customization stage by otopi.
        self.environment[otopicons.NetEnv.FIREWALLD_AVAILABLE] = False

        if self.environment[ohostedcons.NetworkEnv.FIREWALL_MANAGER] is None:
            managers = []
            if self.environment[otopicons.NetEnv.FIREWALLD_AVAILABLE]:
                managers.append('firewalld')
            if self.services.exists('iptables'):
                managers.append('iptables')

            for manager in managers:
                response = self.dialog.queryString(
                    name='OHOSTED_NETWORK_FIREWALL_MANAGER',
                    note=_(
                        '{manager} was detected on your computer, '
                        'do you wish setup to configure it? '
                        '(@VALUES@)[@DEFAULT@]: '
                    ).format(
                        manager=manager,
                    ),
                    prompt=True,
                    validValues=(_('Yes'), _('No')),
                    caseSensitive=False,
                    default=_('Yes'),
                )
                if response == _('Yes').lower():
                    self.environment[
                        ohostedcons.NetworkEnv.FIREWALL_MANAGER
                    ] = manager
                    break

        self.environment[otopicons.NetEnv.IPTABLES_ENABLE] = (
            self.environment[
                ohostedcons.NetworkEnv.FIREWALL_MANAGER
            ] == 'iptables'
        )
        self.environment[otopicons.NetEnv.FIREWALLD_ENABLE] = (
            self.environment[
                ohostedcons.NetworkEnv.FIREWALL_MANAGER
            ] == 'firewalld'
        )

    @plugin.event(
        # must be at customization as otopi modules
        # need a chance to validate content
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.NET_FIREWALL_MANAGER_PROCESS_TEMPLATES,
        priority=plugin.Stages.PRIORITY_LOW,
        after=(
            ohostedcons.Stages.NET_FIREWALL_MANAGER_AVAILABLE,
        ),
        condition=lambda self: not self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
        # must be always enabled to create examples on first host
    )
    def _process_templates(self):
        for service in self.environment[
            ohostedcons.NetworkEnv.FIREWALLD_SERVICES
        ]:
            content = ohostedutil.processTemplate(
                template=os.path.join(
                    ohostedcons.FileLocations.
                    HOSTED_ENGINE_FIREWALLD_TEMPLATES_DIR,
                    service['directory'],
                    '%s.xml.in' % service['name'],
                ),
                subst=self.environment[ohostedcons.NetworkEnv.FIREWALLD_SUBST],
            )

            self.environment[
                otopicons.NetEnv.FIREWALLD_SERVICE_PREFIX +
                service['name']
            ] = content

            target = os.path.join(
                ohostedcons.FileLocations.HOSTED_ENGINE_FIREWALLD_EXAMPLE_DIR,
                '%s.xml' % service['name']
            )

            self.environment[otopicons.CoreEnv.MAIN_TRANSACTION].append(
                filetransaction.FileTransaction(
                    name=target,
                    content=content,
                    modifiedList=self.environment[
                        otopicons.CoreEnv.MODIFIED_FILES
                    ],
                )
            )

        self.environment[
            otopicons.NetEnv.IPTABLES_RULES
        ] = self._createIptablesConfig()

        self.environment[otopicons.CoreEnv.MAIN_TRANSACTION].append(
            filetransaction.FileTransaction(
                name=ohostedcons.FileLocations.HOSTED_ENGINE_IPTABLES_EXAMPLE,
                content=self.environment[otopicons.NetEnv.IPTABLES_RULES],
                modifiedList=self.environment[
                    otopicons.CoreEnv.MODIFIED_FILES
                ],
            )
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        condition=lambda self: (
            self.environment[ohostedcons.NetworkEnv.FIREWALL_MANAGER] is None
            and
            not self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]
        ),

    )
    def _closeup(self):
        self.dialog.note(
            text=_(
                'The following network ports should be opened:\n'
                '{ports}'
            ).format(
                ports='\n'.join([
                    '    ' + l
                    for l in self._createHumanConfig().splitlines()
                ]),
            ),
        )

        self.dialog.note(
            text=_(
                'An example of the required configuration for iptables '
                'can be found at:\n'
                '    {example}'
            ).format(
                example=(
                    ohostedcons.FileLocations.HOSTED_ENGINE_IPTABLES_EXAMPLE
                )
            )
        )

        commands = []
        for service in [
            key[len(otopicons.NetEnv.FIREWALLD_SERVICE_PREFIX):]
            for key in self.environment
            if key.startswith(
                otopicons.NetEnv.FIREWALLD_SERVICE_PREFIX
            )
        ]:
            commands.append('firewall-cmd -service %s' % service)
        self.dialog.note(
            text=_(
                'In order to configure firewalld, copy the '
                'files from\n'
                '{examples} to {configdir}\n'
                'and execute the following commands:\n'
                '{commands}'
            ).format(
                examples=(
                    ohostedcons.FileLocations.
                    HOSTED_ENGINE_FIREWALLD_EXAMPLE_DIR
                ),
                configdir='/etc/firewalld/services',
                commands='\n'.join([
                    '    ' + l
                    for l in commands
                ]),
            )
        )


# vim: expandtab tabstop=4 shiftwidth=4
