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
Local storage domain plugin.
"""

import os
import uuid
import gettext
import socket
import tempfile
import time


from otopi import util
from otopi import plugin


from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import domains as ohosteddomains
from ovirt_hosted_engine_setup import tasks


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    Local storage plugin.
    """

    NFS_DOMAIN = 1
    GLUSTERFS_DOMAIN = 7

    DATA_DOMAIN = 1
    MAX_RETRY = 10

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._checker = ohosteddomains.DomainChecker()
        self.vdsClient = util.loadModule(
            path=ohostedcons.FileLocations.VDS_CLIENT_DIR,
            name='vdsClient'
        )
        self.serv = None
        self.waiter = None
        self.storageType = None

    def _mount(self, path, connection):
        self.execute(
            (
                self.command.get('mount'),
                connection,
                path
            ),
            raiseOnError=True
        )

    def _umount(self, path):
        self.execute(
            (
                self.command.get('umount'),
                path
            ),
            raiseOnError=False
        )

    def _validateDomain(self, connection):
        path = tempfile.mkdtemp()
        try:
            self._mount(path, connection)
            self._checker.check_valid_path(path)
            self._checker.check_base_writable(path)
            self._checker.check_available_space(
                path,
                ohostedcons.Const.MINIMUM_SPACE_STORAGEDOMAIN_MB
            )
        finally:
            self._umount(path)
            os.rmdir(path)

    def _connectStorageServer(self):
        self.logger.debug('connectStorageServer')
        spUUID = self.vdsClient.BLANK_UUID
        conList = (
            "connection={connection},"
            "iqn=,"
            "portal=,"
            "user=kvm,"
            "password=,"
            "id={connectionUUID},"
            "port="
        ).format(
            connection=self.environment[
                ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
            ],
            connectionUUID=self.environment[
                ohostedcons.StorageEnv.CONNECTION_UUID
            ],
        )
        self.serv.connectStorageServer(args=[
            self.storageType,
            spUUID,
            conList
        ])

    def _createStorageDomain(self):
        self.logger.debug('createStorageDomain')
        sdUUID = self.environment[ohostedcons.StorageEnv.SD_UUID]
        domainName = self.environment[
            ohostedcons.StorageEnv.STORAGE_DOMAIN_NAME
        ]
        path = self.environment[
            ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
        ]
        domainType = self.DATA_DOMAIN
        version = 3
        status, message = self.serv.createStorageDomain(args=[
            self.storageType,
            sdUUID,
            domainName,
            path,
            domainType,
            version
        ])
        if status != 0:
            raise RuntimeError(message)
        self.logger.debug(self.serv.s.repoStats())
        self.logger.debug(
            self.serv.s.getStorageDomainStats(sdUUID)
        )

    def _createStoragePool(self):
        self.logger.debug('createStoragePool')
        poolType = -1
        spUUID = self.environment[ohostedcons.StorageEnv.SP_UUID]
        sdUUID = self.environment[ohostedcons.StorageEnv.SD_UUID]
        poolName = self.environment[
            ohostedcons.StorageEnv.STORAGE_DATACENTER_NAME
        ]
        masterDom = sdUUID
        domList = sdUUID  # str: domain,domain,...
        mVer = 1
        status, message = self.serv.createStoragePool(args=[
            poolType,
            spUUID,
            poolName,
            masterDom,
            domList,
            mVer
        ])
        if status != 0:
            raise RuntimeError(message)

    def _connectStoragePool(self):
        self.logger.debug('connectStoragePool')
        spUUID = self.environment[ohostedcons.StorageEnv.SP_UUID]
        sdUUID = self.environment[ohostedcons.StorageEnv.SD_UUID]
        ID = 1
        scsi_key = spUUID
        master = sdUUID
        master_ver = 1
        status, message = self.serv.connectStoragePool(args=[
            spUUID,
            ID,
            scsi_key,
            master,
            master_ver
        ])
        if status != 0:
            raise RuntimeError(message)

    def _spmStart(self):
        self.logger.debug('spmStart')
        spUUID = self.environment[ohostedcons.StorageEnv.SP_UUID]
        prevID = -1
        prevLVER = -1
        recoveryMode = -1
        scsiFencing = 'false'
        maxHostID = 250
        version = 3
        status, status_uuid = self.serv.spmStart(args=[
            spUUID,
            prevID,
            prevLVER,
            recoveryMode,
            scsiFencing,
            maxHostID,
            version
        ])
        if status != 0:
            raise RuntimeError(status_uuid)
        self.logger.debug(status_uuid)

    def _activateStorageDomain(self):
        self.logger.debug('activateStorageDomain')
        sdUUID = self.environment[ohostedcons.StorageEnv.SD_UUID]
        spUUID = self.environment[ohostedcons.StorageEnv.SP_UUID]
        status, message = self.serv.activateStorageDomain(args=[
            sdUUID,
            spUUID
        ])
        if status != 0:
            raise RuntimeError(message)
        self.waiter.wait()
        self.logger.debug(self.serv.s.getSpmStatus(spUUID))
        info = self.serv.s.getStoragePoolInfo(spUUID)
        self.logger.debug(info)
        self.logger.debug(self.serv.s.repoStats())

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.STORAGE_DOMAIN_NAME,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.STORAGE_DATACENTER_NAME,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.CONNECTION_UUID,
            str(uuid.uuid4())
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.SD_UUID,
            str(uuid.uuid4())
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.SP_UUID,
            str(uuid.uuid4())
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.DOMAIN_TYPE,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        self.command.detect('mount')
        self.command.detect('umount')

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.CONFIG_STORAGE,
        priority=plugin.Stages.PRIORITY_FIRST,
    )
    def _customization(self):
        #TODO: ask for domain type: nfs or glusterfs (use lower case in env)
        interactive = (
            self.environment[
                ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
            ] is None or
            self.environment[
                ohostedcons.StorageEnv.DOMAIN_TYPE
            ] is None
        )

        validDomain = False
        while not validDomain:
            try:
                if interactive:
                    self.environment[
                        ohostedcons.StorageEnv.DOMAIN_TYPE
                    ] = self.dialog.queryString(
                        name='OVEHOSTED_STORAGE_DOMAIN_TYPE',
                        note=_(
                            'Please specify the storage '
                            'you would like to use (@VALUES@): '
                        ),
                        prompt=True,
                        caseSensitive=False,
                        validValues=[
                            ('glusterfs'),
                            ('nfs'),
                        ]
                    )

                    self.environment[
                        ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
                    ] = self.dialog.queryString(
                        name='OVEHOSTED_STORAGE_DOMAIN_CONNECTION',
                        note=_(
                            'Please specify the full shared storage '
                            'connection path to use: '
                        ),
                        prompt=True,
                        caseSensitive=True,
                    )

                self._validateDomain(
                    connection=self.environment[
                        ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
                    ]
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
                    raise

        if self.environment[
            ohostedcons.StorageEnv.STORAGE_DOMAIN_NAME
        ] is None:
            self.environment[
                ohostedcons.StorageEnv.STORAGE_DOMAIN_NAME
            ] = self.dialog.queryString(
                name='OVEHOSTED_STORAGE_DOMAIN_NAME',
                note=_(
                    'Please provide storage domain name [@DEFAULT@]: '
                ),
                prompt=True,
                caseSensitive=True,
                default=ohostedcons.Defaults.DEFAULT_STORAGE_DOMAIN_NAME,
            )

        if self.environment[
            ohostedcons.StorageEnv.STORAGE_DATACENTER_NAME
        ] is None:
            self.environment[
                ohostedcons.StorageEnv.STORAGE_DATACENTER_NAME
            ] = self.dialog.queryString(
                name='OVEHOSTED_STORAGE_DATACENTER_NAME',
                note=_('Local storage datacenter name [@DEFAULT@]: '),
                prompt=True,
                caseSensitive=True,
                default=ohostedcons.Defaults.DEFAULT_STORAGE_DATACENTER_NAME,
            )

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        after=[
            ohostedcons.Stages.VDSMD_START,
        ],
        name=ohostedcons.Stages.STORAGE_AVAILABLE,
    )
    def _misc(self):
        self.waiter = tasks.TaskWaiter(self.environment)
        self.serv = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        if self.environment[ohostedcons.StorageEnv.DOMAIN_TYPE] == 'nfs':
            self.storageType = self.NFS_DOMAIN
        elif self.environment[
            ohostedcons.StorageEnv.DOMAIN_TYPE
        ] == 'glusterfs':
            self.storageType = self.GLUSTERFS_DOMAIN
        self.logger.debug(str(self.serv.s.getVdsHardwareInfo()))
        vdsmReady = False
        retry = 0
        while not vdsmReady and retry < self.MAX_RETRY:
            retry += 1
            try:
                self.logger.debug(str(self.serv.s.getVdsHardwareInfo()))
                vdsmReady = True
            except socket.error:
                self.logger.info(_('Waiting for VDSM hardware info'))
                time.sleep(1)
        self.logger.info(_('Creating Storage Domain'))
        self._connectStorageServer()
        self._createStorageDomain()
        self._createStoragePool()
        self._connectStoragePool()
        self._spmStart()
        self._activateStorageDomain()

# vim: expandtab tabstop=4 shiftwidth=4
