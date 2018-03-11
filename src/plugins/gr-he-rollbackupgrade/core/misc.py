#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2016 Red Hat, Inc.
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


"""Misc plugin."""


import gettext
import json

from otopi import context as otopicontext
from otopi import plugin
from otopi import util

from ovirt_hosted_engine_ha.env import config_constants as const
from ovirt_hosted_engine_ha.env import config
from ovirt_hosted_engine_ha.lib import util as ohautil
from ovirt_hosted_engine_ha.lib import image

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import util as ohostedutil


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """Misc plugin."""

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self._config = config.Config(logger=self.logger)
        # TODO: catch error if not configured and properly raise
        self.environment.setdefault(
            ohostedcons.StorageEnv.DOMAIN_TYPE,
            self._config.get(config.ENGINE, const.DOMAIN_TYPE),
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.SD_UUID,
            self._config.get(config.ENGINE, const.SD_UUID),
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.CONF_IMG_UUID,
            self._config.get(config.ENGINE, const.CONF_IMAGE_UUID),
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.CONF_VOL_UUID,
            self._config.get(config.ENGINE, const.CONF_VOLUME_UUID),
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.VM_UUID,
            self._config.get(config.ENGINE, const.HEVMID),
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
        priority=plugin.Stages.PRIORITY_FIRST,
    )
    def _setup(self):
        self.dialog.note(
            _(
                'During customization use CTRL-D to abort.'
            )
        )
        interactive = self.environment[
            ohostedcons.CoreEnv.ROLLBACK_PROCEED
        ] is None
        if interactive:
            self.environment[
                ohostedcons.CoreEnv.ROLLBACK_PROCEED
            ] = self.dialog.queryString(
                name=ohostedcons.Confirms.ROLLBACK_PROCEED,
                note=ohostedutil.readmeFileContent(
                    ohostedcons.FileLocations.README_ROLLBACK
                ) + _(
                    'Continuing will rollback the engine VM from a previous '
                    'upgrade attempt.\n'
                    'This procedure will restore an engine VM image '
                    'from a backup taken during an upgrade attempt.\n'
                    'The result of any action occurred after the backup '
                    'creation instant could be definitively lost.\n'
                    'Are you sure you want to continue? '
                    '(@VALUES@)[@DEFAULT@]: '
                ),
                # TODO: point to our site for troubleshooting info...
                prompt=True,
                validValues=(_('Yes'), _('No')),
                caseSensitive=False,
                default=_('Yes')
            ) == _('Yes').lower()
        if not self.environment[ohostedcons.CoreEnv.ROLLBACK_PROCEED]:
            raise otopicontext.Abort('Aborted by user')

        self.environment[
            ohostedcons.CoreEnv.ROLLBACK_UPGRADE
        ] = True

        self.environment[
            ohostedcons.VDSMEnv.VDS_CLI
        ] = ohautil.connect_vdsm_json_rpc(
            logger=self.logger,
            timeout=ohostedcons.Const.VDSCLI_SSL_TIMEOUT,
        )

        self.environment.setdefault(
            ohostedcons.CoreEnv.REQUIREMENTS_CHECK_ENABLED,
            True
        )
        try:
            # avoid: pyflakes 'Config' imported but unused error
            import ovirt.node.utils.fs
            if hasattr(ovirt.node.utils.fs, 'Config'):
                self.environment[ohostedcons.CoreEnv.NODE_SETUP] = True
        except ImportError:
            self.logger.debug('Disabling persisting file configuration')

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        condition=lambda self: (
            not self.environment[ohostedcons.Upgrade.BACKUP_IMG_UUID] or
            not self.environment[ohostedcons.CoreEnv.BACKUP_VOL_UUID]
        ),
    )
    def _choose_backup(self):
        candidate_backup_volumes = []
        cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        img = image.Image(
            self.environment[ohostedcons.StorageEnv.DOMAIN_TYPE],
            self.environment[ohostedcons.StorageEnv.SD_UUID],
        )
        img_list = img.get_images_list(
            self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        )
        self.logger.debug('img list: {il}'.format(il=img_list))
        sdUUID = self.environment[ohostedcons.StorageEnv.SD_UUID]
        spUUID = ohostedcons.Const.BLANK_UUID
        index = 0
        for img in img_list:
            volumeslist = cli.getVolumesList(
                imageID=img,
                storagepoolID=spUUID,
                storagedomainID=sdUUID,
            )
            self.logger.debug('volumeslist: {vl}'.format(vl=volumeslist))
            if volumeslist['status']['code'] != 0:
                # avoid raising here, simply skip the unknown image
                self.logger.debug(
                    'Error fetching volumes for {image}: {message}'.format(
                        image=image,
                        message=volumeslist['status']['message'],
                    )
                )
            else:
                for vol_uuid in volumeslist['items']:
                    volumeinfo = cli.getVolumeInfo(
                        volumeID=vol_uuid,
                        imageID=img,
                        storagepoolID=spUUID,
                        storagedomainID=sdUUID,
                    )
                    self.logger.debug(volumeinfo)
                    if volumeinfo['status']['code'] != 0:
                        # avoid raising here, simply skip the unknown volume
                        self.logger.debug(
                            (
                                'Error fetching volume info '
                                'for {volume}: {message}'
                            ).format(
                                volume=vol_uuid,
                                message=volumeinfo['status']['message'],
                            )
                        )
                    else:
                        disk_description = ''
                        try:
                            jd = json.loads(volumeinfo['description'])
                            disk_description = jd['DiskDescription']
                        except (ValueError, KeyError):
                            pass
                        if disk_description.startswith(
                            ohostedcons.Const.BACKUP_DISK_PREFIX
                        ):
                            candidate_backup_volumes.append({
                                'index': index+1,
                                'description': disk_description,
                                'img_uuid': img,
                                'vol_uuid': vol_uuid,
                            })
                            index += 1

        if not candidate_backup_volumes:
            self.logger.error(_(
                'Unable to find any backup disk: please ensure that a backup '
                'has been correctly created during a previous upgrade attempt'
            ))
            raise RuntimeError(_('No available backup disk'))

        bd_list = ''
        for entry in candidate_backup_volumes:
            bd_list += _(
                '\t[{i}] - {description}\n'
            ).format(
                i=entry['index'],
                description=entry['description'],
            )

        self.dialog.note(
            _(
                'The following backup disk have been '
                'found on your system:\n'
                '{bd_list}'
            ).format(
                bd_list=bd_list,
            )
        )
        sdisk = self.dialog.queryString(
            name='OVEHOSTED_RB_BACKUP_DISK',
            note=_(
                'Please select one of them  '
                '(@VALUES@) [@DEFAULT@]: '
            ),
            prompt=True,
            caseSensitive=True,
            default='1',
            validValues=[
                str(i + 1) for i in range(len(candidate_backup_volumes))
            ],
        )
        selected_disk = candidate_backup_volumes[int(sdisk)-1]
        self.environment[
            ohostedcons.Upgrade.BACKUP_IMG_UUID
        ] = selected_disk['img_uuid']
        self.environment[
            ohostedcons.Upgrade.BACKUP_VOL_UUID
        ] = selected_disk['vol_uuid']

    @plugin.event(
        stage=plugin.Stages.STAGE_VALIDATION,
    )
    def _validate_disks(self):
        cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        size = cli.getVolumeInfo(
            storagepoolID=ohostedcons.Const.BLANK_UUID,
            storagedomainID=self.environment[
                ohostedcons.StorageEnv.SD_UUID
            ],
            imageID=self.environment[
                ohostedcons.StorageEnv.IMG_UUID
            ],
            volumeID=self.environment[
                ohostedcons.StorageEnv.VOL_UUID
            ],
        )
        self.logger.debug(size)
        if size['status']['code']:
            raise RuntimeError(size['status']['message'])
        destination_size = int(size['capacity'])

        size = cli.getVolumeInfo(
            storagepoolID=ohostedcons.Const.BLANK_UUID,
            storagedomainID=self.environment[
                ohostedcons.StorageEnv.SD_UUID
            ],
            imageID=self.environment[
                ohostedcons.Upgrade.BACKUP_IMG_UUID
            ],
            volumeID=self.environment[
                ohostedcons.Upgrade.BACKUP_VOL_UUID
            ],
        )
        self.logger.debug(size)
        if size['status']['code']:
            raise RuntimeError(size['status']['message'])
        source_size = int(size['apparentsize'])

        if destination_size < source_size:
            raise RuntimeError(
                _(
                    'Error on volume size: the selected backup '
                    '(size {source}) doesn\'t fit the engine VM disk '
                    '(size {destination})'
                ).format(
                    source=source_size,
                    destination=destination_size,
                )
            )


# vim: expandtab tabstop=4 shiftwidth=4
