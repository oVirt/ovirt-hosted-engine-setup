#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2013-2015 Red Hat, Inc.
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


import errno
import gettext
import os


import ethtool


from otopi import util
from otopi import plugin
from vdsm import netinfo


from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import vds_info


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

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        condition=lambda self: self._enabled,
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_NETWORK,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_NETWORK,
        ),
    )
    def _customization(self):
        nics = ethtool.get_devices()
        validValues = []
        enslaved = set()
        interfaces = set()
        for nic in nics:
            try:
                flags = ethtool.get_flags(nic)
                if flags & ethtool.IFF_LOOPBACK:
                    self.logger.debug('Detected loopback device %s' % nic)
                elif ethtool.get_module(nic) == 'bridge':
                    self.logger.debug('Detected bridge device %s' % nic)
                    if os.path.exists('/sys/class/net/%s/brif' % nic):
                        slaves = os.listdir('/sys/class/net/%s/brif' % nic)
                        self.logger.debug(
                            'Detected slaves for device %s: %s' % (
                                nic,
                                ','.join(slaves)
                            )
                        )
                        for iface in slaves:
                            if iface in nics:
                                enslaved.update([iface])
                elif netinfo.isbonding(nic):
                    slaves = netinfo.slaves(nic)
                    if not slaves:
                        self.logger.debug(
                            'Detected bond device %s without slaves' % nic
                        )
                    else:
                        self.logger.debug(
                            'Detected slaves for device %s: %s' % (
                                nic,
                                ','.join(slaves)
                            )
                        )
                        enslaved.update(slaves)
                        interfaces.update([nic])
                else:
                    interfaces.update([nic])
            except IOError as ioe:
                if ioe.errno in (None, errno.EOPNOTSUPP):
                    self.logger.debug('Detected unsupported device %s' % nic)
                else:
                    raise ioe
        validValues = list(interfaces - enslaved)
        self.logger.debug('Nics detected: %s' % ','.join(nics))
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
        networks = {
            self.environment[ohostedcons.NetworkEnv.BRIDGE_NAME]:
            vds_info.network(
                vds_info.capabilities(conn),
                self.environment[ohostedcons.NetworkEnv.BRIDGE_IF]
            )
        }
        _setupNetworks(conn, networks, {}, {'connectivityCheck': False})
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
