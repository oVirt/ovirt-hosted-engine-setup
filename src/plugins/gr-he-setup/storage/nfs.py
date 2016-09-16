#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2014-2015 Red Hat, Inc.
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
NFS / GlusterFS storage plugin.
"""

import gettext
import os
import tempfile
import time
import xml.dom.minidom

from otopi import plugin
from otopi import util

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import domains as ohosteddomains


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    NFS / GlusterFS storage plugin.
    """

    UMOUNT_TRIES = 10

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._checker = ohosteddomains.DomainChecker()

    def _mount(self, path, connection, domain_type):
        fstype = ''
        opts = []

        if domain_type == ohostedcons.DomainTypes.NFS3:
            fstype = ohostedcons.FileSystemTypes.NFS
            opts.append('vers=3')
        elif domain_type == ohostedcons.DomainTypes.NFS4:
            fstype = ohostedcons.FileSystemTypes.NFS
            opts.append('vers=4')
        elif domain_type == ohostedcons.DomainTypes.GLUSTERFS:
            fstype = ohostedcons.FileSystemTypes.GLUSTERFS

        if fstype == ohostedcons.FileSystemTypes.NFS:
            opts.append('retry=1')

        mount_cmd = (
            self.command.get('mount'),
            '-t%s' % fstype,
        )

        if opts:
            mount_cmd += (
                '-o%s' % ','.join(opts),
            )

        mount_cmd += (
            connection,
            path,
        )

        rc, _stdout, stderr = self.execute(
            mount_cmd,
            raiseOnError=False,
            env={
                'LC_ALL': 'C',
            },

        )
        error = '\n'.join(stderr)
        if rc != 0:
            self.logger.error(
                _(
                    'Error while mounting specified storage path: {error}'
                ).format(
                    error=error,
                )
            )
            raise RuntimeError(error)

    def _umount(self, path):
        rc = -1
        tries = self.UMOUNT_TRIES
        while tries > 0:
            rc, _stdout, _stderr = self.execute(
                (
                    self.command.get('umount'),
                    path
                ),
                raiseOnError=False,
                env={
                    'LC_ALL': 'C',
                },
            )
            if rc == 0:
                tries = -1
            else:
                tries -= 1
                time.sleep(1)
                # rc, stdout and stderr are automatically logged as debug
                self.execute(
                    (
                        self.command.get('lsof'),
                        '+D%s' % path,
                        '-xfl'
                    ),
                    raiseOnError=False,
                    env={
                        'LC_ALL': 'C',
                    },
                )
        return rc

    def _check_domain_rights(self, path):
        rc, _stdout, _stderr = self.execute(
            (
                self.command.get('sudo'),
                '-u', 'vdsm',
                '-g', 'kvm',
                'test',
                '-r', path,
                '-a',
                '-w', path,
                '-a',
                '-x', path,
            ),
            raiseOnError=False
        )
        if rc != 0:
            raise RuntimeError(
                _(
                    'permission settings on the specified storage do not '
                    'allow access to the storage to vdsm user and kvm group. '
                    'Verify permission settings on the specified storage '
                    'or specify another location'
                )
            )

    def _check_volume_properties(self, connection):
        server, volume = connection.split(':')
        if volume[0] == '/':
            volume = volume[1:]
        glustercmd = self.command.get('gluster')
        rc, stdout, stderr = self.execute(
            args=(
                glustercmd,
                '--mode=script',
                '--xml',
                'volume',
                'info',
                volume,
                '--remote-host=%s' % server,
            ),
            raiseOnError=True
        )
        if rc != 0:
            self.logger.error(_('Failed to retrieve Gluster Volume info'))
            raise RuntimeError(
                'Failed to retrieve Gluster Volume info: ' + str(stdout)
            )
        self.logger.debug('Gluster Volume info XML output: ' + str(stdout))
        dom = xml.dom.minidom.parseString(''.join(stdout))
        cliOutput = dom.getElementsByTagName('cliOutput')[0]
        opRet = (
            cliOutput.getElementsByTagName('opRet')[0]
        ).firstChild.nodeValue
        opErrno = (
            cliOutput.getElementsByTagName('opErrno')[0]
        ).firstChild.nodeValue
        opErrstrElement = cliOutput.getElementsByTagName('opErrstr')[0]
        opErrstr = ' '.join(
            t.nodeValue for t in opErrstrElement.childNodes
            if t.nodeType == t.TEXT_NODE
        )

        if opRet != '0':
            self.logger.error(_('Failed to retrieve Gluster Volume info'))
            raise RuntimeError(
                'Failed to retrieve Gluster Volume info '
                '[{code}]: {error}'.format(
                    code=opErrno,
                    error=opErrstr,
                )
            )
        volInfo = cliOutput.getElementsByTagName('volInfo')[0]
        volumes = volInfo.getElementsByTagName('volumes')[0]
        volCount = (
            volumes.getElementsByTagName('count')[0]
        ).firstChild.nodeValue
        if volCount != '1':
            raise RuntimeError(
                _('GlusterFS Volume {volume} does not exist!').format(
                    volume=volume,
                )
            )
        volume = volumes.getElementsByTagName('volume')[0]
        replicaCount = (
            volume.getElementsByTagName('replicaCount')[0]
        ).firstChild.nodeValue
        if replicaCount != '3':
            raise RuntimeError(
                _(
                    'GlusterFS Volume is not using replica 3'
                )
            )
        self.logger.info(_('GlusterFS replica 3 Volume detected'))
        host_list = []
        for brickE in volume.getElementsByTagName('brick'):
            host_list.append(
                (brickE.getElementsByTagName('hostUuid')[0])
                .firstChild.nodeValue
            )
        if len(set(host_list)) < 3:
            self.logger.warning(_(
                'Three distinct hosts are required for '
                'safe and reliable operations'
            ))
        status = (
            volume.getElementsByTagName('status')[0]
        ).firstChild.nodeValue
        statusStr = (
            volume.getElementsByTagName('statusStr')[0]
        ).firstChild.nodeValue
        if status != '1':
            raise RuntimeError(
                _(
                    "GlusterFS Volume is '{statusStr}', "
                    "please ensure that it's started"
                ).format(
                    statusStr=statusStr,
                )
            )

    def _fix_path_syntax(self):
        path = self.environment[
            ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
        ]
        if (
            path and
            len(path) > 2 and
            path[-1] == '/' and
            path[-2] == ':'
        ):
            raise RuntimeError(
                _(
                    "'server:/' is not an acceptable export path, "
                    "please use at least one subdirectory"
                )
            )
        path = os.path.normpath(
            self.environment[
                ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
            ]
        )
        if path != self.environment[
            ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
        ]:
            self.logger.warning(
                _(
                    "Fixing path syntax: "
                    "replacing '{original}' with '{fixed}'"
                ).format(
                    original=self.environment[
                        ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
                    ],
                    fixed=path,
                )
            )
            self.environment[
                ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
            ] = path

    def _validateDomain(self, connection, domain_type, check_space):
        if self.environment[
            ohostedcons.StorageEnv.DOMAIN_TYPE
        ] == ohostedcons.DomainTypes.GLUSTERFS:
            self._check_volume_properties(connection)
        path = tempfile.mkdtemp()
        try:
            self._mount(path, connection, domain_type)
            self._checker.check_valid_path(path)
            self._check_domain_rights(path)
            self._checker.check_base_writable(path)
            if check_space:
                self._checker.check_available_space(
                    path,
                    ohostedcons.Const.MINIMUM_SPACE_STORAGEDOMAIN_MB
                )
        finally:
            if self._umount(path) == 0:
                os.rmdir(path)
            else:
                self.logger.warning(
                    _('Cannot unmount {path}').format(
                        path=path,
                    )
                )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        self.command.detect('lsof')
        self.command.detect('sudo')
        self.command.detect('mount')
        self.command.detect('umount')
        self.command.detect('gluster')

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.CONFIG_STORAGE_NFS,
        after=(
            ohostedcons.Stages.CONFIG_STORAGE_EARLY,
        ),
        before=(
            ohostedcons.Stages.CONFIG_STORAGE_LATE,
        ),
        condition=lambda self: (
            self.environment[ohostedcons.StorageEnv.DOMAIN_TYPE] in (
                ohostedcons.DomainTypes.GLUSTERFS,
                ohostedcons.DomainTypes.NFS3,
                ohostedcons.DomainTypes.NFS4,
            )
        ),
    )
    def _customization(self):
        if self.environment[
            ohostedcons.StorageEnv.DOMAIN_TYPE
        ] == ohostedcons.DomainTypes.GLUSTERFS:
            self.logger.info(
                _(
                    'Please note that Replica 3 support is required for '
                    'the shared storage.'
                )
            )
        interactive = self.environment[
            ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
        ] is None
        validDomain = False
        while not validDomain:
            if interactive:
                self.environment[
                    ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
                ] = self.dialog.queryString(
                    name='OVEHOSTED_STORAGE_DOMAIN_CONNECTION',
                    note=_(
                        'Please specify the full shared storage '
                        'connection path to use (example: host:/path): '
                    ),
                    prompt=True,
                    caseSensitive=True,
                )
            try:
                self._fix_path_syntax()
                self._validateDomain(
                    connection=self.environment[
                        ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
                    ],
                    domain_type=self.environment[
                        ohostedcons.StorageEnv.DOMAIN_TYPE
                    ],
                    check_space=False,
                )
                validDomain = True
            except (ValueError, RuntimeError) as e:
                if interactive:
                    self.logger.debug('exception', exc_info=True)
                    self.logger.error(
                        _(
                            'Cannot access storage connection '
                            '{connection}: {error}'
                        ).format(
                            connection=self.environment[
                                ohostedcons.StorageEnv.
                                STORAGE_DOMAIN_CONNECTION
                            ],
                            error=e,
                        )
                    )
                else:
                    raise e
            except ohosteddomains.InsufficientSpaceError as e:
                self.logger.debug('exception', exc_info=True)
                self.logger.debug(e)
                min_requirement = '%0.2f' % (
                    ohostedcons.Const.MINIMUM_SPACE_STORAGEDOMAIN_MB / 1024.0
                )
                if interactive:
                    self.logger.error(
                        _(
                            'Storage domain for self hosted engine '
                            'is too small: '
                            'you should have at least {min_r} GB free'.format(
                                min_r=min_requirement,
                            )
                        )
                    )
                else:
                    raise RuntimeError(
                        _(
                            'Storage domain for self hosted engine '
                            'is too small: '
                            'you should have at least {min_r} GB free'.format(
                                min_r=min_requirement,
                            )
                        )
                    )

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.CONFIG_STORAGE_LATE,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_STORAGE,
        ),
        condition=lambda self: (
            not self.environment[
                ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
            ] and
            self.environment[ohostedcons.StorageEnv.DOMAIN_TYPE] in (
                ohostedcons.DomainTypes.GLUSTERFS,
                ohostedcons.DomainTypes.NFS3,
                ohostedcons.DomainTypes.NFS4,
            )
        ),
    )
    def _late_customization(self):
        # On first host we need to check if we have enough space too.
        # We must skip this check on additional hosts because the space is
        # already filled with the Hosted Engine VM image.
        # Sadly we can't go back to previous customization stage so here
        # we can only fail the setup.
        try:
            self._validateDomain(
                connection=self.environment[
                    ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
                ],
                domain_type=self.environment[
                    ohostedcons.StorageEnv.DOMAIN_TYPE
                ],
                check_space=True,
            )
        except ohosteddomains.InsufficientSpaceError as e:
            self.logger.debug('exception', exc_info=True)
            self.logger.debug(e)
            min_requirement = '%0.2f' % (
                ohostedcons.Const.MINIMUM_SPACE_STORAGEDOMAIN_MB / 1024.0
            )
            raise RuntimeError(
                _(
                    'Storage domain for self hosted engine '
                    'is too small: '
                    'you should have at least {min_r} GB free'.format(
                        min_r=min_requirement,
                    )
                )
            )


# vim: expandtab tabstop=4 shiftwidth=4
