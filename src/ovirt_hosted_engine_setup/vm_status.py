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
import json
import socket
import sys
import time

from ovirt_hosted_engine_ha.client import client
from ovirt_hosted_engine_ha.lib.exceptions import BrokerConnectionError
from ovirt_hosted_engine_ha.lib.exceptions import DisconnectionError


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


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

    def __init__(self, with_json=False):
        super(VmStatus, self).__init__()
        self.with_json = with_json

    def log_error(self, error):
        if self.with_json:
            print(
                json.loads(
                    '{{"exception": "{0}"}}'.format(
                        error.strip()
                    )
                )
            )
        else:
            sys.stderr.write(error)

    def _get_all_host_stats(self):
        ha_cli = client.HAClient()
        try:
            all_host_stats = ha_cli.get_all_host_stats()
        except (socket.error, BrokerConnectionError) as e:
            self.log_error(
                _(
                    '{0}\nCannot connect to the HA daemon, '
                    'please check the logs.\n'
                    ).format(str(e))
            )
            # there is no reason to continue if we can't connect to the daemon
            raise RuntimeError(_('Unable to connect the HA Broker '))
        return all_host_stats

    def _get_cluster_stats(self):
        ha_cli = client.HAClient()
        try:
            cluster_stats = ha_cli.get_all_stats(client.HAClient.
                                                 StatModes.GLOBAL)[0]
        except KeyError:
            # Stats were retrieved but the global section is missing.
            # This is not an error.
            cluster_stats = {}
        except (
            socket.error,
            AttributeError,
            IndexError,
            BrokerConnectionError
        ):
            self.log_error(
                _('Cannot connect to the HA daemon, please check the logs.\n')
            )
            raise RuntimeError(_('Unable to connect the HA Broker '))
        return cluster_stats

    def print_status(self):
        try:
            all_host_stats = self._get_all_host_stats()
            cluster_stats = self._get_cluster_stats()

            if self.with_json:
                for host_id, host_stats in all_host_stats.items():
                    all_host_stats[host_id]['engine-status'] = json.loads(
                        all_host_stats[host_id]['engine-status']
                    )

                all_host_stats["global_maintenance"] = cluster_stats.get(
                    client.HAClient.GlobalMdFlags.MAINTENANCE, False)

                print(json.dumps(all_host_stats))
                return all_host_stats

            glb_msg = ''
            if cluster_stats.get(
                client.HAClient.GlobalMdFlags.MAINTENANCE,
                False
            ):
                glb_msg = _(
                    '\n\n!! Cluster is in GLOBAL MAINTENANCE mode !!\n'
                )
                print(glb_msg)

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
            # Print again so it's easier to notice
            if glb_msg:
                print(glb_msg)
            return all_host_stats
        except DisconnectionError as e:
            sys.stderr.write(_(
                'An error occured while retrieving vm status, '
                'please make sure your storage is reachable.\n'
            ))
            sys.stderr.write(str(e) + '\n')
            return None
        except RuntimeError as e:
            sys.stderr.write(_(
                'An error occured while retrieving vm status, '
                'please make sure the HA daemon is ready and reachable.\n'
            ))
            sys.stderr.write(str(e) + '\n')
            return None

    def get_status(self, timeout=30):
        RETRY_DELAY = 3
        status = {}
        while timeout > 0:
            try:
                cluster_stats = self._get_cluster_stats()
                status['global_maintenance'] = cluster_stats.get(
                    client.HAClient.GlobalMdFlags.MAINTENANCE,
                    False
                )
                status['all_host_stats'] = self._get_all_host_stats()
                status['engine_vm_up'] = False
                status['engine_vm_host'] = None
                for host in status['all_host_stats'].values():
                    if 'engine-status' in host and 'live-data' in host:
                        if '"vm": "up"' in host[
                            'engine-status'
                        ] and host['live-data']:
                            status['engine_vm_up'] = True
                            status['engine_vm_host'] = host['hostname']
                return status
            except RuntimeError:
                if timeout >= RETRY_DELAY:
                    time.sleep(RETRY_DELAY)
                timeout -= RETRY_DELAY
        raise RuntimeError(
            _('Unable to connect the HA Broker within {t} seconds').format(
                t=timeout,
            )
        )


if __name__ == "__main__":
    status_checker = VmStatus(with_json=any(['--json' in sys.argv]))
    if not status_checker.print_status():
        sys.exit(1)


# vim: expandtab tabstop=4 shiftwidth=4
