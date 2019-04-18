#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2019 Red Hat, Inc.
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
network_test configuration plugin.
"""


import gettext

from otopi import plugin
from otopi import util

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import util as ohostedutil


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    network_test configuration plugin.
    """
    _TIMEOUT = 2

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._enabled = True

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        self.command.detect('ping')
        self.command.detect('dig')
        self.command.detect('nc')

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.NetworkEnv.NETWORK_TEST,
            None
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.NETWORK_TEST_TCP_ADDRESS,
            None
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.NETWORK_TEST_TCP_PORT,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_NETWORK,
            ohostedcons.Stages.CONFIG_GATEWAY,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_NETWORK,
        ),
        name=ohostedcons.Stages.CONFIG_NETWORK_TEST,
    )
    def _customization(self):

        interactive = self.environment[
            ohostedcons.NetworkEnv.NETWORK_TEST
        ] is None
        valid = False
        while not valid:
            if interactive:
                self.environment[
                    ohostedcons.NetworkEnv.NETWORK_TEST
                ] = self.dialog.queryString(
                    name='OVEHOSTED_NETWORK_TEST',
                    note=_(
                        'Please specify which way the network connectivity '
                        'should be checked (@VALUES@) [@DEFAULT@]: '
                    ),
                    validValues=(
                        'ping',
                        'dns',
                        'tcp',
                        'none'
                    ),
                    prompt=True,
                    caseSensitive=True,
                    default='dns',
                )

            network_test = self.environment[
                ohostedcons.NetworkEnv.NETWORK_TEST
            ]

            if network_test == 'ping':
                valid = ohostedutil.check_is_pingable(
                    self,
                    self.environment[
                        ohostedcons.NetworkEnv.GATEWAY
                    ]
                )
                if not valid:
                    self._propagate_error(
                        interactive,
                        _('Specified gateway is not pingable'))
            elif network_test == 'dns':
                valid = self._check_dns()
                if not valid:
                    self._propagate_error(
                        interactive,
                        _('DNS query failed'))
            elif network_test == 'tcp':
                valid = self._customize_tcp()

    def _customize_tcp(self):
        tcp_t_address = self.environment[
            ohostedcons.NetworkEnv.NETWORK_TEST_TCP_ADDRESS
        ]
        tcp_t_port = self.environment[
            ohostedcons.NetworkEnv.NETWORK_TEST_TCP_PORT
        ]

        tcp_interactive = tcp_t_address is None or tcp_t_port is None
        if tcp_interactive:
            tcp_t_address = self.dialog.queryString(
                name='OVEHOSTED_NETWORK_TEST_TCP_ADDRESS',
                note=_(
                    'Please specify the desired destination IP address '
                    'of the TCP connection test: '
                ),
                prompt=True,
                caseSensitive=True,
            )
            tcp_t_port = self.dialog.queryString(
                name='OVEHOSTED_NETWORK_TEST_TCP_PORT',
                note=_(
                    'Please specify the desired destination TCP port '
                    'of the TCP connection test: '
                ),
                prompt=True,
            )

        valid = self._check_tcp(tcp_t_address, tcp_t_port)
        if valid:
            self.environment[
                ohostedcons.NetworkEnv.NETWORK_TEST_TCP_ADDRESS
            ] = tcp_t_address

            self.environment[
                ohostedcons.NetworkEnv.NETWORK_TEST_TCP_PORT
            ] = tcp_t_port
        else:
            if tcp_interactive:
                self.environment[
                    ohostedcons.NetworkEnv.NETWORK_TEST_TCP_ADDRESS
                ] = None

                self.environment[
                    ohostedcons.NetworkEnv.NETWORK_TEST_TCP_PORT
                ] = None
            self._propagate_error(
                tcp_interactive,
                _('Failed to connect via TCP'))
        return valid

    def _propagate_error(self, interactive, error_msg):
        if not interactive:
            raise RuntimeError(error_msg)
        else:
            self.logger.error(error_msg)

    def _check_dns(self):
        cmd = [
            'dig',
            '+tries=1',
            '+time={t}'.format(t=self._TIMEOUT)
        ]

        return self._executes_successful(cmd)

    def _check_tcp(self, tcp_t_address, tcp_t_port):
        cmd = [
            'nc',
            '-w',
            str(self._TIMEOUT),
            '-z',
            tcp_t_address,
            tcp_t_port,
        ]

        return self._executes_successful(cmd)

    def _executes_successful(self, cmd):
        rc, stdout, stderr = self.execute(
            tuple(cmd),
            raiseOnError=False,
        )
        if rc == 0:
            return True
        return False

# vim: expandtab tabstop=4 shiftwidth=4
