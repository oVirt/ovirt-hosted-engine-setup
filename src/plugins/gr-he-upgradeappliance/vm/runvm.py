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


"""
VM restart plugin.
"""


import gettext
import os
import re
import tempfile
import time

from otopi import plugin
from otopi import util

from ovirt_hosted_engine_ha.env import config

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import tasks


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    VM configuration plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._temp_vm_conf = None

    def _createvm(self):
        # TODO: parse the file and use JsonRPC via mixins.py
        self.execute(
            args=(
                self.command.get('vdsClient'),
                '-s',
                '0',
                'create',
                self._temp_vm_conf
            ),
            raiseOnError=True
        )
        POWER_MAX_TRIES = 20
        POWER_DELAY = 3
        cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        # Now it's in WaitForLaunch, need to be on powering up
        powering = False
        tries = POWER_MAX_TRIES
        while not powering and tries > 0:
            tries -= 1
            stats = cli.getVmStats(
                self.environment[ohostedcons.VMEnv.VM_UUID]
            )
            self.logger.debug(stats)
            if stats['status']['code'] != 0:
                raise RuntimeError(stats['status']['message'])
            else:
                statsList = stats['items'][0]
                if statsList['status'] in ('Powering up', 'Up'):
                    powering = True
                elif statsList['status'] == 'Down':
                    # VM creation failure
                    tries = 0
                else:
                    time.sleep(POWER_DELAY)
        if not powering:
            raise RuntimeError(
                _(
                    'The VM is not powering up: please check VDSM logs'
                )
            )

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.Upgrade.EXTEND_VOLUME,
            False,
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        self.command.detect('vdsClient')

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        after=(
            ohostedcons.Stages.UPGRADE_BACKUP_DISK_CREATED,
        ),
        name=ohostedcons.Stages.UPGRADE_VM_SHUTDOWN,
    )
    def _misc_shutdown(self):
        self.logger.info(_('Shutting down the current engine VM'))
        cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        res = cli.shutdown(self.environment[ohostedcons.VMEnv.VM_UUID])
        self.logger.debug(res)

        waiter = tasks.VMDownWaiter(self.environment)
        if not waiter.wait():
            # The VM is down but not destroyed
            status = self.environment[
                ohostedcons.VDSMEnv.VDS_CLI
            ].destroy(
                self.environment[ohostedcons.VMEnv.VM_UUID]
            )
            self.logger.debug(status)
            if status['status']['code'] != 0:
                self.logger.error(
                    _(
                        'Cannot destroy the Hosted Engine VM: ' +
                        status['status']['message']
                    )
                )
                raise RuntimeError(status['status']['message'])

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        name=ohostedcons.Stages.UPGRADE_DISK_EXTENDED,
        after=(
            ohostedcons.Stages.UPGRADE_DISK_BACKUP_SAVED,
        ),
        condition=lambda self: self.environment[
            ohostedcons.Upgrade.EXTEND_VOLUME
        ],
    )
    def _misc_extend_disk(self):
        self.logger.info(_('Extending VM disk'))
        cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        res = cli.getStorageDomainInfo(
            storagedomainID=self.environment[ohostedcons.StorageEnv.SD_UUID]
        )
        self.logger.debug(res)
        if 'status' not in res or res['status']['code'] != 0:
            raise RuntimeError(
                _('Failed getting storage domain info: {m}').format(
                    m=res['status']['message'],
                )
            )
        pool_id = res['pool'][0]
        res = cli.extendVolumeSize(
            storagepoolID=pool_id,
            storagedomainID=self.environment[ohostedcons.StorageEnv.SD_UUID],
            imageID=self.environment[ohostedcons.StorageEnv.IMG_UUID],
            volumeID=self.environment[ohostedcons.StorageEnv.VOL_UUID],
            newSize=str(int(self.environment[
                ohostedcons.StorageEnv.IMAGE_SIZE_GB
            ])*1024*1024*1024),
        )
        self.logger.debug(res)
        if 'status' not in res or res['status']['code'] != 0:
            raise RuntimeError(
                _('Failed getting storage domain info: {m}').format(
                    m=res['status']['message'],
                )
            )
        task_id = res['status']['message']
        waiter = tasks.TaskWaiter(self.environment)
        res = waiter.wait(task_id, 1800)
        self.logger.debug(res)
        if res['code'] != 0:
            raise RuntimeError(
                _('Failed extending the hosted-engine disk: {m}').format(
                    m=res['message'],
                )
            )

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        name=ohostedcons.Stages.UPGRADED_APPLIANCE_RUNNING,
    )
    def _boot_new_appliance(self):
        try:
            fd, self._temp_vm_conf = tempfile.mkstemp(
                prefix='appliance',
                suffix='.conf',
            )
            os.close(fd)
            _config = config.Config(logger=self.logger)
            _config.refresh_local_conf_file(
                localcopy_filename=self._temp_vm_conf,
                archive_fname=ohostedcons.FileLocations.HECONFD_VM_CONF,
            )

            vm_conf = open(self._temp_vm_conf)
            lines = vm_conf.readlines()
            self.logger.debug('Original vm.conf: {l}'.format(l=lines))
            vm_conf.close()

            plines = []
            cdrom_attached = False
            for line in lines:
                if 'device:cdrom' in line and 'path:' in line:
                    # attaching cloud-init iso to configure the new appliance
                    sline = re.sub(
                        r'path:[^,]*,',
                        'path:{iso},'.format(
                            iso=self.environment[ohostedcons.VMEnv.CDROM]
                        ),
                        line
                    )
                    plines.append(sline)
                    cdrom_attached = True
                else:
                    plines.append(line)

            if not cdrom_attached:
                raise RuntimeError(_(
                    'Unable to attach cloud-init ISO image'
                ))

            vm_conf = open(self._temp_vm_conf, 'w')
            vm_conf.writelines(plines)
            vm_conf.close()
            self.logger.debug('Patched vm.conf: {l}'.format(l=plines))
        except EnvironmentError as ex:
            self.logger.error(
                _(
                    'Unable to generate the temporary vm.conf file: {msg}'
                ).format(
                    msg=ex.message,
                )
            )
        self._createvm()

    @plugin.event(
        stage=plugin.Stages.STAGE_CLEANUP,
    )
    def _cleanup(self):
        try:
            if (
                self._temp_vm_conf is not None and
                os.path.exists(self._temp_vm_conf)
            ):
                os.unlink(self._temp_vm_conf)
        except EnvironmentError as ex:
            self.logger.error(
                _(
                    'Unable to cleanup the temporary vm.conf file: {msg}'
                ).format(
                    msg=ex.message,
                )
            )


# vim: expandtab tabstop=4 shiftwidth=4
