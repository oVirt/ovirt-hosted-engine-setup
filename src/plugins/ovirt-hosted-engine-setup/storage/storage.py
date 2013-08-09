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
    UMOUNT_TRIES = 10

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
        self.domain_exists = False
        self.pool_exists = False

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
        rc = -1
        tries = self.UMOUNT_TRIES
        while tries > 0:
            rc, _stdout, _stderr = self.execute(
                (
                    self.command.get('umount'),
                    path
                ),
                raiseOnError=False
            )
            if rc == 0:
                tries = -1
            else:
                tries -= 1
                time.sleep(1)
        return rc

    def _handleHostId(self):
        if not self.environment[
            ohostedcons.CoreEnv.ADDITIONAL_HOST_ENABLED
        ]:
            self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST] = False
            self.logger.info(_('Installing on first host'))
        else:
            interactive = self.environment[
                ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
            ] is None
            if interactive:
                self.environment[
                    ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
                ] = self.dialog.queryString(
                    name='OVEHOSTED_ADDITIONAL_HOST',
                    note=_(
                        'The specified storage location already contains a '
                        'data domain. Is this an additional host setup '
                        '(@VALUES@)[@DEFAULT@]? '
                    ),
                    prompt=True,
                    validValues=(_('Yes'), _('No')),
                    caseSensitive=False,
                    default=_('Yes')
                ) == _('Yes').lower()
        if not self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]:
            self.logger.info(_('Installing on first host'))
            self.environment[
                ohostedcons.StorageEnv.HOST_ID
            ] = ohostedcons.Const.FIRST_HOST_ID
        else:
            self.logger.info(_('Installing on additional host'))
            if self.environment[
                ohostedcons.StorageEnv.HOST_ID
            ] == ohostedcons.Const.FIRST_HOST_ID:
                self.environment[
                    ohostedcons.StorageEnv.HOST_ID
                ] = None
            interactive = self.environment[
                ohostedcons.StorageEnv.HOST_ID
            ] is None
            valid = False
            while not valid:
                if interactive:
                    self.environment[
                        ohostedcons.StorageEnv.HOST_ID
                    ] = self.dialog.queryString(
                        name='OVEHOSTED_HOST_ID',
                        note=_(
                            'Please specify the Host ID '
                            '[Must be integer, default: @DEFAULT@]: '
                        ),
                        prompt=True,
                        default=ohostedcons.Const.FIRST_HOST_ID + 1,
                    )
                try:
                    valid = True
                    if int(
                        self.environment[ohostedcons.StorageEnv.HOST_ID]
                    ) == ohostedcons.Const.FIRST_HOST_ID:
                        valid = False
                        if interactive:
                            self.logger.error(
                                _('Cannot use the same ID used by first host')
                            )
                        else:
                            raise RuntimeError(
                                _('Cannot use the same ID used by first host')
                            )
                except ValueError:
                    valid = False
                    if interactive:
                        self.logger.error(
                            _('Invalid value for Host ID: must be integer')
                        )
                    else:
                        raise RuntimeError(
                            _('Invalid value for Host ID: must be integer')
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
            if self._umount(path) == 0:
                os.rmdir(path)
            else:
                self.logger.warning(
                    _('Cannot unmount {path}').format(
                        path=path,
                    )
                )

    def _getExistingDomain(self):
        self._storageServerConnection()
        domains = self._getStorageDomainsList()
        for sdUUID in domains:
            domain_info = self._getStorageDomainInfo(sdUUID)
            if (
                domain_info and
                domain_info['remotePath'] == self.environment[
                    ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
                ]
            ):
                self.domain_exists = True
                self.environment[
                    ohostedcons.CoreEnv.ADDITIONAL_HOST_ENABLED
                ] = True
                self._handleHostId()
                self.environment[
                    ohostedcons.StorageEnv.STORAGE_DOMAIN_NAME
                ] = domain_info['name']

                self.environment[
                    ohostedcons.StorageEnv.SD_UUID
                ] = sdUUID
                pool_list = domain_info['pool']
                if pool_list:
                    self.pool_exists = True
                    spUUID = pool_list[0]
                    self.environment[
                        ohostedcons.StorageEnv.SP_UUID
                    ] = spUUID
                    self._connectStoragePool()
                    pool_info = self._getStoragePoolInfo(spUUID)
                    if pool_info:
                        self.environment[
                            ohostedcons.StorageEnv.STORAGE_DATACENTER_NAME
                        ] = pool_info['name']
                break

        if not self.domain_exists:
            self._handleHostId()
            self._storageServerConnection(disconnect=True)
        else:
            self.environment[
                ohostedcons.CoreEnv.ADDITIONAL_HOST_ENABLED
            ] = True

    def _getStorageDomainsList(self, spUUID=None):
        if not spUUID:
            spUUID = self.vdsClient.BLANK_UUID
        self.logger.debug('getStorageDomainsList')
        domains = []
        response = self.serv.s.getStorageDomainsList(spUUID)
        self.logger.debug(response)
        if response['status']['code'] == 0:
            for entry in response['domlist']:
                domains.append(entry)
        return domains

    def _getStorageDomainInfo(self, sdUUID):
        self.logger.debug('getStorageDomainInfo')
        info = {}
        response = self.serv.s.getStorageDomainInfo(sdUUID)
        self.logger.debug(response)
        if response['status']['code'] == 0:
            for key, respinfo in response['info'].iteritems():
                info[key] = respinfo
        return info

    def _getStoragePoolInfo(self, spUUID):
        self.logger.debug('getStoragePoolInfo')
        info = {}
        response = self.serv.s.getStoragePoolInfo(spUUID)
        self.logger.debug(response)
        if response['status']['code'] == 0:
            for key in response['info'].keys():
                info[key] = response['info'][key]
        return info

    def _storageServerConnection(self, disconnect=False):
        method = self.serv.connectStorageServer
        debug_msg = 'connectStorageServer'
        if disconnect:
            method = self.serv.disconnectStorageServer
            debug_msg = 'disconnectStorageServer'
        self.logger.debug(debug_msg)
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
        method(args=[
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
        ID = self.environment[ohostedcons.StorageEnv.HOST_ID]
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
        self.environment.setdefault(
            ohostedcons.StorageEnv.HOST_ID,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.STORAGE_TYPE,
            None
        )
        self.environment.setdefault(
            ohostedcons.CoreEnv.ADDITIONAL_HOST_ENABLED,
            False
        )
        self.environment.setdefault(
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST,
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
        self.dialog.note(
            _(
                'During customization use CTRL-D to abort.'
            )
        )
        self.serv = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
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
                            'you would like to use (@VALUES@)[@DEFAULT@]: '
                        ),
                        prompt=True,
                        caseSensitive=True,
                        validValues=(
                            'glusterfs',
                            'nfs',
                        ),
                        default='nfs',
                    )

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
            ohostedcons.StorageEnv.DOMAIN_TYPE
        ] == 'nfs':
            self.storageType = self.NFS_DOMAIN
        elif self.environment[
            ohostedcons.StorageEnv.DOMAIN_TYPE
        ] == 'glusterfs':
            self.storageType = self.GLUSTERFS_DOMAIN
        self._getExistingDomain()
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
        after=(
            ohostedcons.Stages.VDSMD_START,
        ),
        name=ohostedcons.Stages.STORAGE_AVAILABLE,
    )
    def _misc(self):
        self.waiter = tasks.TaskWaiter(self.environment)
        self.serv = self.environment[ohostedcons.VDSMEnv.VDS_CLI]

        # vdsmd has been restarted, we need to reconnect in any case.
        self._storageServerConnection()
        if self.domain_exists:
            self.logger.info(_('Connecting Storage Domain'))
        else:
            self.logger.info(_('Creating Storage Domain'))
            self._createStorageDomain()
        if self.pool_exists:
            self.logger.info(_('Connecting Storage Pool'))
        else:
            self.logger.info(_('Creating Storage Pool'))
            self._createStoragePool()
        self._connectStoragePool()
        if not self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]:
            self._spmStart()
            self._activateStorageDomain()

# vim: expandtab tabstop=4 shiftwidth=4
