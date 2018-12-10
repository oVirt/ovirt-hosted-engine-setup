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
sanlock lockspace initialization plugin.
"""

import gettext

from otopi import plugin
from otopi import util

from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    sanlock lockspace initialization plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT
    )
    def _init(self):

        # TODO: check what's still in use and remove everything else from here
        self.environment.setdefault(
            ohostedcons.SanlockEnv.SANLOCK_SERVICE,
            ohostedcons.Defaults.DEFAULT_SANLOCK_SERVICE
        )
        self.environment.setdefault(
            ohostedcons.SanlockEnv.LOCKSPACE_NAME,
            ohostedcons.Defaults.DEFAULT_LOCKSPACE_NAME
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.METADATA_VOLUME_UUID,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.METADATA_IMAGE_UUID,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.LOCKSPACE_VOLUME_UUID,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.LOCKSPACE_IMAGE_UUID,
            None
        )


# vim: expandtab tabstop=4 shiftwidth=4
