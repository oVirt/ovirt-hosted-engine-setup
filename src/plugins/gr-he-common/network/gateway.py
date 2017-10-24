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
gateway configuration plugin.
"""


import gettext
import os
import socket
import struct

from otopi import plugin
from otopi import util

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import util as ohostedutil


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    gateway configuration plugin.
    """
    ROUTE_DESTINATION = 1
    ROUTE_GW = 2

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._enabled = True

    def _get_default_gw(self):
        gateway = ''
        with open('/proc/net/route', 'r') as f:
            lines = f.read().splitlines()
            for line in lines:
                data = line.split()
                if data[self.ROUTE_DESTINATION] == '00000000':
                    gateway = socket.inet_ntoa(
                        struct.pack(
                            'I',
                            int(data[self.ROUTE_GW], 16)
                        )
                    )
                    break
        return gateway

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.NetworkEnv.GATEWAY,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        self.command.detect('ping')
        if (
            os.environ.get('proxy') or
            os.environ.get('http_proxy') or
            os.environ.get('https_proxy')
        ):
            self.logger.warning(_(
                'It seems that this host is configured to use a proxy, '
                'please ensure that this host will be able to reach the '
                'engine VM trough that proxy or add a specific exception.'
            ))

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_NETWORK,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_NETWORK,
        ),
        name=ohostedcons.Stages.CONFIG_GATEWAY,
        condition=lambda self: (
            not self.environment[ohostedcons.CoreEnv.UPGRADING_APPLIANCE] and
            not self.environment[ohostedcons.CoreEnv.ROLLBACK_UPGRADE]
        ),
    )
    def _customization(self):

        interactive = self.environment[
            ohostedcons.NetworkEnv.GATEWAY
        ] is None
        valid = False
        while not valid:
            if interactive:
                self.environment[
                    ohostedcons.NetworkEnv.GATEWAY
                ] = self.dialog.queryString(
                    name='OVEHOSTED_GATEWAY',
                    note=_(
                        'Please indicate a pingable gateway IP address '
                        '[@DEFAULT@]: '
                    ),
                    prompt=True,
                    caseSensitive=True,
                    default=self._get_default_gw(),
                )
            valid = ohostedutil.check_is_pingable(
                self,
                self.environment[
                    ohostedcons.NetworkEnv.GATEWAY
                ]
            )
            if not valid:
                if not interactive:
                    raise RuntimeError(_('Specified gateway is not pingable'))
                else:
                    self.logger.error(_('Specified gateway is not pingable'))


# vim: expandtab tabstop=4 shiftwidth=4
