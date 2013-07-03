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


"""
libvirt errors workaround plugin.
"""


import gettext
import sys


from otopi import util
from otopi import plugin


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    libvirt errors workaround plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_TERMINATE,
        priority=plugin.Stages.PRIORITY_LAST + 10000,
    )
    def _terminate(self):
        #TODO: libvirt has an issue in a destructor that cause an error
        #message to be printed on stderr. The error is not relevant for us
        #but it's really ugly to see at the end of the setup execution.
        #Remove this plugin once libvirt is fixed.
        #The error reported is:
        #Exception AttributeError:
        #AttributeError("virConnect instance has no attribute
        #  'domainEventCallbacks'",) in
        #<bound method  virConnect.__del__ of
        #<libvirt.virConnect instance at  0x4280f38>> ignored
        sys.stderr.close()


# vim: expandtab tabstop=4 shiftwidth=4
