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


"""Check for hosted engine VM status"""


import gettext
import socket
import sys


from ovirt_hosted_engine_ha.client import client
from ovirt_hosted_engine_ha.lib.exceptions import BrokerConnectionError


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


class VmStatus(object):

    DESCRIPTIONS = {
        'first-update': _('First update'),
        'last-update-local-ts': _('Last update received'),
        'last-update-host-ts': _('Last update generated'),
        'alive': _('Host is alive'),
        'score': _('Score'),
        'engine-status': _('Engine status'),
        'hostname': _('Hostname'),
        'host-id': _('Host ID'),
        'host-ts': _('Host timestamp'),
        'live-data': _('Status up-to-date'),
        'extra': _('Extra metadata (valid at timestamp)'),
        'maintenance': _('Local maintenance')
    }

    def __init__(self):
        super(VmStatus, self).__init__()

    def print_status(self):
        ha_cli = client.HAClient()
        try:
            all_host_stats = ha_cli.get_all_host_stats()
        except (socket.error, BrokerConnectionError) as e:
            sys.stderr.write(
                _('{0}\n'.format(str(e)))
            )
            sys.stderr.write(
                _('Cannot connect to the HA daemon, please check the logs.\n')
            )
            # there is no reason to continue if we can't connect to the daemon
            return

        try:
            cluster_stats = ha_cli.get_all_stats(client.HAClient.
                                                 StatModes.GLOBAL)[0]
        except KeyError:
            # Stats were retrieved but the global section is missing.
            # This is not an error.
            cluster_stats = {}
        except (socket.error, AttributeError, IndexError):
            sys.stderr.write(
                _('Cannot connect to the HA daemon, please check the logs.\n')
            )
            cluster_stats = {}

        if cluster_stats.get(client.HAClient.GlobalMdFlags.MAINTENANCE, False):
            print _('\n\n!! Cluster is in GLOBAL MAINTENANCE mode !!\n')

        for host_id, host_stats in all_host_stats.items():
            print _('\n\n--== Host {host_id} status ==--\n').format(
                host_id=host_id
            )
            for key in host_stats.keys():
                if (key == 'engine-status' and
                        not host_stats.get('live-data', True)):
                    print _('{key:35}: {value}').format(
                        key=self.DESCRIPTIONS.get(key, key),
                        value=_('unknown stale-data'),
                    )
                elif key != 'extra':
                    print _('{key:35}: {value}').format(
                        key=self.DESCRIPTIONS.get(key, key),
                        value=host_stats[key],
                    )
            if 'extra' in host_stats.keys():
                key = 'extra'
                print _('{key:35}:').format(
                    key=self.DESCRIPTIONS.get(key, key)
                )
                for line in host_stats[key].splitlines():
                    print '\t{value}'.format(
                        value=line
                    )
        return all_host_stats


if __name__ == "__main__":
    status_checker = VmStatus()
    if not status_checker.print_status():
        sys.exit(1)


# vim: expandtab tabstop=4 shiftwidth=4
