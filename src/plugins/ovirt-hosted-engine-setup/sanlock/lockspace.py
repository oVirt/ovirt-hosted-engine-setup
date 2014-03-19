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
sanlock lockspace initialization plugin.
"""

import gettext
import sanlock
import stat
import os

from otopi import util
from otopi import plugin


from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import util as ohostedutil
from ovirt_hosted_engine_ha.lib.storage_backends import FilesystemBackend

_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


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

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        name=ohostedcons.Stages.SANLOCK_INITIALIZED,
        condition=lambda self: not self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
        after=(
            ohostedcons.Stages.STORAGE_AVAILABLE,
        ),
    )
    def _misc(self):
        self.logger.info(_('Verifying sanlock lockspace initialization'))
        self.services.state(
            name=self.environment[
                ohostedcons.SanlockEnv.SANLOCK_SERVICE
            ],
            state=True,
        )

        uuid = self.environment[ohostedcons.StorageEnv.SD_UUID]
        dom_type = self.environment[ohostedcons.StorageEnv.DOMAIN_TYPE]

        # Prepare the Backend interface
        # - this supports nfs, iSCSI and Gluster automatically
        backend = FilesystemBackend(sd_uuid=uuid,
                                    dom_type=dom_type)

        lockspace = self.environment[ohostedcons.SanlockEnv.LOCKSPACE_NAME]
        host_id = self.environment[ohostedcons.StorageEnv.HOST_ID]

        # Compute the size needed to store metadata for all hosts
        # and for the global cluster state
        md_size = (ohostedcons.Const.METADATA_CHUNK_SIZE
                   * (ohostedcons.Const.MAX_HOST_ID + 1))

        with ohostedutil.VirtUserContext(
                environment=self.environment,
                # umask 007
                umask=stat.S_IRWXO,
                ):

            # Create storage for he metadata and sanlock lockspace
            # 1MB is good for 2000 clients when the block size is 512B
            created = backend.create({
                lockspace + '.lockspace': 1024*1024*backend.blocksize/512,
                lockspace + '.metadata': md_size
            })

            # Get the path to sanlock lockspace area
            lease_file, offset = backend.filename(lockspace + '.lockspace')

            # Update permissions on the lockspace directory to 0755
            os.chmod(os.path.dirname(lease_file),
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

# vim: expandtab tabstop=4 shiftwidth=4
