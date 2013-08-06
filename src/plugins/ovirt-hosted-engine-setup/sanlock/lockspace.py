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
import glob
import os
import sanlock
import stat


from otopi import util
from otopi import plugin


from ovirt_hosted_engine_setup import constants as ohostedcons


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


class VirtUserContext(object):
    """
    Switch to vdsm:kvm user with provided umask
    """

    def __init__(self, environment, umask):
        super(VirtUserContext, self).__init__()
        self.environment = environment
        self._euid = None
        self._egid = None
        self._umask = umask
        self._old_umask = None

    def __enter__(self):
        self._euid = os.geteuid()
        self._egid = os.getegid()
        self._old_umask = os.umask(self._umask)
        os.setegid(self.environment[ohostedcons.VDSMEnv.KVM_GID])
        os.seteuid(self.environment[ohostedcons.VDSMEnv.VDSM_UID])

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.seteuid(self._euid)
        os.setegid(self._egid)
        os.umask(self._umask)


@util.export
class Plugin(plugin.PluginBase):
    """
    sanlock lockspace initialization plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    def _get_metadata_path(self):
        """
        Return path of storage domain holding engine vm
        """
        domains = glob.glob(
            os.path.join(
                ohostedcons.FileLocations.SD_MOUNT_PARENT_DIR,
                '*',
                self.environment[ohostedcons.StorageEnv.SD_UUID],
            )
        )
        if not domains:
            raise RuntimeError(
                _(
                    'Path to storage domain {sd_uuid} not found in {root}'
                ).format(
                    sd_uuid=self.environment[ohostedcons.StorageEnv.SD_UUID],
                    root=ohostedcons.FileLocations.SD_MOUNT_PARENT_DIR,
                )
            )
        return os.path.join(
            domains[0],
            ohostedcons.FileLocations.SD_METADATA_DIR_NAME,
        )

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
        metadatadir = self._get_metadata_path()
        lockspace = self.environment[ohostedcons.SanlockEnv.LOCKSPACE_NAME]
        lease_file = os.path.join(
            metadatadir,
            lockspace + '.lockspace'
        )
        host_id = self.environment[ohostedcons.StorageEnv.HOST_ID]
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
        if not os.path.isdir(metadatadir):
            self.logger.debug('Creating metadata directory')
            with VirtUserContext(
                environment=self.environment,
                umask=stat.S_IWGRP | stat.S_IWOTH,
            ):
                os.mkdir(metadatadir)
        if os.path.exists(lease_file):
            self.logger.info(_('sanlock lockspace already initialized'))
        else:
            self.logger.info(_('Initializing sanlock lockspace'))
            with VirtUserContext(
                environment=self.environment,
                umask=stat.S_IXUSR | stat.S_IXGRP | stat.S_IRWXO,
            ):
                open(lease_file, 'w').close()
            sanlock.write_lockspace(
                lockspace=lockspace,
                path=lease_file,
            )


# vim: expandtab tabstop=4 shiftwidth=4
