#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2013-2017 Red Hat, Inc.
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
VM machine configuration plugin.
"""

import gettext
import uuid

import distro

from otopi import plugin
from otopi import util

from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    VM machine configuration plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._distribution = distro.linux_distribution(
            full_distribution_name=0
        )[0]

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.VMEnv.CDROM_UUID,
            str(uuid.uuid4())
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.NIC_UUID,
            str(uuid.uuid4())
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.CONSOLE_UUID,
            str(uuid.uuid4())
        )
        if self._distribution in (
            'redhat',
        ):
            self.environment.setdefault(
                ohostedcons.VMEnv.EMULATED_MACHINE,
                ohostedcons.Defaults.DEFAULT_RHEL_EMULATED_MACHINE
            )
        else:
            self.environment.setdefault(
                ohostedcons.VMEnv.EMULATED_MACHINE,
                ohostedcons.Defaults.DEFAULT_EMULATED_MACHINE
            )


# vim: expandtab tabstop=4 shiftwidth=4
