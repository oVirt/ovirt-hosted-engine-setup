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


"""Set maintenance mode for hosted engine VM"""


import gettext
import socket
import sys

from vdsm.client import ServerError

from ovirt_hosted_engine_ha.client import client
from ovirt_hosted_engine_ha.env import config
from ovirt_hosted_engine_ha.env import config_constants as const
from ovirt_hosted_engine_ha.lib import util as ohautil


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


class Maintenance(object):

    def __init__(self):
        super(Maintenance, self).__init__()

    def set_mode(self, mode):
        ha_cli = client.HAClient()
        if mode not in (
            'local',
            'global',
            'none',
        ):
            sys.stderr.write(
                _('Invalid maintenance mode: {0}\n').format(mode)
            )
            return False
        m_local = (mode == 'local')
        m_global = (mode == 'global')
        if m_local:
            # Check that the engine VM is not running here
            vm_id = config.Config().get(config.ENGINE, const.HEVMID)
            cli = ohautil.connect_vdsm_json_rpc()
            try:
                vm_list = cli.Host.getVMList()
            except ServerError as e:
                sys.stderr.write(
                    _("Failed communicating with VDSM: {e}").format(e=e)
                )
                return False
            if vm_id in [ item['vmId'] for item in vm_list ]:
                sys.stderr.write(_(
                    "Unable to enter local maintenance mode: "
                    "the engine VM is running on the current host, "
                    "please migrate it before entering local "
                    "maintenance mode.\n"
                ))
                return False
        try:
            ha_cli.set_maintenance_mode(
                mode=ha_cli.MaintenanceMode.LOCAL,
                value=m_local,
            )
            ha_cli.set_maintenance_mode(
                mode=ha_cli.MaintenanceMode.GLOBAL,
                value=m_global,
            )
            ha_cli.set_maintenance_mode(
                mode=ha_cli.MaintenanceMode.LOCAL_MANUAL,
                value=m_local,
            )
        except socket.error:
            sys.stderr.write(
                _('Cannot connect to the HA daemon, please check the logs.\n')
            )
            return False
        return True


if __name__ == "__main__":
    maintenance = Maintenance()
    if not maintenance.set_mode(sys.argv[1]):
        sys.exit(1)


# vim: expandtab tabstop=4 shiftwidth=4
