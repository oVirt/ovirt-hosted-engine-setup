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


"""hosted engine storage plugin."""


from otopi import util

from . import blockd
from . import heconf
from . import nfs
from . import storage


@util.export
def createPlugins(context):
    blockd.Plugin(context=context)
    heconf.Plugin(context=context)
    nfs.Plugin(context=context)
    storage.Plugin(context=context)


# vim: expandtab tabstop=4 shiftwidth=4
