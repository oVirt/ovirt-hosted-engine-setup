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
import time

from otopi import context as otopicontext
from otopi import plugin
from otopi import util

from ovirt_hosted_engine_ha.env import config
from ovirt_hosted_engine_ha.lib import util as ohautil
from ovirt_hosted_engine_ha.lib import image

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import vm_status


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
            self._config.get(config.ENGINE, config.DOMAIN_TYPE),
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.SD_UUID,
            self._config.get(config.ENGINE, config.SD_UUID),
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.CONF_IMG_UUID,
            self._config.get(config.ENGINE, config.CONF_IMAGE_UUID),
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.CONF_VOL_UUID,
            self._config.get(config.ENGINE, config.CONF_VOLUME_UUID),
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.VM_UUID,
            self._config.get(config.ENGINE, config.HEVMID),
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.HOST_ID,
            int(self._config.get(config.ENGINE, config.HOST_ID)),
        )
        self.environment.setdefault(
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST,
            False,
        )
        self.environment.setdefault(
            ohostedcons.Upgrade.LM_VOLUMES_UPGRADE_PROCEED,
            None,
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
            ohostedcons.CoreEnv.UPGRADE_PROCEED
        ] is None
        if interactive:
            self.environment[
                ohostedcons.CoreEnv.UPGRADE_PROCEED
            ] = self.dialog.queryString(
                name=ohostedcons.Confirms.UPGRADE_PROCEED,
                note=_(
                    'Continuing will upgrade the engine VM running on this '
                    'hosts deploying and configuring '
                    'a new appliance.\n'
                    'If your engine VM is already based on el7 you can also '
                    'simply upgrade the engine there.\n'
                    'This procedure will create a new disk on the '
                    'hosted-engine storage domain and it will backup '
                    'there the content of your current engine VM disk.\n'
                    'The new el7 based appliance will be deployed over the '
                    'existing disk destroying its content; '
                    'at any time you will be able to rollback using the '
                    'content of the backup disk.\n'
                    'You will be asked to take a backup of the running engine '
                    'and copy it to this host.\n'
                    'The engine backup will be automatically injected '
                    'and recovered on the new appliance.\n'
                    'Are you sure you want to continue? '
                    '(@VALUES@)[@DEFAULT@]: '
                ),
                # TODO: point to our site for troubleshooting info...
                prompt=True,
                validValues=(_('Yes'), _('No')),
                caseSensitive=False,
                default=_('Yes')
            ) == _('Yes').lower()
        if not self.environment[ohostedcons.CoreEnv.UPGRADE_PROCEED]:
            raise otopicontext.Abort('Aborted by user')

        self.environment[
            ohostedcons.CoreEnv.UPGRADING_APPLIANCE
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
        stage=plugin.Stages.STAGE_VALIDATION,
        condition=lambda self: (
            not self.environment[
                ohostedcons.StorageEnv.LOCKSPACE_VOLUME_UUID
            ] or
            not self.environment[ohostedcons.StorageEnv.METADATA_VOLUME_UUID]
        ),
    )
    def _validata_lm_volumes(self):
        """
        This method, if the relevant uuids aren't in the initial answerfile,
        will look for lockspace and metadata volumes on the shared
        storage identifying them by their description.
        We need to re-scan each time we run the upgrade flow since they
        could have been created in a previous upgrade attempt.
        If the volumes are not on disk, it triggers volume creation as for
        fresh deployments; volume creation code will also remove the previous
        file and create a new symlink to the volume using the same file name.
        """
        self.logger.info(_('Scanning for lockspace and metadata volumes'))
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
        for img in img_list:
            volumeslist = cli.getVolumesList(
                imageID=img,
                storagepoolID=spUUID,
                storagedomainID=sdUUID,
            )
            self.logger.debug('volumeslist: {vl}'.format(vl=volumeslist))
            if (
                volumeslist['status']['code'] != 0 or
                'items' not in volumeslist
            ):
                # avoid raising here, simply skip the unknown image
                self.logger.debug(
                    'Error fetching volumes for {image}: {message}'.format(
                        image=img,
                        message=volumeslist['status']['message'],
                    )
                )
                continue
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
                    continue
                disk_description = volumeinfo['description']
                if disk_description == self.environment[
                    ohostedcons.SanlockEnv.LOCKSPACE_NAME
                ] + '.lockspace':
                    self.environment[
                        ohostedcons.StorageEnv.LOCKSPACE_VOLUME_UUID
                    ] = vol_uuid
                    self.environment[
                        ohostedcons.StorageEnv.LOCKSPACE_IMAGE_UUID
                    ] = img
                elif disk_description == self.environment[
                    ohostedcons.SanlockEnv.LOCKSPACE_NAME
                ] + '.metadata':
                    self.environment[
                        ohostedcons.StorageEnv.METADATA_VOLUME_UUID
                    ] = vol_uuid
                    self.environment[
                        ohostedcons.StorageEnv.METADATA_IMAGE_UUID
                    ] = img

        if (
            self.environment[ohostedcons.StorageEnv.LOCKSPACE_VOLUME_UUID] and
            self.environment[ohostedcons.StorageEnv.METADATA_VOLUME_UUID]
        ):
            self.logger.info(_(
                'Lockspace and metadata volumes are already on the '
                'HE storage domain'
            ))
            return

        interactive = self.environment[
            ohostedcons.Upgrade.LM_VOLUMES_UPGRADE_PROCEED
        ] is None
        if interactive:
            self.environment[
                ohostedcons.Upgrade.LM_VOLUMES_UPGRADE_PROCEED
            ] = self.dialog.queryString(
                name=ohostedcons.Confirms.LM_VOLUMES_UPGRADE_PROCEED,
                note=_(
                    'This system was initially deployed with oVirt 3.4 '
                    'using file based metadata and lockspace area.\n'
                    'Now you have to upgrade to up to date structure '
                    'using this tool.\n'
                    'In order to do that please manually stop ovirt-ha-agent '
                    'and ovirt-ha-broker on all the other HE hosts '
                    '(but not this one). '
                    'At the end you of this procedure you can simply '
                    'manually upgrade ovirt-hosted-engine-ha and '
                    'restart ovirt-ha-agent and ovirt-ha-broker on all '
                    'the hosted-engine hosts.\n'
                    'Are you sure you want to continue? '
                    '(@VALUES@)[@DEFAULT@]: '
                ),
                prompt=True,
                validValues=(_('Yes'), _('No')),
                caseSensitive=False,
                default=_('Yes')
            ) == _('Yes').lower()
        if not self.environment[
            ohostedcons.Upgrade.LM_VOLUMES_UPGRADE_PROCEED
        ]:
            raise otopicontext.Abort('Aborted by user')

        self.logger.info(_(
            'Waiting for HA agents on other hosts to be stopped'
        ))
        vmstatus = vm_status.VmStatus()
        ready = False
        while not ready:
            ready = True
            status = vmstatus.get_status()
            self.logger.debug('hosted-engine-status: {s}'.format(s=status))
            for h in status['all_host_stats']:
                host_id = status['all_host_stats'][h]['host-id']
                stopped = status['all_host_stats'][h]['stopped']
                hostname = status['all_host_stats'][h]['hostname']
                if host_id == self.environment[ohostedcons.StorageEnv.HOST_ID]:
                    if stopped:
                        self.logger.warning(_(
                            'Please keep ovirt-ha-agent running on this host'
                        ))
                        ready = False
                else:
                    if not stopped:
                        self.logger.warning(_(
                            'ovirt-ha-agent is still active on host {h}, '
                            'please stop it (it can require a few seconds).'
                        ).format(h=hostname))
                        ready = False
            if not ready:
                time.sleep(2)

        self.environment[
            ohostedcons.Upgrade.UPGRADE_CREATE_LM_VOLUMES
        ] = True


# vim: expandtab tabstop=4 shiftwidth=4
