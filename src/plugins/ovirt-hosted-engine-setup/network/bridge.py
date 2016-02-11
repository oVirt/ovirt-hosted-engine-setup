#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2013-2016 Red Hat, Inc.
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


from otopi import util
from otopi import plugin


from vdsm import netinfo


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

    @plugin.event(
        stage=plugin.Stages.STAGE_PROGRAMS
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
        condition=lambda self: (
            self._enabled and
            not self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]
        ),
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_NETWORK,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_NETWORK,
        ),
    )
    def _customization(self):
        info = netinfo.CachingNetInfo(
            vds_info.capabilities(
                self.environment[ohostedcons.VDSMEnv.VDS_CLI]
            )
        )
        interfaces = set(
            info.nics.keys() +
            info.bondings.keys() +
            info.vlans.keys()
        )
        validValues = []
        enslaved = set()
        inv_bond = set()

        for bridge in info.bridges.keys():
            enslaved.update(set(info.bridges[bridge]['ports']))
        for bond in info.bondings.keys():
            slaves = set(info.bondings[bond]['slaves'])
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
            default = ohostedcons.Defaults.DEFAULT_BRIDGE_IF
            if default not in validValues:
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
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        condition=lambda self: (
            not self._enabled and
            not self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]
        ),
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_NETWORK,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_NETWORK,
        ),
    )
    def _get_existing_bridge_interface(self):
        info = netinfo.CachingNetInfo(
            vds_info.capabilities(
                self.environment[ohostedcons.VDSMEnv.VDS_CLI]
            )
        )
        cfgif = []
        for e in info.nics.keys():
            if 'cfg' in info.nics[e]:
                cfgif.append((e, info.nics[e]['cfg']))
        for e in info.bondings.keys():
            if 'cfg' in info.bondings[e]:
                cfgif.append((e, info.bondings[e]['cfg']))
        for e in info.vlans.keys():
            if 'cfg' in info.vlans[e]:
                cfgif.append((e, info.vlans[e]['cfg']))
        bridge_ifs = [
            e[0] for e in cfgif
            if 'BRIDGE' in e[1] and
            e[1]['BRIDGE'] == self.environment[
                ohostedcons.NetworkEnv.BRIDGE_NAME
            ]
            ]
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
        condition=lambda self: not self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
    )
    def _get_hostname_from_bridge_if(self):
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
            raise RuntimeError(_('Cannot acquire nic/bond/vlan address'))
        ipaddr = status['ipaddr']
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
        condition=lambda self: self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
    )
    def _get_hostname_additional_hosts(self):
        self.environment[
            ohostedcons.NetworkEnv.HOST_NAME
        ] = socket.getfqdn()

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        name=ohostedcons.Stages.BRIDGE_AVAILABLE,
        condition=lambda self: (
            self._enabled and
            not self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]
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
        condition=lambda self: not self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
    )
    def _closeup(self):
        self.services.startup('network', True)


def _setupNetworks(conn, networks, bonds, options):
    result = conn.setupNetworks(networks, bonds, options)
    code, message = result['status']['code'], result['status']['message']
    if code != 0:
        raise RuntimeError('Failed to setup networks %r. Error code: "%s" '
                           'message: "%s"' % (networks, code, message))


def _setSafeNetworkConfig(conn):
    result = conn.setSafeNetworkConfig()
    code, message = result['status']['code'], result['status']['message']
    if code != 0:
        raise RuntimeError('Failed to persist network configuration. '
                           'Error code: "%s" message: "%s"' %
                           (code, message))


# vim: expandtab tabstop=4 shiftwidth=4
