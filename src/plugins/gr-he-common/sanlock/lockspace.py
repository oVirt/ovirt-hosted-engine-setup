#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2013-2014 Red Hat, Inc.
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
import os
import sanlock
import stat

from otopi import plugin
from otopi import util

from ovirt_hosted_engine_ha.lib import storage_backends

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import util as ohostedutil


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
        self.environment.setdefault(
            ohostedcons.Upgrade.UPGRADE_CREATE_LM_VOLUMES,
            False,
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        name=ohostedcons.Stages.SANLOCK_INITIALIZED,
        condition=lambda self: (
            (
                not self.environment[
                    ohostedcons.CoreEnv.UPGRADING_APPLIANCE
                ] or
                (
                    self.environment[
                        ohostedcons.CoreEnv.UPGRADING_APPLIANCE
                    ] and
                    self.environment[
                        ohostedcons.Upgrade.UPGRADE_CREATE_LM_VOLUMES
                    ]
                )
            ) and
            not self.environment[ohostedcons.CoreEnv.ROLLBACK_UPGRADE]
        ),
        after=(
            ohostedcons.Stages.STORAGE_AVAILABLE,
        ),
    )
    def _misc(self):
        """
        Here the storage pool is connected and activated.
        Pass needed configuration to HA VdsmBackend for initializing
        the metadata and lockspace volumes.
        """
        self.logger.info(_('Verifying sanlock lockspace initialization'))
        self.services.state(
            name=self.environment[
                ohostedcons.SanlockEnv.SANLOCK_SERVICE
            ],
            state=True,
        )

        dom_type = self.environment[ohostedcons.StorageEnv.DOMAIN_TYPE]
        lockspace = self.environment[ohostedcons.SanlockEnv.LOCKSPACE_NAME]
        host_id = self.environment[ohostedcons.StorageEnv.HOST_ID]

        sp_uuid = self.environment[ohostedcons.StorageEnv.SP_UUID]
        if self.environment[
            ohostedcons.Upgrade.UPGRADE_CREATE_LM_VOLUMES
        ]:
            cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
            res = cli.getStorageDomainInfo(
                storagedomainID=self.environment[
                    ohostedcons.StorageEnv.SD_UUID
                ]
            )
            self.logger.debug(res)
            if 'status' not in res or res['status']['code'] != 0:
                raise RuntimeError(
                    _('Failed getting storage domain info: {m}').format(
                        m=res['status']['message'],
                    )
                )
            sp_uuid = res['pool'][0]

        # Prepare the Backend interface
        # - this supports nfs, iSCSI and Gluster automatically
        activate_devices = {
            lockspace + '.lockspace': None,  # created by backend
            lockspace + '.metadata': None,   # created by backend
        }
        backend = storage_backends.VdsmBackend(
            sd_uuid=self.environment[ohostedcons.StorageEnv.SD_UUID],
            sp_uuid=sp_uuid,
            dom_type=dom_type,
            **activate_devices
        )
        backend.set_external_logger(self.logger)

        # Compute the size needed to store metadata for all hosts
        # and for the global cluster state
        md_size = (
            ohostedcons.Const.METADATA_CHUNK_SIZE * (
                ohostedcons.Const.MAX_HOST_ID + 1
            )
        )

        with ohostedutil.VirtUserContext(
            self.environment,
            # umask 007
            umask=stat.S_IRWXO
        ):
            # Create storage for he metadata and sanlock lockspace
            # 1MB is good for 2000 clients when the block size is 512B
            created = backend.create({
                lockspace + '.lockspace': 1024*1024*backend.blocksize/512,
                lockspace + '.metadata': md_size,
            })

            # Get UUIDs of the storage
            metadata_device = backend.get_device(lockspace + '.metadata')
            self.environment[
                ohostedcons.StorageEnv.METADATA_VOLUME_UUID
            ] = metadata_device.volume_uuid
            self.environment[
                ohostedcons.StorageEnv.METADATA_IMAGE_UUID
            ] = metadata_device.image_uuid

            lockspace_device = backend.get_device(lockspace + '.lockspace')
            self.environment[
                ohostedcons.StorageEnv.LOCKSPACE_VOLUME_UUID
            ] = lockspace_device.volume_uuid
            self.environment[
                ohostedcons.StorageEnv.LOCKSPACE_IMAGE_UUID
            ] = lockspace_device.image_uuid

            # for lv_based storage (like iscsi) creates symlinks in /rhev/..
            # for nfs does nothing (the real files are already in /rhev/..)
            backend.connect(initialize=False)

            # Get the path to sanlock lockspace area
            lease_file, offset = backend.filename(lockspace + '.lockspace')

            agent_data_dir = os.path.dirname(lease_file)

            stat_info = os.stat(agent_data_dir)
            # only change it when it's not already owned by vdsm,
            # because on NFS we don't need the chown and it won't work
            if stat_info.st_uid != self.environment[
                ohostedcons.VDSMEnv.VDSM_UID
            ]:
                os.chown(
                    agent_data_dir,
                    self.environment[ohostedcons.VDSMEnv.VDSM_UID],
                    self.environment[ohostedcons.VDSMEnv.KVM_GID]
                )
            # Update permissions on the lockspace directory to 0755
            os.chmod(agent_data_dir,
                     stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)

            self.logger.debug(
                (
                    'Ensuring lease for lockspace {lockspace}, '
                    'host id {host_id} '
                    'is acquired (file: {lease_file})'
                ).format(
                    lockspace=lockspace,
                    host_id=host_id,
                    lease_file=lease_file,
                )
            )

        # Reinitialize the sanlock lockspace
        # if it was newly created or updated
        if (lockspace + '.lockspace') in created:
            sanlock.write_lockspace(
                lockspace=lockspace,
                path=lease_file,
                offset=offset
            )
        backend.disconnect()


# vim: expandtab tabstop=4 shiftwidth=4
