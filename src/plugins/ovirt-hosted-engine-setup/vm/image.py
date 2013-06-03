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
VM image creation plugin.
"""

import uuid
import gettext


from otopi import util
from otopi import plugin


from ovirt_hosted_engine_setup import constants as ohostedcons


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    VM image creation plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.StorageEnv.IMAGE_SIZE_GB,
            ohostedcons.Defaults.DEFAULT_IMAGE_SIZE_GB
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.IMG_UUID,
            str(uuid.uuid4())
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.VOL_UUID,
            str(uuid.uuid4())
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.IMAGE_DESC,
            ohostedcons.Defaults.DEFAULT_IMAGE_DESC
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        after=[
            ohostedcons.Stages.STORAGE_AVAILABLE,
        ],
        name=ohostedcons.Stages.VM_IMAGE_AVAILABLE,
    )
    def _misc(self):
        sdUUID = self.environment[ohostedcons.StorageEnv.SD_UUID]
        spUUID = self.environment[ohostedcons.StorageEnv.SP_UUID]
        imgUUID = self.environment[ohostedcons.StorageEnv.IMG_UUID]
        volUUID = self.environment[ohostedcons.StorageEnv.VOL_UUID]
        serv = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        self.logger.info(_('Creating VM Image'))
        self.logger.debug('createVolume')
        status, message = serv.createVolume([
            sdUUID,
            spUUID,
            imgUUID,
            self.environment[ohostedcons.StorageEnv.IMAGE_SIZE_GB],
            5,
            2,
            2,
            volUUID,
            self.environment[ohostedcons.StorageEnv.IMAGE_DESC],
        ])
        if status == 0:
            self.logger.debug(
                (
                    'Created volume {newUUID}, request was:\n'
                    '- image: {imgUUID}\n'
                    '- volume: {volUUID}'
                ).format(
                    newUUID=message,
                    imgUUID=imgUUID,
                    volUUID=volUUID,
                )
            )
        else:
            raise RuntimeError(message)


# vim: expandtab tabstop=4 shiftwidth=4
