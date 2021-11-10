#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2013-2017 Red Hat, Inc.
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


import ethtool
import gettext
import socket

from otopi import plugin
from otopi import util

from ovirt_setup_lib import hostname as osetuphostname

from ovirt_hosted_engine_setup import ansible_utils
from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    bridge configuration plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

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
        self.environment.setdefault(
            ohostedcons.NetworkEnv.REFUSE_DEPLOYING_WITH_NM,
            False
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.FQDN_REVERSE_VALIDATION,
            False
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.ALLOW_INVALID_BOND_MODES,
            False
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.HOST_NAME,
            None
        )
        self.environment.setdefault(
            ohostedcons.EngineEnv.APP_HOST_NAME,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        self._hostname_helper = osetuphostname.Hostname(plugin=self)

    @plugin.event(
        stage=plugin.Stages.STAGE_PROGRAMS,
        condition=lambda self: self.environment[
            ohostedcons.NetworkEnv.REFUSE_DEPLOYING_WITH_NM
        ]
    )
    def _check_NM(self):
        nmstatus = self.services.status('NetworkManager')
        self.logger.debug('NetworkManager: {status}'.format(
            status=nmstatus,
        ))
        if nmstatus:
            raise RuntimeError(_(
                'hosted-engine cannot be deployed while NetworkManager is '
                'running, please stop and disable it before proceeding'
            ))

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.BRIDGE_DETECTED,
        after=(
            ohostedcons.Stages.REQUIRE_ANSWER_FILE,
            ohostedcons.Stages.DIALOG_TITLES_S_NETWORK,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_NETWORK,
        ),
    )
    def _detect_bridges(self):
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

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_NETWORK,
            ohostedcons.Stages.BRIDGE_DETECTED,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_NETWORK,
        ),
    )
    def _customization(self):
        self.logger.info(_('Checking available network interfaces:'))
        validValues = []
        ah = ansible_utils.AnsibleHelper(
            tags=ohostedcons.Const.HE_TAG_NETWORK_INTERFACES,
            extra_vars={'he_just_collect_network_interfaces': True},
            user_extra_vars=self.environment.get(
                ohostedcons.CoreEnv.ANSIBLE_USER_EXTRA_VARS
            ),
        )
        r = ah.run()
        self.logger.debug(r)
        try:
            validValues = r[
                'otopi_host_net'
            ]['ansible_facts']['otopi_host_net']
        except KeyError:
            raise RuntimeError(_(
                'No suitable network interfaces were found'
            ))
        if not validValues:
            raise RuntimeError(_('A Network interface is required'))
        interactive = self.environment[
            ohostedcons.NetworkEnv.BRIDGE_IF
        ] is None
        if interactive:
            default = self._get_active_interface(validValues)
            self.environment[
                ohostedcons.NetworkEnv.BRIDGE_IF
            ] = self.dialog.queryString(
                name='ovehosted_bridge_if',
                note=_(
                    'Please indicate a nic to set '
                    '{bridge} bridge on (@VALUES@) [@DEFAULT@]: '
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

    def _get_active_interface(self, valid_interfaces):
        for iface in valid_interfaces:
            try:
                if (
                    socket.getfqdn(ethtool.get_ipaddr(iface)) ==
                    socket.gethostname()
                ):
                    return iface
            except IOError:
                pass
        return valid_interfaces[0]

    @plugin.event(
        stage=plugin.Stages.STAGE_VALIDATION,
    )
    def _validate_hostname_first_host(self):
        self._hostname_helper.getHostname(
            envkey=ohostedcons.NetworkEnv.HOST_NAME,
            whichhost='first HE',
            prompttext=(
                'Please provide the hostname of this host '
                'on the management network'
            ),
            supply_default=True,
            validate_syntax=True,
            system=True,
            dns=True,
            local_non_loopback=True,
            reverse_dns=self.environment[
                ohostedcons.NetworkEnv.FQDN_REVERSE_VALIDATION
            ],
            not_local=False,
            allow_empty=False,
            v6=self.environment[
                ohostedcons.NetworkEnv.FORCE_IPV6
            ],
            v4=self.environment[
                ohostedcons.NetworkEnv.FORCE_IPV4
            ],
        )
        if not self.environment[
            ohostedcons.EngineEnv.APP_HOST_NAME
        ]:
            self.environment[
                ohostedcons.EngineEnv.APP_HOST_NAME
            ] = self.environment[
                ohostedcons.NetworkEnv.HOST_NAME
            ]

# vim: expandtab tabstop=4 shiftwidth=4
