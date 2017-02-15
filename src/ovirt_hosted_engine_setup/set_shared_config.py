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


"""Set shared storage configuration for hosted engine VM"""


import gettext
import socket
import sys

from ovirt_hosted_engine_ha.client import client


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


class SetSharedConfig(object):

    def set_shared_config(self, key, value, config_type):
        ha_cli = client.HAClient()
        try:
            ha_cli.set_shared_config(key, value, config_type)
        except socket.error:
            sys.stderr.write(
                _('Cannot connect to the HA daemon, please check the logs.\n')
            )
            return False
        except KeyError:
            config_keys_for_type = ha_cli.get_all_config_keys(config_type)
            sys.stderr.write(
                _('Invalid configuration key {key}.\n'.
                  format(key=key)
                 )
            )
            sys.stderr.write(
                _('Available keys are:\n')
            )
            for c_type in config_keys_for_type:
                sys.stderr.write(
                    _('{c_type} : {keys}\n'.
                      format(c_type=c_type,
                             keys=config_keys_for_type[c_type]
                            )
                     )
                )
            return False
        except Exception as e:
            sys.stderr.write(str(e) + '\n')
            return False
        return True


if __name__ == "__main__":
    set_shared_config = SetSharedConfig()
    sys.argv.pop(0)
    if not set_shared_config.set_shared_config(*sys.argv):
        sys.exit(1)

# vim: expandtab tabstop=4 shiftwidth=4
