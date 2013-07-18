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
bridge configuration plugin.
"""


import gettext


import ethtool


from otopi import util
from otopi import plugin


from ovirt_hosted_engine_setup import constants as ohostedcons


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    bridge configuration plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._enabled = True

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.NetworkEnv.BRIDGE_IF,
            None
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.BRIDGE_NAME,
            ohostedcons.Defaults.DEFAULT_BRIDGE_NAME
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        if (
            self.environment[ohostedcons.NetworkEnv.BRIDGE_NAME] in
            ethtool.get_devices()
        ):
            self.logger.info(
                _(
                    'Bridge {bridge} already created'
                ).format(
                    bridge=self.environment[ohostedcons.NetworkEnv.BRIDGE_NAME]
                )
            )
            self._enabled = False
        else:
            self.command.detect('vdsClient')

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        condition=lambda self: (
            self._enabled and
            not self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]
        ),
    )
    def _customization(self):
        nics = ethtool.get_devices()
        validValues = []
        for nic in nics:
            flags = ethtool.get_flags(nic)
            if flags & ethtool.IFF_LOOPBACK:
                self.logger.debug('Detected loopback device %s' % nic)
            else:
                validValues.append(nic)
        if not validValues:
            raise RuntimeError('A Network interface is required')
        interactive = self.environment[
            ohostedcons.NetworkEnv.BRIDGE_IF
        ] is None
        if interactive:
            default = ohostedcons.Defaults.DEFAULT_BRIDGE_IF
            if not default in validValues:
                default = validValues[0]
            self.environment[
                ohostedcons.NetworkEnv.BRIDGE_IF
            ] = self.dialog.queryString(
                name='ovehosted_bridge_if',
                note=_(
                    'Please indicate a nic to set '
                    '{bridge} bridge on: (@VALUES@) [@DEFAULT@]: '
                ).format(
                    bridge=self.environment[
                        ohostedcons.NetworkEnv.BRIDGE_NAME
                    ]
                ),
                prompt=True,
                caseSensitive=True,
                default=default,
                validValues=validValues,
            )

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        name=ohostedcons.Stages.BRIDGE_AVAILABLE,
        condition=lambda self: (
            self._enabled and
            not self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]
        ),
    )
    def _misc(self):
        self.logger.info(_('Configuring the management bridge'))
        nic = self.environment[ohostedcons.NetworkEnv.BRIDGE_IF]
        bridge = self.environment[ohostedcons.NetworkEnv.BRIDGE_NAME]

        self.execute(
            (
                self.command.get('vdsClient'),
                '-s',
                'localhost',
                'addNetwork',
                'bridge=%s' % bridge,
                'vlan=',
                'bond=',
                'nics=%s' % nic,
                'force=False',
                'bridged=True',
                'BOOTPROTO=dhcp',
                'ONBOOT=yes',
                'blockingdhcp=true',
            ),
            raiseOnError=True
        )

        for state in (False, True):
            self.services.state(
                name='network',
                state=state,
            )

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        condition=lambda self: not self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
    )
    def _closeup(self):
        self.services.startup('network', True)


# vim: expandtab tabstop=4 shiftwidth=4
