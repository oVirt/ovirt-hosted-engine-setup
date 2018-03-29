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
VM image creation plugin.
"""


import gettext
import uuid

from otopi import plugin
from otopi import util

from vdsm.client import ServerError

from ovirt_hosted_engine_ha.lib import heconflib

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import domains as ohosteddomains


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


def _int_or_0(x):
    return int(x) if x else 0


@util.export
class Plugin(plugin.PluginBase):
    """
    VM image creation plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    def _customize_disk_size(self, available_gb=None):
        interactive = self.environment[
            ohostedcons.StorageEnv.IMAGE_SIZE_GB
        ] is None
        default = max(
            _int_or_0(ohostedcons.Defaults.DEFAULT_IMAGE_SIZE_GB),
            _int_or_0(self.environment[ohostedcons.StorageEnv.OVF_SIZE_GB]),
            _int_or_0(self.environment[ohostedcons.Upgrade.BACKUP_SIZE_GB])
        )

        valid = False
        while not valid:
            if interactive:
                self.environment[
                    ohostedcons.StorageEnv.IMAGE_SIZE_GB
                ] = self.dialog.queryString(
                    name='ovehosted_vmenv_image',
                    note=_(
                        'Please specify the size of the VM disk in GB: '
                        '[@DEFAULT@]: '
                    ),
                    prompt=True,
                    default=default,
                )
            try:
                valid = True
                if available_gb is not None and (
                    int(
                        self.environment[
                            ohostedcons.StorageEnv.IMAGE_SIZE_GB
                        ]
                    ) + ohostedcons.Const.OVFSTORE_SIZE_GIB +
                    ohostedcons.Const.CRITICAL_SPACE_ACTION_BLOCKER
                ) > available_gb:
                    msg = _(
                        'Not enough free space, '
                        'about {estimate} GiB will be available '
                        'within the storage domain '
                        '(required {required} GiB for the engine VM disk '
                        'plus {req_ovf} GiB for the OVF_STORE disks creation)'
                    ).format(
                        estimate=available_gb,
                        required=self.environment[
                            ohostedcons.StorageEnv.IMAGE_SIZE_GB
                        ],
                        req_ovf=(
                            ohostedcons.Const.OVFSTORE_SIZE_GIB +
                            ohostedcons.Const.CRITICAL_SPACE_ACTION_BLOCKER
                        ),
                    )
                    self.logger.warning(msg)
                    valid = False
                    if not interactive:
                        raise RuntimeError(msg)

                if valid and self.environment[
                    ohostedcons.StorageEnv.OVF_SIZE_GB
                ] and int(
                    self.environment[ohostedcons.StorageEnv.OVF_SIZE_GB]
                ) > int(
                    self.environment[ohostedcons.StorageEnv.IMAGE_SIZE_GB]
                ):
                    msg = _(
                        'Minimum requirements to fit the disk from the '
                        'appliance OVF not met (required {required} GiB)'
                    ).format(
                        required=self.environment[
                            ohostedcons.StorageEnv.OVF_SIZE_GB
                        ],
                    )
                    self.logger.warning(msg)
                    valid = False
                    if not interactive:
                        raise RuntimeError(msg)

                if valid and self.environment[
                    ohostedcons.Upgrade.BACKUP_SIZE_GB
                ] and int(
                    self.environment[ohostedcons.Upgrade.BACKUP_SIZE_GB]
                ) > int(
                    self.environment[ohostedcons.StorageEnv.IMAGE_SIZE_GB]
                ):
                    msg = _(
                        'The current appliance disk is bigger than the '
                        'proposed size, this upgrade procedure cannot shrink '
                        'the existing disk (minimum {minimum} GiB).'
                    ).format(
                        minimum=self.environment[
                            ohostedcons.Upgrade.BACKUP_SIZE_GB
                        ],
                    )
                    self.logger.warning(msg)
                    valid = False
                    if not interactive:
                        raise RuntimeError(msg)

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
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.StorageEnv.IMAGE_SIZE_GB,
            None
        )
        self.environment.setdefault(
            ohostedcons.Upgrade.BACKUP_SIZE_GB,
            None,
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.BDEVICE_SIZE_GB,
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
        condition=lambda self: (
            not self.environment[ohostedcons.CoreEnv.ROLLBACK_UPGRADE] and
            not self.environment[ohostedcons.CoreEnv.ANSIBLE_DEPLOYMENT]
        ),
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_VM,
            ohostedcons.Stages.CONFIG_OVF_IMPORT,
            ohostedcons.Stages.REQUIRE_ANSWER_FILE
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_VM,
        ),
    )
    def _disk_customization(self):
        estimate_gb = None
        if self.environment[
            ohostedcons.StorageEnv.BDEVICE_SIZE_GB
        ] is not None and not self.environment[
            ohostedcons.CoreEnv.UPGRADING_APPLIANCE
        ]:
            # Conservative estimate, the exact value could be gathered from
            # vginfo but at this point the VG has still has to be created.
            # Later on it will be checked against the real value
            estimate_gb = int(self.environment[
                ohostedcons.StorageEnv.BDEVICE_SIZE_GB
            ]) - ohostedcons.Const.STORAGE_DOMAIN_OVERHEAD_GIB
        self._customize_disk_size(estimate_gb)

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        after=(
            ohostedcons.Stages.SANLOCK_INITIALIZED,
        ),
        name=ohostedcons.Stages.VM_IMAGE_AVAILABLE,
        condition=lambda self: (
            not self.environment[ohostedcons.CoreEnv.ROLLBACK_UPGRADE] and
            not self.environment[ohostedcons.CoreEnv.UPGRADING_APPLIANCE] and
            not self.environment[ohostedcons.CoreEnv.ANSIBLE_DEPLOYMENT]
        ),
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
            try:
                vg_uuid = self.environment[ohostedcons.StorageEnv.VG_UUID]
                vginfo = cli.LVMVolumeGroup.getInfo(lvmvolumegroupID=vg_uuid)
            except ServerError as e:
                raise RuntimeError(str(e))

            self.logger.debug(vginfo)
            vgfree = int(vginfo['vgfree'])
            available_gb = vgfree / pow(2, 30)
            required_size = int(self.environment[
                ohostedcons.StorageEnv.IMAGE_SIZE_GB
            ]) + int(self.environment[
                ohostedcons.StorageEnv.CONF_IMAGE_SIZE_GB
            ])
            if required_size > available_gb:
                raise ohosteddomains.InsufficientSpaceError(
                    _(
                        'Error: the VG on block device has capacity of only '
                        '{available_gb} GiB while '
                        '{required_size} GiB is required for the image'
                    ).format(
                        available_gb=available_gb,
                        required_size=required_size,
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

        heconflib.create_and_prepare_image(
            self.logger,
            cli,
            volFormat,
            preallocate,
            sdUUID,
            spUUID,
            imgUUID,
            volUUID,
            diskType,
            self.environment[ohostedcons.StorageEnv.IMAGE_SIZE_GB],
            self.environment[ohostedcons.StorageEnv.IMAGE_DESC],
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        after=(
            ohostedcons.Stages.ANSIBLE_CREATE_SD,
        ),
        name=ohostedcons.Stages.ANSIBLE_CUSTOMIZE_DISK_SIZE,
        condition=lambda self: (
            self.environment[ohostedcons.CoreEnv.ANSIBLE_DEPLOYMENT]
        ),
    )
    def _closeup_ansible(self):
        self._customize_disk_size(available_gb=self.environment[
            ohostedcons.StorageEnv.BDEVICE_SIZE_GB
        ])

# vim: expandtab tabstop=4 shiftwidth=4
