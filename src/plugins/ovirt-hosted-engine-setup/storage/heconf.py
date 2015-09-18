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


"""
HEConf storage domain plugin.
"""

import gettext
import uuid


from otopi import plugin
from otopi import util


from ovirt_hosted_engine_ha.lib import heconflib
from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    Local storage plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self.cli = None

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.StorageEnv.CONF_IMAGE_SIZE_GB,
            ohostedcons.Defaults.DEFAULT_CONF_IMAGE_SIZE_GB
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.CONF_IMG_UUID,
            str(uuid.uuid4())
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.CONF_VOL_UUID,
            str(uuid.uuid4())
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.ANSWERFILE_CONTENT,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.HECONF_CONTENT,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.BROKER_CONF_CONTENT,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.VM_CONF_CONTENT,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        name=ohostedcons.Stages.CONF_VOLUME_AVAILABLE,
        after=(ohostedcons.Stages.STORAGE_AVAILABLE,),
        condition=lambda self: not self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
    )
    def _misc_create_volume(self):
        diskType = 2
        heconflib.create_and_prepare_image(
            self.logger,
            self.environment[ohostedcons.VDSMEnv.VDS_CLI],
            ohostedcons.VolumeFormat.RAW_FORMAT,
            ohostedcons.VolumeTypes.PREALLOCATED_VOL,
            self.environment[ohostedcons.StorageEnv.SD_UUID],
            self.environment[ohostedcons.StorageEnv.SP_UUID],
            self.environment[ohostedcons.StorageEnv.CONF_IMG_UUID],
            self.environment[ohostedcons.StorageEnv.CONF_VOL_UUID],
            diskType,
            self.environment[ohostedcons.StorageEnv.CONF_IMAGE_SIZE_GB],
            ohostedcons.Const.CONF_IMAGE_DESC,
        )
        #  TODO: add this volume to the engine to prevent misuse

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        after=(
            ohostedcons.Stages.ANSWER_FILE_AVAILABLE,
            ohostedcons.Stages.OS_INSTALLED,
            ohostedcons.Stages.IMAGES_REPREPARED,
        ),
        condition=lambda self: not self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
        name=ohostedcons.Stages.CONF_IMAGE_AVAILABLE,
    )
    def _closeup_create_tar(self):
        self.logger.info(_(
            'Saving hosted-engine configuration '
            'on the shared storage domain'
        ))

        dest = heconflib.get_volume_path(
            self.environment[
                ohostedcons.StorageEnv.DOMAIN_TYPE
            ],
            self.environment[ohostedcons.StorageEnv.SD_UUID],
            self.environment[ohostedcons.StorageEnv.CONF_IMG_UUID],
            self.environment[ohostedcons.StorageEnv.CONF_VOL_UUID]
        )

        heconflib.create_heconfimage(
            self.logger,
            self.environment[
                ohostedcons.StorageEnv.ANSWERFILE_CONTENT
            ],
            self.environment[
                ohostedcons.StorageEnv.HECONF_CONTENT
            ],
            self.environment[
                ohostedcons.StorageEnv.BROKER_CONF_CONTENT
            ],
            self.environment[
                ohostedcons.StorageEnv.VM_CONF_CONTENT
            ],
            dest
        )


# vim: expandtab tabstop=4 shiftwidth=4
