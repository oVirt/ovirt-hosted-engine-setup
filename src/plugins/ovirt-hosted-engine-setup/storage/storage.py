#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2013-2015 Red Hat, Inc.
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

import gettext
import re
import stat
import uuid


from otopi import constants as otopicons
from otopi import plugin
from otopi import util


from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import tasks
from ovirt_hosted_engine_setup import util as ohostedutil


from ovirt_hosted_engine_ha.client import client
from ovirt_hosted_engine_ha.lib import storage_backends


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    Local storage plugin.
    """

    _RE_NOT_ALPHANUMERIC = re.compile(r"[^-\w]")
    _NOT_VALID_NAME_MSG = _(
        'It can only consist of alphanumeric '
        'characters (that is, letters, numbers, '
        'and signs "-" and "_"). All other characters '
        'are not valid in the name.'
    )

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self.cli = None
        self.waiter = None
        self.storageType = None
        self.protocol_version = None
        self.domain_exists = False
        self.pool_exists = False
        self._connected = False
        self._monitoring = False

    def _re_deploying_host(self):
        interactive = self.environment[ohostedcons.CoreEnv.RE_DEPLOY] is None
        if interactive:
            self.environment[
                ohostedcons.CoreEnv.RE_DEPLOY
            ] = self.dialog.queryString(
                name='OVEHOSTED_RE_DEPLOY_HOST',
                note=_(
                    'The Host ID is already known. '
                    'Is this a re-deployment on an additional host that was '
                    'previously set up '
                    '(@VALUES@)[@DEFAULT@]? '
                ),
                prompt=True,
                validValues=(_('Yes'), _('No')),
                caseSensitive=False,
                default=_('Yes')
            ) == _('Yes').lower()
        return self.environment[ohostedcons.CoreEnv.RE_DEPLOY]

    def _handleHostId(self):
        if not self.environment[
            ohostedcons.CoreEnv.ADDITIONAL_HOST_ENABLED
        ]:
            self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST] = False
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
                    host_id = self.dialog.queryString(
                        name='OVEHOSTED_HOST_ID',
                        note=_(
                            'Please specify the Host ID '
                            '[Must be integer, default: @DEFAULT@]: '
                        ),
                        prompt=True,
                        default=ohostedcons.Const.FIRST_HOST_ID + 1,
                    )
                else:
                    host_id = self.environment[
                        ohostedcons.StorageEnv.HOST_ID
                    ]
                try:
                    # ensure it's an int and not the FIRST_HOST_ID.
                    if int(host_id) == ohostedcons.Const.FIRST_HOST_ID:
                        valid = False
                        if interactive:
                            self.logger.error(
                                _('Cannot use the same ID used by first host')
                            )
                        else:
                            raise RuntimeError(
                                _('Cannot use the same ID used by first host')
                            )
                    else:
                        valid = True
                        self.environment[
                            ohostedcons.StorageEnv.HOST_ID
                        ] = int(host_id)
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

    @plugin.event(
        stage=plugin.Stages.STAGE_VALIDATION,
        condition=lambda self: self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
        after=(
            ohostedcons.Stages.LOCKSPACE_VALID,
        ),
    )
    def _validation(self):
        """
        Check that host id is not already in use
        """
        if self.storageType in (
            ohostedcons.VDSMConstants.ISCSI_DOMAIN,
            ohostedcons.VDSMConstants.FC_DOMAIN,
        ):
            # For iSCSI we need to connect the pool for
            # having /rhev populated.
            self._storagePoolConnection()
            # And we need also to connect metadata LVMs
            # Prepare the Backend interface
            # Get UUIDs of the storage
            lockspace = self.environment[
                ohostedcons.SanlockEnv.LOCKSPACE_NAME
            ]
            activate_devices = {
                lockspace + '.lockspace': (
                    storage_backends.VdsmBackend.Device(
                        image_uuid=self.environment[
                            ohostedcons.StorageEnv.
                            LOCKSPACE_IMAGE_UUID
                        ],
                        volume_uuid=self.environment[
                            ohostedcons.StorageEnv.
                            LOCKSPACE_VOLUME_UUID
                        ],
                    )
                ),
                lockspace + '.metadata': (
                    storage_backends.VdsmBackend.Device(
                        image_uuid=self.environment[
                            ohostedcons.StorageEnv.
                            METADATA_IMAGE_UUID
                        ],
                        volume_uuid=self.environment[
                            ohostedcons.StorageEnv.
                            METADATA_VOLUME_UUID
                        ],
                    )
                ),
            }
            backend = storage_backends.VdsmBackend(
                sd_uuid=self.environment[
                    ohostedcons.StorageEnv.SD_UUID
                ],
                sp_uuid=self.environment[
                    ohostedcons.StorageEnv.SP_UUID
                ],
                dom_type=self.environment[
                    ohostedcons.StorageEnv.DOMAIN_TYPE
                ],
                **activate_devices
            )
            with ohostedutil.VirtUserContext(
                self.environment,
                # umask 007
                umask=stat.S_IRWXO
            ):
                backend.connect()
        all_host_stats = {}
        with ohostedutil.VirtUserContext(
            environment=self.environment,
            umask=stat.S_IWGRP | stat.S_IWOTH,
        ):
            ha_cli = client.HAClient()
            all_host_stats = ha_cli.get_all_host_stats_direct(
                dom_type=self.environment[
                    ohostedcons.StorageEnv.DOMAIN_TYPE
                ],
                sd_uuid=self.environment[
                    ohostedcons.StorageEnv.SD_UUID
                ],
                service_type=self.environment[
                    ohostedcons.SanlockEnv.LOCKSPACE_NAME
                ] + ".metadata",
            )
        if (
            self.environment[
                ohostedcons.StorageEnv.HOST_ID
            ] in all_host_stats.keys() and
            not self._re_deploying_host()
        ):
            raise RuntimeError(
                _('Invalid value for Host ID: already used')
            )

    def _validName(self, name):
        if (
            name is None or
            self._RE_NOT_ALPHANUMERIC.search(name)
        ):
            return False
        return True

    def _removeNFSTrailingSlash(self, path):
        nfspath = path.split(":")
        if len(nfspath[1]) > 1:
            ename = nfspath[1].rstrip('/')
        else:
            ename = nfspath[1]
        return nfspath[0] + ':' + ename

    def _getExistingDomain(self):
        self.logger.debug('_getExistingDomain')
        if self.storageType in (
            ohostedcons.VDSMConstants.ISCSI_DOMAIN,
            ohostedcons.VDSMConstants.FC_DOMAIN,
        ):
            if self.environment[ohostedcons.StorageEnv.VG_UUID] is not None:
                vginfo = self.cli.getVGInfo(
                    self.environment[ohostedcons.StorageEnv.VG_UUID]
                )
                self.logger.debug(vginfo)
                if vginfo['status']['code'] != 0:
                    raise RuntimeError(vginfo['status']['message'])
                self.environment[
                    ohostedcons.CoreEnv.ADDITIONAL_HOST_ENABLED
                ] = True
                self.environment[
                    ohostedcons.StorageEnv.SD_UUID
                ] = vginfo['info']['name']
                domain_info = self._getStorageDomainInfo(
                    self.environment[
                        ohostedcons.StorageEnv.SD_UUID
                    ]
                )
                if 'uuid' in domain_info:
                    self.domain_exists = True
                    pool_list = domain_info['pool']
                    if pool_list:
                        self.pool_exists = True
                        spUUID = pool_list[0]
                        self.environment[
                            ohostedcons.StorageEnv.SP_UUID
                        ] = spUUID
                self._handleHostId()
                if self.pool_exists:
                    pool_info = self._getStoragePoolInfo(spUUID)
                    if pool_info:
                        self.environment[
                            ohostedcons.StorageEnv.STORAGE_DATACENTER_NAME
                        ] = pool_info['name']
        elif self.storageType in (
            ohostedcons.VDSMConstants.NFS_DOMAIN,
            ohostedcons.VDSMConstants.GLUSTERFS_DOMAIN,
        ) and not self.environment[
            ohostedcons.StorageEnv.GLUSTER_PROVISIONING_ENABLED
        ]:
            self._storageServerConnection()
            domains = self._getStorageDomainsList()
            for sdUUID in domains:
                domain_info = self._getStorageDomainInfo(sdUUID)
                if (
                    domain_info and
                    'remotePath' in domain_info and
                    'type' in domain_info and
                    domain_info['type'] in (
                        ohostedcons.StorageDomainType.NFS,
                        ohostedcons.StorageDomainType.GLUSTERFS,
                    ) and
                    self._removeNFSTrailingSlash(
                        domain_info['remotePath']
                    ) == self._removeNFSTrailingSlash(
                        self.environment[
                            ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
                        ]
                    )
                ):
                    self.domain_exists = True
                    self.environment[
                        ohostedcons.CoreEnv.ADDITIONAL_HOST_ENABLED
                    ] = True
                    self.environment[
                        ohostedcons.StorageEnv.STORAGE_DOMAIN_NAME
                    ] = domain_info['name']
                    self.environment[
                        ohostedcons.StorageEnv.SD_UUID
                    ] = sdUUID
                    self._handleHostId()
                    pool_list = domain_info['pool']
                    if pool_list:
                        self.pool_exists = True
                        spUUID = pool_list[0]
                        self.environment[
                            ohostedcons.StorageEnv.SP_UUID
                        ] = spUUID
                        self._storagePoolConnection()
                        pool_info = self._getStoragePoolInfo(spUUID)
                        if pool_info:
                            self.environment[
                                ohostedcons.StorageEnv.STORAGE_DATACENTER_NAME
                            ] = pool_info['name']
                    break

        if not self.domain_exists:
            self._handleHostId()
            if self.storageType in (
                ohostedcons.VDSMConstants.NFS_DOMAIN,
                ohostedcons.VDSMConstants.GLUSTERFS_DOMAIN,
            ) and not self.environment[
                ohostedcons.StorageEnv.GLUSTER_PROVISIONING_ENABLED
            ]:
                self._storageServerConnection(disconnect=True)
        else:
            valid = self._validateStorageDomain(
                self.environment[
                    ohostedcons.StorageEnv.SD_UUID
                ]
            )
            if valid[0] != 0:
                raise RuntimeError(
                    _(
                        'Dirty Storage Domain: {message}\n'
                        'Please clean the storage device and try again'
                    ).format(
                        message=valid[1],
                    )
                )

    def _getStorageDomainsList(self, spUUID=None):
        if not spUUID:
            spUUID = ohostedcons.Const.BLANK_UUID
        self.logger.debug('getStorageDomainsList')
        domains = []
        response = self.cli.getStorageDomainsList(spUUID)
        self.logger.debug(response)
        if response['status']['code'] == 0:
            for entry in response['domlist']:
                domains.append(entry)
        return domains

    def _validateStorageDomain(self, sdUUID):
        self.logger.debug('validateStorageDomain')
        response = self.cli.validateStorageDomain(sdUUID)
        self.logger.debug(response)
        if response['status']['code']:
            return response['status']['code'], response['status']['message']
        return 0, ''

    def _getStorageDomainInfo(self, sdUUID):
        self.logger.debug('getStorageDomainInfo')
        info = {}
        response = self.cli.getStorageDomainInfo(sdUUID)
        self.logger.debug(response)
        if response['status']['code'] == 0:
            for key, respinfo in response['info'].iteritems():
                info[key] = respinfo
        return info

    def _getStoragePoolInfo(self, spUUID):
        self.logger.debug('getStoragePoolInfo')
        info = {}
        response = self.cli.getStoragePoolInfo(spUUID)
        self.logger.debug(response)
        if response['status']['code'] == 0:
            for key in response['info'].keys():
                info[key] = response['info'][key]
        return info

    def _storageServerConnection(self, disconnect=False):
        method = self.cli.connectStorageServer
        debug_msg = 'connectStorageServer'
        if disconnect:
            method = self.cli.disconnectStorageServer
            debug_msg = 'disconnectStorageServer'
        self.logger.debug(debug_msg)
        spUUID = ohostedcons.Const.BLANK_UUID
        conList = None
        if self.storageType in (
            ohostedcons.VDSMConstants.NFS_DOMAIN,
            ohostedcons.VDSMConstants.GLUSTERFS_DOMAIN,
        ):
            conDict = {
                'connection': self.environment[
                    ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
                ],
                'user': 'kvm',
                'id': self.environment[
                    ohostedcons.StorageEnv.CONNECTION_UUID
                ],
            }
            if self.storageType == ohostedcons.VDSMConstants.NFS_DOMAIN:
                conDict['protocol_version'] = self.protocol_version
            if self.storageType == ohostedcons.VDSMConstants.GLUSTERFS_DOMAIN:
                conDict['tpgt'] = '1'
                conDict['vfs_type'] = 'glusterfs'
            conList = [conDict]
        elif self.storageType in (
            ohostedcons.VDSMConstants.ISCSI_DOMAIN,
        ):
            conList = [
                {
                    'connection': self.environment[
                        ohostedcons.StorageEnv.ISCSI_IP_ADDR
                    ],
                    'iqn': self.environment[
                        ohostedcons.StorageEnv.ISCSI_TARGET
                    ],
                    'portal': self.environment[
                        ohostedcons.StorageEnv.ISCSI_PORTAL
                    ],
                    'user': self.environment[
                        ohostedcons.StorageEnv.ISCSI_USER
                    ],
                    'password': self.environment[
                        ohostedcons.StorageEnv.ISCSI_PASSWORD
                    ],
                    'id': self.environment[
                        ohostedcons.StorageEnv.CONNECTION_UUID
                    ],
                    'port': self.environment[
                        ohostedcons.StorageEnv.ISCSI_PORT
                    ],
                }
            ]
        else:
            raise RuntimeError(_('Invalid Storage Type'))

        status = method(
            self.storageType,
            spUUID,
            conList
        )
        self.logger.debug(status)
        if status['status']['code'] != 0:
            raise RuntimeError(status['status']['message'])
        if not disconnect:
            for con in status['statuslist']:
                if con['status'] != 0:
                    raise RuntimeError(
                        _('Connection to storage server failed')
                    )

    def _createStorageDomain(self):
        self.logger.debug('createStorageDomain')
        sdUUID = self.environment[ohostedcons.StorageEnv.SD_UUID]
        domainName = self.environment[
            ohostedcons.StorageEnv.STORAGE_DOMAIN_NAME
        ]
        typeSpecificArgs = None
        if self.storageType in (
            ohostedcons.VDSMConstants.NFS_DOMAIN,
            ohostedcons.VDSMConstants.GLUSTERFS_DOMAIN,
        ):
            typeSpecificArgs = self.environment[
                ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
            ]
        elif self.storageType in (
            ohostedcons.VDSMConstants.ISCSI_DOMAIN,
            ohostedcons.VDSMConstants.FC_DOMAIN,
        ):
            typeSpecificArgs = self.environment[
                ohostedcons.StorageEnv.VG_UUID
            ]
        else:
            raise RuntimeError(_('Invalid Storage Type'))
        domainType = ohostedcons.VDSMConstants.DATA_DOMAIN
        version = 3
        status = self.cli.createStorageDomain(
            self.storageType,
            sdUUID,
            domainName,
            typeSpecificArgs,
            domainType,
            version
        )
        if status['status']['code'] != 0:
            raise RuntimeError(status['status']['message'])
        self.logger.debug(self.cli.repoStats())
        self.logger.debug(
            self.cli.getStorageDomainStats(sdUUID)
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
        domList = [sdUUID]
        mVer = 1
        self.logger.debug((
            'createStoragePool(args=['
            'poolType={poolType},'
            'spUUID={spUUID},'
            'poolName={poolName},'
            'masterDom={masterDom},'
            'domList={domList},'
            'mVer={mVer}'
            '])'
        ).format(
            poolType=poolType,
            spUUID=spUUID,
            poolName=poolName,
            masterDom=masterDom,
            domList=domList,
            mVer=mVer,
        ))

        status = self.cli.createStoragePool(
            poolType,
            spUUID,
            poolName,
            masterDom,
            domList,
            mVer
        )
        self.logger.debug(status)
        if status['status']['code'] != 0:
            raise RuntimeError(status['status']['message'])

    def _startMonitoringDomain(self):
        self.logger.debug('_startMonitoringDomain')
        status = self.cli.startMonitoringDomain(
            self.environment[ohostedcons.StorageEnv.SD_UUID],
            self.environment[ohostedcons.StorageEnv.HOST_ID]
        )
        self.logger.debug(status)
        if status['status']['code'] != 0:
            raise RuntimeError(status['status']['message'])

        waiter = tasks.DomainMonitorWaiter(self.environment)
        waiter.wait(self.environment[ohostedcons.StorageEnv.SD_UUID])

    def _stopMonitoringDomain(self):
        self.logger.debug('_stopMonitoringDomain')
        status = self.cli.stopMonitoringDomain(
            self.environment[ohostedcons.StorageEnv.SD_UUID],
            self.environment[ohostedcons.StorageEnv.HOST_ID]
        )
        self.logger.debug(status)
        if status['status']['code'] != 0:
            raise RuntimeError(status['status']['message'])

    def _storagePoolConnection(self, disconnect=False):
        spUUID = self.environment[ohostedcons.StorageEnv.SP_UUID]
        sdUUID = self.environment[ohostedcons.StorageEnv.SD_UUID]
        ID = self.environment[ohostedcons.StorageEnv.HOST_ID]
        scsi_key = spUUID
        master = sdUUID
        master_ver = 1
        method = self.cli.connectStoragePool
        method_args = [
            spUUID,
            ID,
            scsi_key,
        ]
        debug_msg = 'connectStoragePool'
        if disconnect:
            method = self.cli.disconnectStoragePool
            debug_msg = 'disconnectStoragePool'
        else:
            method_args += [
                master,
                master_ver,
                {sdUUID: 'active'},
            ]
        self.logger.debug(debug_msg)
        status = method(*method_args)
        if status['status']['code'] != 0:
            raise RuntimeError(status['status']['message'])
        self._connected = not disconnect

    def _spmStart(self):
        self.logger.debug('spmStart')
        spUUID = self.environment[ohostedcons.StorageEnv.SP_UUID]
        prevID = -1
        prevLVER = -1
        recoveryMode = -1
        scsiFencing = 'false'
        maxHostID = ohostedcons.Const.MAX_HOST_ID
        version = 3
        status = self.cli.spmStart(
            spUUID,
            prevID,
            prevLVER,
            recoveryMode,
            scsiFencing,
            maxHostID,
            version
        )
        self.logger.debug(status)
        if status['status']['code'] != 0:
            raise RuntimeError(status['status']['message'])

    def _spmStop(self):
        self.logger.debug('spmStop')
        spUUID = self.environment[ohostedcons.StorageEnv.SP_UUID]
        status = self.cli.spmStop(
            spUUID,
        )
        self.logger.debug(status)
        if status['status']['code'] != 0:
            raise RuntimeError(status['status']['message'])

    def _activateStorageDomain(self):
        self.logger.debug('activateStorageDomain')
        sdUUID = self.environment[ohostedcons.StorageEnv.SD_UUID]
        spUUID = self.environment[ohostedcons.StorageEnv.SP_UUID]
        status = self.cli.activateStorageDomain(
            sdUUID,
            spUUID
        )
        if status['status']['code'] != 0:
            raise RuntimeError(status['status']['message'])
        self.waiter.wait()
        self.logger.debug(self.cli.getSpmStatus(spUUID))
        info = self.cli.getStoragePoolInfo(spUUID)
        self.logger.debug(info)
        self.logger.debug(self.cli.repoStats())

    def _check_existing_pools(self):
        self.logger.debug('_check_existing_pools')
        self.logger.debug('getConnectedStoragePoolsList')
        pools = self.cli.getConnectedStoragePoolsList()
        self.logger.debug(pools)
        if pools['status']['code'] != 0:
            raise RuntimeError(pools['status']['message'])
        if pools['poollist']:
            self.logger.error(
                _(
                    'The following storage pool has been found connected: '
                    '{pools}'
                ).format(
                    pools=', '.join(pools['poollist'])
                )
            )
            raise RuntimeError(
                _('Cannot setup Hosted Engine with connected storage pools')
            )

    def _customizeStorageDomainName(self):
        interactive = self.environment[
            ohostedcons.StorageEnv.STORAGE_DOMAIN_NAME
        ] is None
        while not self._validName(
            self.environment[
                ohostedcons.StorageEnv.STORAGE_DOMAIN_NAME
            ]
        ):
            self.environment[
                ohostedcons.StorageEnv.STORAGE_DOMAIN_NAME
            ] = self.dialog.queryString(
                name='OVEHOSTED_STORAGE_DOMAIN_NAME',
                note=_(
                    'Please provide storage domain name. '
                    '[@DEFAULT@]: '
                ),
                prompt=True,
                caseSensitive=True,
                default=ohostedcons.Defaults.DEFAULT_STORAGE_DOMAIN_NAME,
            )
            if not self._validName(
                self.environment[
                    ohostedcons.StorageEnv.STORAGE_DOMAIN_NAME
                ]
            ):
                if interactive:
                    self.dialog.note(
                        text=_(
                            'Storage domain name cannot be empty. '
                            '{notvalid}'
                        ).format(
                            notvalid=self._NOT_VALID_NAME_MSG
                        )
                    )
                else:
                    raise RuntimeError(
                        _(
                            'Storage domain name cannot be empty. '
                            '{notvalid}'
                        ).format(
                            notvalid=self._NOT_VALID_NAME_MSG
                        )
                    )

    def _customizeStorageDatacenterName(self):
        interactive = self.environment[
            ohostedcons.StorageEnv.STORAGE_DATACENTER_NAME
        ] is None
        while not self._validName(
            self.environment[
                ohostedcons.StorageEnv.STORAGE_DATACENTER_NAME
            ]
        ):
            self.environment[
                ohostedcons.StorageEnv.STORAGE_DATACENTER_NAME
            ] = self.dialog.queryString(
                name='OVEHOSTED_STORAGE_DATACENTER_NAME',
                note=_(
                    'Local storage datacenter name is an internal name\n'
                    'and currently will not be shown in engine\'s admin UI.\n'
                    'Please enter local datacenter name [@DEFAULT@]: '
                ),
                prompt=True,
                caseSensitive=True,
                default=ohostedcons.Defaults.DEFAULT_STORAGE_DATACENTER_NAME,
            )
            if not self._validName(
                self.environment[
                    ohostedcons.StorageEnv.STORAGE_DATACENTER_NAME
                ]
            ):
                if interactive:
                    self.dialog.note(
                        text=_(
                            'Data center name cannot be empty. '
                            '{notvalid}'
                        ).format(
                            notvalid=self._NOT_VALID_NAME_MSG
                        )
                    )
                else:
                    raise RuntimeError(
                        _(
                            'Data center name cannot be empty. '
                            '{notvalid}'
                        ).format(
                            notvalid=self._NOT_VALID_NAME_MSG
                        )
                    )

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
            ohostedcons.StorageEnv.BDEVICE_SIZE_GB,
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
        self.environment.setdefault(
            ohostedcons.CoreEnv.RE_DEPLOY,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.CONFIG_STORAGE_EARLY,
        priority=plugin.Stages.PRIORITY_FIRST,
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_STORAGE,
        ),
        before=(
            ohostedcons.Stages.CONFIG_STORAGE_NFS,
            ohostedcons.Stages.CONFIG_STORAGE_BLOCKD,
        ),
    )
    def _early_customization(self):
        self.dialog.note(
            _(
                'During customization use CTRL-D to abort.'
            )
        )
        self.cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        self._check_existing_pools()
        domain_type = self.environment[ohostedcons.StorageEnv.DOMAIN_TYPE]
        if domain_type is None:
            domain_type = self.dialog.queryString(
                name='OVEHOSTED_STORAGE_DOMAIN_TYPE',
                note=_(
                    'Please specify the storage '
                    'you would like to use (@VALUES@)[@DEFAULT@]: '
                ),
                prompt=True,
                caseSensitive=True,
                validValues=(
                    ohostedcons.DomainTypes.GLUSTERFS,
                    ohostedcons.DomainTypes.ISCSI,
                    ohostedcons.DomainTypes.FC,
                    ohostedcons.DomainTypes.NFS3,
                    ohostedcons.DomainTypes.NFS4,
                ),
                default=ohostedcons.DomainTypes.NFS3,
            )

        if domain_type == ohostedcons.DomainTypes.NFS3:
            self.storageType = ohostedcons.VDSMConstants.NFS_DOMAIN
            self.protocol_version = 3
        elif domain_type == ohostedcons.DomainTypes.NFS4:
            self.storageType = ohostedcons.VDSMConstants.NFS_DOMAIN
            self.protocol_version = 4
        elif domain_type == ohostedcons.DomainTypes.GLUSTERFS:
            self.storageType = ohostedcons.VDSMConstants.GLUSTERFS_DOMAIN
        elif domain_type == ohostedcons.DomainTypes.ISCSI:
            self.storageType = ohostedcons.VDSMConstants.ISCSI_DOMAIN
        elif domain_type == ohostedcons.DomainTypes.FC:
            self.storageType = ohostedcons.VDSMConstants.FC_DOMAIN

        else:
            raise RuntimeError(
                _(
                    'Invalid domain type: "{dtype}"'
                ).format(
                    dtype=self.environment[
                        ohostedcons.StorageEnv.DOMAIN_TYPE
                    ],
                )
            )
        self.environment[ohostedcons.StorageEnv.DOMAIN_TYPE] = domain_type
        # Here the execution flow go to specific plugin activated by domain
        # type.

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.CONFIG_STORAGE_LATE,
        priority=plugin.Stages.PRIORITY_FIRST,
        after=(
            ohostedcons.Stages.CONFIG_STORAGE_NFS,
            ohostedcons.Stages.CONFIG_STORAGE_BLOCKD,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_STORAGE,
        ),
    )
    def _late_customization(self):
        # This will be executed after specific plugin activated by domain
        # type finishes.
        self._getExistingDomain()
        self._customizeStorageDomainName()
        self._customizeStorageDatacenterName()

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        after=(
            ohostedcons.Stages.VDSMD_START,
        ),
        name=ohostedcons.Stages.STORAGE_AVAILABLE,
    )
    def _misc(self):
        self.waiter = tasks.TaskWaiter(self.environment)
        self.cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        self._check_existing_pools()
        if self.storageType in (
            ohostedcons.VDSMConstants.NFS_DOMAIN,
            ohostedcons.VDSMConstants.GLUSTERFS_DOMAIN,
        ):
            # vdsmd has been restarted, we need to reconnect in any case.
            self._storageServerConnection()
            if self.domain_exists:
                self.logger.info(_('Connected to Storage Domain'))
            else:
                self.logger.info(_('Creating Storage Domain'))
                self._createStorageDomain()
        elif self.storageType in (
            ohostedcons.VDSMConstants.ISCSI_DOMAIN,
        ):
            devices = self.cli.getDeviceList(
                self.storageType
            )
            self.logger.debug(devices)
            if devices['status']['code'] != 0:
                raise RuntimeError(devices['status']['message'])
            iscsi_device = None
            for device in devices['devList']:
                for path in device['pathlist']:
                    if path['iqn'] == self.environment[
                        ohostedcons.StorageEnv.ISCSI_TARGET
                    ]:
                        iscsi_device = device
                        break
            if iscsi_device is None:
                self.logger.info(_('Connecting Storage Domain'))
                self._storageServerConnection()
            if not self.domain_exists:
                self.logger.info(_('Creating Storage Domain'))
                self._createStorageDomain()
        if self.storageType in (
            ohostedcons.VDSMConstants.FC_DOMAIN,
        ):
            if not self.domain_exists:
                self.logger.info(_('Creating Storage Domain'))
                self._createStorageDomain()

        if not self.pool_exists:
            self.logger.info(_('Creating Storage Pool'))
            self._createStoragePool()
        if not self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]:
            self.logger.info(_('Connecting Storage Pool'))
            self._storagePoolConnection()
            self._spmStart()
            self._activateStorageDomain()

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        name=ohostedcons.Stages.STORAGE_POOL_DISCONNECTED,
        after=(
            ohostedcons.Stages.VM_IMAGE_AVAILABLE,
            ohostedcons.Stages.OVF_IMPORTED,
        ),
        condition=lambda self: not self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
    )
    def _disconnect_pool(self):
        self.logger.info(_('Disconnecting Storage Pool'))
        self.waiter.wait()
        self._spmStop()
        self._storagePoolConnection(disconnect=True)
        self.logger.info(_('Start monitoring domain'))
        self._startMonitoringDomain()
        self._monitoring = True

    @plugin.event(
        stage=plugin.Stages.STAGE_CLEANUP,
        condition=lambda self: self.environment[
            otopicons.BaseEnv.ERROR
        ],
    )
    def _cleanup(self):
        if self._connected:
            try:
                self._spmStop()
            except RuntimeError:
                self.logger.debug('Not SPM?', exc_info=True)
            self._storagePoolConnection(disconnect=True)
        if self._monitoring:
            self._stopMonitoringDomain()


# vim: expandtab tabstop=4 shiftwidth=4
