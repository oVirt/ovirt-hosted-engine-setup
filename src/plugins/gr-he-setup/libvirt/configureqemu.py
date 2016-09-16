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


"""
libvirt qemu configuration plugin.
"""


import gettext
import os
import re

from otopi import constants as otopicons
from otopi import filetransaction
from otopi import plugin
from otopi import transaction
from otopi import util

from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    libvirt qemu configuration plugin.
    """

    RE_LOCK_MANAGER = re.compile(r'^lock_manager\s*=\s*\"(\w+)\"')

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    def _restartLibvirt(self):
        """
        Restart libvirt service
        """
        for state in (False, True):
            self.services.state(
                name='libvirtd',
                state=state,
            )

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        name=ohostedcons.Stages.LIBVIRT_CONFIGURED,
    )
    def _misc(self):
        self.logger.info(_('Configuring libvirt'))
        old_content = []
        if os.path.exists(ohostedcons.FileLocations.LIBVIRT_QEMU_CONF):
            with open(ohostedcons.FileLocations.LIBVIRT_QEMU_CONF, 'r') as f:
                old_content = f.read().splitlines()
        new_content = []
        new_conf = 'lock_manager="sanlock"'
        found = False
        for line in old_content:
            match = self.RE_LOCK_MANAGER.match(line)
            if match:
                found = True
                self.logger.debug(
                    'Changing lock_manager from {old} to sanlock'.format(
                        old=match.group(1)
                    )
                )
                line = new_conf
            new_content.append(line)
        if not found:
            new_content.append(new_conf)
        with transaction.Transaction() as localtransaction:
            localtransaction.append(
                filetransaction.FileTransaction(
                    name=ohostedcons.FileLocations.LIBVIRT_QEMU_CONF,
                    content=new_content,
                    modifiedList=self.environment[
                        otopicons.CoreEnv.MODIFIED_FILES
                    ],
                ),
            )
        if not self.services.supportsDependency:
            if self.services.exists('cgconfig'):
                self.services.state('cgconfig', True)
                self.services.startup('cgconfig', True)
            if self.services.exists('messagebus'):
                self.services.state('messagebus', True)
                self.services.startup('messagebus', True)
            if self.services.exists('libvirtd'):
                self.services.state('libvirtd', True)
                self.services.startup('libvirtd', True)
        self._restartLibvirt()


# vim: expandtab tabstop=4 shiftwidth=4
