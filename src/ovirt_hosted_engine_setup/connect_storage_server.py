#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2015 Red Hat, Inc.
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


"""Connect storage server"""

from ovirt_hosted_engine_ha.client import client

from ovirt_hosted_engine_setup import constants as ohostedcons

if __name__ == "__main__":
    ha_cli = client.HAClient()
    ha_cli.connect_storage_server(
        timeout=ohostedcons.Const.STORAGE_SERVER_TIMEOUT,
    )
