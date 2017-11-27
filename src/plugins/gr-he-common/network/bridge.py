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

from vdsm.client import ServerError

from ovirt_setup_lib import hostname as osetuphostname

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import vds_info


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


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
            self._enabled = False

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        condition=lambda self: (
            self._enabled
        ),
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_NETWORK,
            ohostedcons.Stages.BRIDGE_DETECTED,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_NETWORK,
        ),
    )
    def _customization(self):
        validValues = []
        if self.environment[ohostedcons.CoreEnv.ANSIBLE_DEPLOYMENT]:
            # TODO: fix for bond and vlan with ansible
            validValues = ethtool.get_devices()
            if 'lo' in validValues:
                validValues.remove('lo')
        else:
            INVALID_BOND_MODES = ('0', '5', '6')
            ALLOW_INVALID_BOND_MODES =  \
                ohostedcons.NetworkEnv.ALLOW_INVALID_BOND_MODES

            caps = vds_info.capabilities(
                self.environment[ohostedcons.VDSMEnv.VDS_CLI]
            )
            interfaces = set(
                caps['nics'].keys() +
                caps['bondings'].keys() +
                caps['vlans'].keys()
            )
            validValues = []
            enslaved = set()
            inv_bond = set()

            for bridge in caps['bridges'].keys():
                enslaved.update(set(caps['bridges'][bridge]['ports']))
            for bond in caps['bondings'].keys():
                bondMode = caps['bondings'][bond]['opts']['mode']
                if (bondMode in INVALID_BOND_MODES):
                    self.logger.warning(
                        _(
                            "Bond {bondname} is on mode {bondmode}, "
                            "modes {invalid} are not supported"
                        ).format(
                            bondname=bond,
                            bondmode=bondMode,
                            invalid=INVALID_BOND_MODES
                        )
                    )
                    if not self.environment[ALLOW_INVALID_BOND_MODES]:
                        inv_bond.update(set([bond]))
                    else:
                        self.logger.warning(
                            _(
                                "Allowing anyway, as enforced by {key}={val}"
                            ).format(
                                key=ALLOW_INVALID_BOND_MODES,
                                val=self.environment[ALLOW_INVALID_BOND_MODES]
                            )
                        )
                slaves = set(caps['bondings'][bond]['slaves'])
                if slaves:
                    enslaved.update(slaves)
                else:
                    self.logger.debug(
                        'Detected bond device %s without slaves' % bond
                    )
                    inv_bond.update(set([bond]))

            validValues = list(interfaces - enslaved - inv_bond)
            self.logger.debug('Nics detected: %s' % ','.join(interfaces))
            self.logger.debug('Nics enslaved: %s' % ','.join(enslaved))
            self.logger.debug('Nics valid: %s' % ','.join(validValues))
        if not validValues:
            if enslaved:
                raise RuntimeError(
                    _(
                        'The following existing interfaces are not suitable '
                        'for vdsm: {enslaved}. You might want to pull out an '
                        'interface out of a bridge to be able to use it'
                    ).format(
                        enslaved=','.join(enslaved)
                    )
                )
            else:
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
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        condition=lambda self: (
            not self._enabled and
            # TODO: properly handle it without vdsm
            not self.environment[ohostedcons.CoreEnv.ANSIBLE_DEPLOYMENT]
        ),
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_NETWORK,
            ohostedcons.Stages.BRIDGE_DETECTED,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_NETWORK,
        ),
    )
    def _get_existing_bridge_interface(self):
        caps = vds_info.capabilities(
            self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        )
        bridge_name = self.environment[ohostedcons.NetworkEnv.BRIDGE_NAME]
        bridge_network = caps['networks'].get(bridge_name)
        bridge_ifs = bridge_network['ports'] if bridge_network else []
        if len(bridge_ifs) > 1:
            self.logger.warning(
                _(
                    'Unable to uniquely detect the interface where Bridge '
                    '{bridge} has been created on, {bridge_ifs} appear to be '
                    'valid alternatives'
                ).format(
                    bridge=self.environment[
                        ohostedcons.NetworkEnv.BRIDGE_NAME
                    ],
                    bridge_ifs=bridge_ifs,
                )
            )
        elif len(bridge_ifs) < 1:
            self.logger.warning(
                _(
                    'Unable to detect the interface where Bridge '
                    '{bridge} has been created on'
                ).format(
                    bridge=self.environment[
                        ohostedcons.NetworkEnv.BRIDGE_NAME
                    ],
                )
            )
        else:
            self.environment[
                ohostedcons.NetworkEnv.BRIDGE_IF
            ] = bridge_ifs[0]

    @plugin.event(
        stage=plugin.Stages.STAGE_VALIDATION,
        name=ohostedcons.Stages.GOT_HOSTNAME_FIRST_HOST,
    )
    def _get_hostname_from_bridge_if(self):
        if self.environment[ohostedcons.CoreEnv.ANSIBLE_DEPLOYMENT]:
            # TODO: properly handle it without vdsm
            if not self.environment[
                ohostedcons.NetworkEnv.HOST_NAME
            ]:
                self.environment[
                    ohostedcons.NetworkEnv.HOST_NAME
                ] = socket.gethostname()
            if not self.environment[
                ohostedcons.EngineEnv.APP_HOST_NAME
            ]:
                self.environment[
                    ohostedcons.EngineEnv.APP_HOST_NAME
                ] = socket.gethostname()
        else:
            ipaddr = None
            if self._enabled:
                # acquiring interface address
                configuration, status = vds_info.network(
                    vds_info.capabilities(
                        self.environment[ohostedcons.VDSMEnv.VDS_CLI]
                    ),
                    self.environment[
                        ohostedcons.NetworkEnv.BRIDGE_IF
                    ],
                )
                self.logger.debug('Network info: {info}'.format(info=status))
                if 'ipaddr' not in status:
                    raise RuntimeError(_(
                        'Cannot acquire nic/bond/vlan address'
                    ))
                ipaddr = status['ipaddr']
            else:
                # acquiring bridge address
                caps = vds_info.capabilities(
                    self.environment[ohostedcons.VDSMEnv.VDS_CLI]
                )

                if 'networks' in caps:
                    networks = caps['networks']
                    if self.environment[
                        ohostedcons.NetworkEnv.BRIDGE_NAME
                    ] in networks:
                        bridge = networks[
                            self.environment[
                                ohostedcons.NetworkEnv.BRIDGE_NAME
                            ]
                        ]
                        if 'addr' in bridge:
                            ipaddr = bridge['addr']
                if not ipaddr:
                    raise RuntimeError(_('Cannot acquire bridge address'))

            hostname, aliaslist, ipaddrlist = socket.gethostbyaddr(ipaddr)
            self.logger.debug(
                "hostname: '{h}', aliaslist: '{a}', ipaddrlist: '{i}'".format(
                    h=hostname,
                    a=aliaslist,
                    i=ipaddrlist,
                )
            )
            if len(ipaddrlist) > 1:
                other_ip = set(ipaddrlist) - set([ipaddr])
                raise RuntimeError(_(
                    "hostname '{h}' doesn't uniquely match the interface "
                    "'{i}' selected for the management bridge; "
                    "it matches also interface with IP {o}. "
                    "Please make sure that the hostname got from "
                    "the interface for the management network resolves "
                    "only there."
                ).format(
                    h=hostname,
                    i=self.environment[
                        ohostedcons.NetworkEnv.BRIDGE_IF
                    ],
                    o=other_ip,
                ))
            self.environment[
                ohostedcons.NetworkEnv.HOST_NAME
            ] = hostname

    @plugin.event(
        stage=plugin.Stages.STAGE_VALIDATION,
        after=(
            ohostedcons.Stages.GOT_HOSTNAME_FIRST_HOST,
        ),
    )
    def _validate_hostname_first_host(self):
        self._hostname_helper.getHostname(
            envkey=ohostedcons.NetworkEnv.HOST_NAME,
            whichhost='HostedEngine',
            supply_default=False,
            validate_syntax=True,
            system=True,
            dns=True,
            local_non_loopback=True,
            reverse_dns=self.environment[
                ohostedcons.NetworkEnv.FQDN_REVERSE_VALIDATION
            ],
            not_local=False,
            allow_empty=False,
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        name=ohostedcons.Stages.BRIDGE_AVAILABLE,
        condition=lambda self: (
            self._enabled and
            not self.environment[ohostedcons.CoreEnv.ANSIBLE_DEPLOYMENT]
        ),
        after=(
            ohostedcons.Stages.VDSMD_START,
        ),
    )
    def _misc(self):
        self.logger.info(_('Configuring the management bridge'))
        conn = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        nconf, nstatus = vds_info.network(
            vds_info.capabilities(conn),
            self.environment[ohostedcons.NetworkEnv.BRIDGE_IF]
        )
        networks = {
            self.environment[ohostedcons.NetworkEnv.BRIDGE_NAME]:
            nconf
        }
        bonds = {}
        options = {'connectivityCheck': False}
        self.logger.debug('networks: {networks}'.format(networks=networks))
        self.logger.debug('bonds: {bonds}'.format(bonds=bonds))
        self.logger.debug('options: {options}'.format(options=options))
        _setupNetworks(conn, networks, bonds, options)
        _setSafeNetworkConfig(conn)

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        condition=lambda self: (
            not self.environment[ohostedcons.CoreEnv.ANSIBLE_DEPLOYMENT]
        ),
    )
    def _closeup(self):
        self.services.startup('network', True)


def _setupNetworks(conn, networks, bonds, options):
    try:
        conn.Host.setupNetworks(
            networks=networks,
            bondings=bonds,
            options=options
        )
    except ServerError as e:
        raise RuntimeError('Failed to setup networks %r. Error: "%s"' %
                           (networks, str(e)))


def _setSafeNetworkConfig(conn):
    try:
        conn.Host.setSafeNetworkConfig()
    except ServerError as e:
        raise RuntimeError('Failed to persist network configuration. '
                           'Error: "%s"' % str(e))


# vim: expandtab tabstop=4 shiftwidth=4
