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
VM image creation plugin.
"""

import uuid
import gettext


from otopi import util
from otopi import plugin


from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import domains as ohosteddomains
from ovirt_hosted_engine_setup import tasks


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
            None
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
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        condition=lambda self: not self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_VM,
            ohostedcons.Stages.CONFIG_OVF_IMPORT,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_VM,
        ),
    )
    def _disk_customization(self):
        interactive = self.environment[
            ohostedcons.StorageEnv.IMAGE_SIZE_GB
        ] is None

        estimate_gb = None
        if self.environment[
            ohostedcons.StorageEnv.BDEVICE_SIZE_GB
        ] is not None:
            # Conservative estimate, the exact value could be gathered from
            # vginfo but at this point the VG has still has to be created.
            # Later on it will be checked against the real value
            estimate_gb = int(self.environment[
                ohostedcons.StorageEnv.BDEVICE_SIZE_GB
            ]) - ohostedcons.Const.STORAGE_DOMAIN_OVERHEAD_GIB

        valid = False
        while not valid:
            if interactive:
                self.environment[
                    ohostedcons.StorageEnv.IMAGE_SIZE_GB
                ] = self.dialog.queryString(
                    name='ovehosted_vmenv_mem',
                    note=_(
                        'Please specify the disk size of the VM in GB '
                        '[Defaults to minimum requirement: @DEFAULT@]: '
                    ),
                    prompt=True,
                    default=ohostedcons.Defaults.DEFAULT_IMAGE_SIZE_GB,
                )
            try:
                valid = True
                if estimate_gb is not None and int(
                    self.environment[ohostedcons.StorageEnv.IMAGE_SIZE_GB]
                ) > estimate_gb:
                    self.logger.warning(
                        _(
                            'Not enough free space, '
                            'about {estimate} GiB are available'
                        ).format(
                            estimate=estimate_gb
                        )
                    )
                    valid = False
                if valid and int(
                    self.environment[ohostedcons.StorageEnv.IMAGE_SIZE_GB]
                ) < ohostedcons.Defaults.DEFAULT_IMAGE_SIZE_GB:
                    self.logger.warning(
                        _('Minimum requirements for disk size not met')
                    )
                    if (
                        interactive and
                        self.environment[
                            ohostedcons.CoreEnv.REQUIREMENTS_CHECK_ENABLED
                        ] and
                        not self.dialog.queryString(
                            name=ohostedcons.Confirms.DISK_PROCEED,
                            note=_(
                                'Continue with specified disk size? '
                                '(@VALUES@)[@DEFAULT@]: '
                            ),
                            prompt=True,
                            validValues=(_('Yes'), _('No')),
                            caseSensitive=False,
                            default=_('No')
                        ) == _('Yes').lower()
                    ):
                        valid = False
            except ValueError:
                valid = False
                if not interactive:
                    raise RuntimeError(
                        _('Invalid disk size specified: {size}').format(
                            size=self.environment[
                                ohostedcons.StorageEnv.IMAGE_SIZE_GB
                            ],
                        )
                    )
                else:
                    self.logger.error(
                        _('Invalid disk size specified: {size}').format(
                            size=self.environment[
                                ohostedcons.StorageEnv.IMAGE_SIZE_GB
                            ],
                        )
                    )

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        after=(
            ohostedcons.Stages.SANLOCK_INITIALIZED,
        ),
        name=ohostedcons.Stages.VM_IMAGE_AVAILABLE,
        condition=lambda self: not self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
    )
    def _misc(self):
        sdUUID = self.environment[ohostedcons.StorageEnv.SD_UUID]
        spUUID = self.environment[ohostedcons.StorageEnv.SP_UUID]
        imgUUID = self.environment[ohostedcons.StorageEnv.IMG_UUID]
        volUUID = self.environment[ohostedcons.StorageEnv.VOL_UUID]
        cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]

        if self.environment[ohostedcons.StorageEnv.DOMAIN_TYPE] in (
            ohostedcons.DomainTypes.ISCSI,
            ohostedcons.DomainTypes.FC,
        ):
            # Checking the available space on VG where
            # we have to preallocate the image
            vginfo = cli.getVGInfo(
                self.environment[ohostedcons.StorageEnv.VG_UUID]
            )
            self.logger.debug(vginfo)
            if vginfo['status']['code'] != 0:
                raise RuntimeError(vginfo['status']['message'])
            vgfree = int(vginfo['info']['vgfree'])
            available_gb = vgfree / pow(2, 30)
            if int(
                self.environment[
                    ohostedcons.StorageEnv.IMAGE_SIZE_GB
                ]
            ) > available_gb:
                raise ohosteddomains.InsufficientSpaceError(
                    _(
                        'Error: the VG on block device has capacity of only '
                        '{available_gb} GiB while '
                        '{image_gb} GiB is required for the image'
                    ).format(
                        available_gb=available_gb,
                        image_gb=self.environment[
                            ohostedcons.StorageEnv.IMAGE_SIZE_GB
                        ],
                    )
                )

        self.logger.info(_('Creating VM Image'))
        self.logger.debug('createVolume')
        volFormat = ohostedcons.VolumeFormat.RAW_FORMAT
        preallocate = ohostedcons.VolumeTypes.SPARSE_VOL
        if self.environment[ohostedcons.StorageEnv.DOMAIN_TYPE] in (
            ohostedcons.DomainTypes.ISCSI,
            ohostedcons.DomainTypes.FC,
        ):
            # Can't use sparse volume on block devices
            preallocate = ohostedcons.VolumeTypes.PREALLOCATED_VOL

        diskType = 2
        status = cli.createVolume(
            sdUUID,
            spUUID,
            imgUUID,
            str(
                int(
                    self.environment[ohostedcons.StorageEnv.IMAGE_SIZE_GB]
                ) * pow(2, 30)
            ),
            volFormat,
            preallocate,
            diskType,
            volUUID,
            self.environment[ohostedcons.StorageEnv.IMAGE_DESC],
        )
        self.logger.debug(status)
        if status['status']['code'] == 0:
            self.logger.debug(
                (
                    'Created volume {newUUID}, request was:\n'
                    '- image: {imgUUID}\n'
                    '- volume: {volUUID}'
                ).format(
                    newUUID=status['status']['message'],
                    imgUUID=imgUUID,
                    volUUID=volUUID,
                )
            )
        else:
            raise RuntimeError(status['status']['message'])
        waiter = tasks.TaskWaiter(self.environment)
        waiter.wait()


# vim: expandtab tabstop=4 shiftwidth=4
