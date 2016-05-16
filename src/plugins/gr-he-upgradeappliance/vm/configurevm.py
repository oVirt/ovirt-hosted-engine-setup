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
VM configuration plugin.
"""


import gettext
import hashlib
import os
import tarfile


from otopi import plugin
from otopi import util


from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import vm_status


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    VM configuration plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    def _validate_backup_file(self, backup_file_path):
        self.logger.info(
            _("Validating backup file '{backup_file_path}'").format(
                backup_file_path=backup_file_path,
            )
        )
        if not os.path.isfile(backup_file_path):
            self.logger.error(
                _("Unable to open '{path}'").format(
                    path=backup_file_path
                )
            )
            return False
        try:
            tar = tarfile.open(backup_file_path, 'r:*')
        except tarfile.ReadError as ex:
            self.logger.error(
                _("'{path}' is not a tar.gz archive: {m}").format(
                    path=backup_file_path,
                    m=ex.message,
                )
            )
            return False
        files = tar.getnames()
        self.logger.debug('backup contents: {files}'.format(files=files))
        if (
            './files' not in files or
            './version' not in files or
            './md5sum' not in files or
            './db/engine_backup.db' not in files or
            './config' not in files
        ):
            self.logger.error(
                _("'{path}' is not a complete backup").format(
                    path=backup_file_path
                )
            )
            tar.close()
            return False
        if './db/dwh_backup.db' in files:
            self.environment[ohostedcons.Upgrade.RESTORE_DWH] = True
            self.logger.info(_(
                'The provided file contains also a DWH DB backup: '
                'it will be restored as well'
            ))
        if './db/reports_backup.db' in files:
            self.environment[ohostedcons.Upgrade.RESTORE_REPORTS] = True
            self.logger.info(_(
                'The provided file contains also a Reports DB backup: '
                'it will be restored as well'
            ))

        md5_f = tar.extractfile(tar.getmember('./md5sum'))
        md5_lines = md5_f.readlines()
        md5_list = [(x[0], './'+x[1].replace('\n', '')) for x in (
            x.split('  ')
            for x in md5_lines
        )]
        self.logger.debug('md5_list: {ml}'.format(ml=md5_list))
        for cfile in md5_list:
            self.logger.debug('checking {f}'.format(f=cfile[1]))
            fo = tar.extractfile(tar.getmember(cfile[1]))
            hash_md5 = hashlib.md5()
            for chunk in iter(lambda: fo.read(4096), b""):
                hash_md5.update(chunk)
            calc_md5 = hash_md5.hexdigest()
            self.logger.debug(
                'calculated {f} - stored {s}'.format(
                    f=calc_md5,
                    s=cfile[0],
                )
            )
            if calc_md5 != cfile[0]:
                self.logger.error(
                    _("'{path}' is corrupted").format(
                        path=backup_file_path
                    )
                )
                tar.close()
                return False
        self.logger.info(
            _("'{backup_file_path}' is a sane backup file").format(
                backup_file_path=backup_file_path
            )
        )
        tar.close()
        return True

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.VMEnv.BOOT,
            'disk',
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.BRIDGE_NAME,
            None,
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.GATEWAY,
            None,
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.HOST_NAME,
            None
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN,
            None,
        )
        self.environment.setdefault(
            ohostedcons.EngineEnv.ADMIN_PASSWORD,
            None
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.VM_UUID,
            None,
        )
        self.environment.setdefault(
            ohostedcons.Upgrade.RESTORE_DWH,
            False,
        )
        self.environment.setdefault(
            ohostedcons.Upgrade.RESTORE_REPORTS,
            False,
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_LATE_SETUP,
        after=(
            ohostedcons.Stages.VDSMD_CONF_LOADED,
            ohostedcons.Stages.VDSM_LIBVIRT_CONFIGURED,
        ),
        name=ohostedcons.Stages.CHECK_MAINTENANCE_MODE,
    )
    def _late_setup(self):
        self.logger.info('Checking maintenance mode')
        vmstatus = vm_status.VmStatus()
        status = vmstatus.get_status()
        self.logger.debug('hosted-engine-status: {s}'.format(s=status))
        if not status['global_maintenance']:
            self.logger.error(_(
                'Please enable global maintenance mode before upgrading'
            ))
            raise RuntimeError(_('Not in global maintenance mode'))
        if status['engine_vm_up']:
            self.logger.error(
                _(
                    'The engine VM is runnnig on {host}, '
                    'please shut it down it before upgrading'
                ).format(
                    host=status['engine_vm_host']
                )
            )
            raise RuntimeError(_('Engine VM is running'))

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.CONFIG_OVF_IMPORT,
        ),
        name=ohostedcons.Stages.CONFIG_BACKUP_FILE,
    )
    def _customization(self):
        valid = False
        interactive = self.environment[ohostedcons.Upgrade.BACKUP_FILE] is None
        while not valid:
            if interactive:
                backup_file_path = self.dialog.queryString(
                    name='OVEHOSTED_CONFIGURATION_BACKUPFILE',
                    note=_(
                        'Please specify path to engine backup archive '
                        'you would like to restore on the new appliance: '
                    ),
                    prompt=True,
                    caseSensitive=True,
                )
            valid = self._validate_backup_file(backup_file_path)
            if valid and interactive:
                self.environment[
                    ohostedcons.Upgrade.BACKUP_FILE
                ] = backup_file_path
            if not valid and not interactive:
                raise RuntimeError(_('Invalid backup file'))

# vim: expandtab tabstop=4 shiftwidth=4
