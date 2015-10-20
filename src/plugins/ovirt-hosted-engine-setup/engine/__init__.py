#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2013-2014 Red Hat, Inc.
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


"""hosted engine engine plugin."""


from otopi import util


from . import os_install
from . import fqdn
from . import health
from . import add_host


@util.export
def createPlugins(context):
    os_install.Plugin(context=context)
    fqdn.Plugin(context=context)
    health.Plugin(context=context)
    add_host.Plugin(context=context)


# vim: expandtab tabstop=4 shiftwidth=4
