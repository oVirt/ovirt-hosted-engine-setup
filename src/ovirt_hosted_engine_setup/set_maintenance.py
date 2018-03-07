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

from ovirt_hosted_engine_ha.client import client
from ovirt_hosted_engine_ha.env import config_constants as const
from ovirt_hosted_engine_ha.env import config


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
            # Check that we have a host where to migrate VM to.
            _host_id = int(config.Config().get(config.ENGINE, const.HOST_ID))
            candidates = ha_cli.get_all_host_stats()
            candidates = [h for h in candidates
                          if candidates[h]["score"] > 0 and
                          candidates[h]["host-id"] != _host_id and
                          candidates[h]["live-data"]]
            if not candidates:
                sys.stderr.write(
                    _("Unable to enter local maintenance mode: "
                      "there are no available hosts capable "
                      "of running the engine VM.\n")
                )
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
