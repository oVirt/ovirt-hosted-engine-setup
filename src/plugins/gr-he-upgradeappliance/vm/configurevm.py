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


import configparser
import gettext
import hashlib
import lzma
import os
import shutil
import tarfile
import tempfile


from io import StringIO

from otopi import plugin
from otopi import util

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import engineapi


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    VM configuration plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._tmp_files_directory_name = None

    def _validate_authz(self, files_tar):
        self.logger.info(_("Validating authentication plugins"))
        authz_ext = set([])
        flist = files_tar.getmembers()
        self.logger.debug('Content:')
        self.logger.debug([f.name for f in flist])
        authplist = [
            f for f in flist if f.isfile() and
            'etc/ovirt-engine/extensions.d' in f.name and
            f.name.endswith('.properties')
        ]
        self.logger.debug('Configured plugins:')
        self.logger.debug([ap.name for ap in authplist])
        for authp in authplist:
            authp_file = files_tar.extractfile(authp)
            auth_f_str = '[section]\n' + authp_file.read()
            auth_fp = StringIO(unicode(auth_f_str))
            config = configparser.RawConfigParser()
            try:
                config.readfp(auth_fp)
            except configparser.Error as ex:
                msg = _(
                    'The extension configuration file \'{authp}\' inside '
                    'the backup seams invalid, '
                    'please check its content on the engine VM and fix: {ex}'
                ).format(
                    authp=authp,
                    ex=ex
                )
                self.logger.error(msg)
                return False
            if (
                config.has_section('section') and
                config.has_option(
                    'section',
                    'ovirt.engine.extension.provides'
                ) and
                config.has_option(
                    'section',
                    'ovirt.engine.extension.name'
                )
            ):
                provides = config.get(
                    'section',
                    'ovirt.engine.extension.provides'
                )
                name = config.get(
                    'section',
                    'ovirt.engine.extension.name'
                )
                self.logger.debug(
                    'Extension {n} provides {p}'.format(
                        n=name,
                        p=provides
                    )
                )
                if provides == 'org.ovirt.engine.api.extensions.aaa.Authz':
                    authz_ext.add(name)
            else:
                msg = _(
                    'The extension configuration file \'{authp}\' inside '
                    'the backup seams invalid, '
                    'please check its content on the engine VM and fix.'
                ).format(
                    authp=authp,
                )
                self.logger.error(msg)
                return False
        self.logger.debug(
            'Authz extensions configured on fs: {l}'.format(l=authz_ext)
        )
        engine_api = engineapi.get_engine_api(self)
        eng_authz_domains = set([
            d.get_name() for d in engine_api.domains.list()
        ])
        self.logger.debug(
            'Authz domains configured on the engine: {l}'.format(
                l=eng_authz_domains
            )
        )
        if eng_authz_domains > authz_ext:
            to_be_fixed = eng_authz_domains - authz_ext
            msg = _(
                '{tbf}: such AAA domains are still configured in a '
                'deprecated way that is not compatible with the current '
                'release; please upgrade them to ovirt-engine-extension '
                'mechanism before proceeding.'
            ).format(
                tbf=[d for d in to_be_fixed],
            )
            self.logger.error(msg)
            raise RuntimeError('Unsupported AAA mechanism')
        return True

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

        self._tmp_files_directory_name = tempfile.mkdtemp()

        tar.extract(
            tar.getmember('./files'),
            path=self._tmp_files_directory_name
        )

        # tarfile on Python 2 doesn't natively support xz compression
        # which is the engine-backup default
        try:
            uncompressed_file = lzma.LZMAFile(
                os.path.join(
                    self._tmp_files_directory_name,
                    './files'
                )
            )
            try:
                files_tar = tarfile.open(
                    fileobj=uncompressed_file,
                    mode='r:'
                )
            except tarfile.ReadError as ex:
                self.logger.error(
                    _("'{path}' is not a valid archive: {m}").format(
                        path='./files',
                        m=ex.message,
                    )
                )
                tar.close()
                return False
        except lzma.error:
            self.logger.debug('Not lzma')
            try:
                files_tar = tarfile.open(
                    fileobj=tar.extractfile(tar.getmember('./files')),
                    mode='r:*'
                )
            except tarfile.ReadError as ex:
                self.logger.error(
                    _(
                        "'{path}' is not a valid archive: {m} - please try "
                        "recreating the backup with "
                        "'--files-compressor=gzip' option."
                    ).format(
                        path='./files',
                        m=ex.message,
                    )
                )
                tar.close()
                return False

        auth_valid = self._validate_authz(files_tar)
        files_tar.close()
        if not auth_valid:
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
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.CONFIG_OVF_IMPORT,
            ohostedcons.Stages.UPGRADE_CHECK_UPGRADE_VERSIONS,
        ),
        name=ohostedcons.Stages.CONFIG_BACKUP_FILE,
    )
    def _customization(self):
        valid = False
        interactive = self.environment[ohostedcons.Upgrade.BACKUP_FILE] is None
        backup_file_path = self.environment[ohostedcons.Upgrade.BACKUP_FILE]
        while not valid:
            # TODO: do it automatically
            self.dialog.note(_(
                'Please take a backup of the current engine running this '
                'command on the engine VM:\n'
                ' engine-backup --mode=backup --archive-compressor=gzip '
                '--file=engine_backup.tar.gz --log=engine_backup.log\n'
                'Then copy the backup archive to this host and input here '
                'its path when ready.\n'
            ))
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
            backup_file_path = self.resolveFile(backup_file_path)
            valid = self._validate_backup_file(backup_file_path)
            if valid:
                self.environment[
                    ohostedcons.Upgrade.BACKUP_FILE
                ] = backup_file_path
                if not self.environment[ohostedcons.Upgrade.DST_BACKUP_FILE]:
                    self.environment[
                        ohostedcons.Upgrade.DST_BACKUP_FILE
                    ] = os.path.join(
                        '/root/',
                        os.path.basename(backup_file_path)
                    )
            if not valid and not interactive:
                raise RuntimeError(_('Invalid backup file'))

    @plugin.event(
        stage=plugin.Stages.STAGE_CLEANUP,
    )
    def _cleanup(self):
        if self._tmp_files_directory_name is not None:
            shutil.rmtree(self._tmp_files_directory_name)

# vim: expandtab tabstop=4 shiftwidth=4
