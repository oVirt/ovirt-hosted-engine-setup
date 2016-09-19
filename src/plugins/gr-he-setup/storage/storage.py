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
import os
import re
import selinux
import stat
import tempfile
import uuid


from otopi import constants as otopicons
from otopi import plugin
from otopi import util


from ovirt_hosted_engine_ha.client import client
from ovirt_hosted_engine_ha.lib import heconflib
from ovirt_hosted_engine_ha.lib import image
from ovirt_hosted_engine_ha.lib import storage_backends


from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import tasks
from ovirt_hosted_engine_setup import util as ohostedutil


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
    VFSTYPE = 'ext3'
    SIZE = '2G'

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self.cli = None
        self.storageType = None
        self.protocol_version = None
        self.domain_exists = False
        self.pool_exists = False
        self._connected = False
        self._monitoring = False
        self._fake_SD_path = None
        self._fake_file = None
        self._selinux_enabled = False
        self._pool_created_by_me = False

    def _attach_loopback_device(self):
        if not self._fake_file:
            self._fake_file = tempfile.mkstemp(
                dir=ohostedcons.FileLocations.OVIRT_HOSTED_ENGINE_LB_DIR
            )[1]
        os.chown(
            self._fake_file,
            self.environment[ohostedcons.VDSMEnv.VDSM_UID],
            self.environment[ohostedcons.VDSMEnv.KVM_GID],
        )
        self.execute(
            args=(
                self.command.get('truncate'),
                '--size=%s' % self.SIZE,
                self._fake_file
            ),
            raiseOnError=True
        )
        losetup = self.command.get('losetup')
        rc, stdout, stderr = self.execute(
            args=(
                losetup,
                '--find',
                '--show',
                '--sizelimit=%s' % self.SIZE,
                self._fake_file,
            ),
            raiseOnError=True
        )
        if rc == 0:
            for line in stdout:
                self._fake_SD_path = line
            if self._fake_SD_path[:9] != '/dev/loop':
                raise RuntimeError(
                    -("Invalid loopback device path name: '{path}'").format(
                        path=self._fake_SD_path,
                    )
                )
            self.logger.debug(
                'Found a available loopback device on %s' % self._fake_SD_path
            )
        if not self._fake_SD_path:
            raise RuntimeError(
                _('Unable to find an available loopback device path ')
            )
        self.execute(
            args=(
                self.command.get('mkfs'),
                '-t',
                self.VFSTYPE,
                self._fake_SD_path,
            ),
            raiseOnError=True
        )
        mntpoint = tempfile.mkdtemp(
            dir=ohostedcons.FileLocations.OVIRT_HOSTED_ENGINE_LB_DIR
        )
        self.execute(
            args=(
                self.command.get('mount'),
                self._fake_SD_path,
                mntpoint
            ),
            raiseOnError=True
        )
        self.execute(
            args=(
                self.command.get('chown'),
                '-R',
                '{u}:{g}'.format(
                    u=self.environment[ohostedcons.VDSMEnv.VDSM_UID],
                    g=self.environment[ohostedcons.VDSMEnv.KVM_GID],
                ),
                mntpoint,
            ),
            raiseOnError=True
        )
        if self._selinux_enabled:
            con = "system_u:object_r:virt_var_lib_t:s0"
            selinux.chcon(path=mntpoint, context=con, recursive=True)
        self.execute(
            args=(
                self.command.get('umount'),
                mntpoint,
            ),
            raiseOnError=True
        )
        os.rmdir(mntpoint)

    def _remove_loopback_device(self):
        if self._fake_SD_path:
            self.execute(
                args=(
                    self.command.get('losetup'),
                    '--detach',
                    self._fake_SD_path,
                ),
                raiseOnError=True
            )
            self._fake_SD_path = None
        if self._fake_file:
            os.unlink(self._fake_file)
            self._fake_file = None

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
            self.logger.warning(
                _(
                    'Setup of additional hosts using this software is '
                    'deprecated and will be removed in 4.1. Please use the '
                    'engine web interface to deploy any additional hosts.'
                )
            )
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
        if self.environment[
            ohostedcons.CoreEnv.ADDITIONAL_HOST_ENABLED
        ] and not self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]:
            msg = _(
                'Re-deploying the engine VM over a previously (partially) '
                'deployed system is not supported. Please clean up the '
                'storage device or select a different one and retry.'
            )
            self.logger.error(msg)
            raise RuntimeError(msg)

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
                    valid = True
                    self.environment[
                        ohostedcons.StorageEnv.HOST_ID
                    ] = int(host_id)
                    if (
                        self.environment[
                            ohostedcons.StorageEnv.HOST_ID
                        ] > ohostedcons.Const.MAX_HOST_ID or
                        self.environment[
                            ohostedcons.StorageEnv.HOST_ID
                        ] < ohostedcons.Const.FIRST_HOST_ID
                    ):
                        valid = False
                        msg = _(
                            'Invalid value for Host ID: must be in {min}-{max}'
                        ).format(
                            min=ohostedcons.Const.FIRST_HOST_ID,
                            max=ohostedcons.Const.MAX_HOST_ID,
                        )
                        if interactive:
                            self.logger.error(msg)
                        else:
                            raise RuntimeError(msg)
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

    def _analyze_volume(self, img, vol_uuid):
        cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        sdUUID = self.environment[ohostedcons.StorageEnv.SD_UUID]
        spUUID = ohostedcons.Const.BLANK_UUID

        voldict = {
            ohostedcons.Const.CONF_IMAGE_DESC: {
                'img_key': ohostedcons.StorageEnv.CONF_IMG_UUID,
                'vol_key': ohostedcons.StorageEnv.CONF_VOL_UUID,
            },
            self.environment[
                ohostedcons.SanlockEnv.LOCKSPACE_NAME
            ] + '.lockspace': {
                'img_key': ohostedcons.StorageEnv.LOCKSPACE_IMAGE_UUID,
                'vol_key': ohostedcons.StorageEnv.LOCKSPACE_VOLUME_UUID,
            },
            self.environment[
                ohostedcons.SanlockEnv.LOCKSPACE_NAME
            ] + '.metadata': {
                'img_key': ohostedcons.StorageEnv.METADATA_IMAGE_UUID,
                'vol_key': ohostedcons.StorageEnv.METADATA_VOLUME_UUID,
            },
        }

        volumeinfo = cli.getVolumeInfo(
            volumeID=vol_uuid,
            imageID=img,
            storagepoolID=spUUID,
            storagedomainID=sdUUID,
        )
        self.logger.debug(volumeinfo)
        if volumeinfo['status']['code'] != 0:
            # avoid raising here, simply skip the unknown volume
            self.logger.debug(
                (
                    'Error fetching volume info '
                    'for {volume}: {message}'
                ).format(
                    volume=vol_uuid,
                    message=volumeinfo['status']['message'],
                )
            )
        else:
            description = volumeinfo['description']
            if description in voldict:
                self.environment[voldict[description]['img_key']] = img
                self.environment[voldict[description]['vol_key']] = vol_uuid
                self.logger.debug(
                    'Found {desc} volume: imgUUID:{img}, volUUID:{vol}'.format(
                        desc=description,
                        img=img,
                        vol=vol_uuid,
                    )
                )

    def _analyze_image(self, img):
        cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        sdUUID = self.environment[ohostedcons.StorageEnv.SD_UUID]
        spUUID = ohostedcons.Const.BLANK_UUID

        volumeslist = cli.getVolumesList(
            imageID=img,
            storagepoolID=spUUID,
            storagedomainID=sdUUID,
        )
        self.logger.debug('volumeslist: {vl}'.format(vl=volumeslist))
        if volumeslist['status']['code'] != 0:
            # avoid raising here, simply skip the unknown image
            self.logger.debug(
                'Error fetching volumes for {image}: {message}'.format(
                    image=image,
                    message=volumeslist['status']['message'],
                )
            )
        else:
            for vol_uuid in volumeslist['items']:
                self._analyze_volume(img, vol_uuid)

    def _scan_images(self):
        """
        Scan for metadata, lockspace and configuration image uuids
        """
        # VDSM getImagesList doesn't work when the SD is not connect to
        # a storage pool so we cannot simply directly call getImagesList
        # see: https://bugzilla.redhat.com/1274622
        img = image.Image(
            self.environment[ohostedcons.StorageEnv.DOMAIN_TYPE],
            self.environment[ohostedcons.StorageEnv.SD_UUID],
        )
        img.prepare_images()
        images = img.get_images_list(self.cli)
        self.logger.debug("Existing images: {images}".format(images=images))
        for img in images:
            self._analyze_image(img)

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        self.command.detect('truncate')
        self.command.detect('mkfs')
        self.command.detect('losetup')
        self.command.detect('mount')
        self.command.detect('umount')
        self.command.detect('chown')

    @plugin.event(
        stage=plugin.Stages.STAGE_VALIDATION,
        condition=lambda self: self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
        name=ohostedcons.Stages.EXISTING_CONF_VOLUME_DETECTED,
    )
    def _validation(self):
        """
        Check that host id is not already in use
        """

        if self.storageType in (
            ohostedcons.VDSMConstants.ISCSI_DOMAIN,
            ohostedcons.VDSMConstants.FC_DOMAIN,
        ):
            # We need to connect metadata LVMs
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
            backend.set_external_logger(self.logger)
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
                ] = vginfo['name']
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
                        if self.environment[
                            ohostedcons.StorageEnv.SP_UUID
                        ] != ohostedcons.Const.BLANK_UUID:
                            self.environment[
                                ohostedcons.StorageEnv.SP_UUID
                            ] = spUUID
                        else:
                            self.logger.debug(
                                'hosted-engine storage domain is attached to '
                                'storage pool {sp}: the engine already '
                                'imported it. Honoring BLANK_UUID from the '
                                'answerfile'
                            )
                self._handleHostId()
        elif self.storageType in (
            ohostedcons.VDSMConstants.NFS_DOMAIN,
            ohostedcons.VDSMConstants.GLUSTERFS_DOMAIN,
        ):
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
                        if self.environment[
                            ohostedcons.StorageEnv.SP_UUID
                        ] != ohostedcons.Const.BLANK_UUID:
                            self.environment[
                                ohostedcons.StorageEnv.SP_UUID
                            ] = spUUID
                        else:
                            self.logger.debug(
                                'hosted-engine storage domain is attached to '
                                'storage pool {sp}: the engine already '
                                'imported it. Honoring BLANK_UUID from the '
                                'answerfile'
                            )
                    break

        if not self.domain_exists:
            self._handleHostId()
            if self.storageType in (
                ohostedcons.VDSMConstants.NFS_DOMAIN,
                ohostedcons.VDSMConstants.GLUSTERFS_DOMAIN,
            ):
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
        if response['status']['code'] == 0 and 'items' in response:
            for entry in response['items']:
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
            for key, respinfo in response.iteritems():
                if key is not 'status':
                    info[key] = respinfo
        return info

    def _getStoragePoolInfo(self, spUUID):
        self.logger.debug('getStoragePoolInfo')
        info = {}
        response = self.cli.getStoragePoolInfo(spUUID)
        self.logger.debug(response)
        if response['status']['code'] == 0:
            for key, respinfo in response.iteritems():
                if key is not 'status':
                    info[key] = respinfo
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
        elif self.storageType in (
                ohostedcons.VDSMConstants.FC_DOMAIN,
        ):
            conList = None
        else:
            raise RuntimeError(_('Invalid Storage Type'))

        if conList:
            if self.environment[ohostedcons.StorageEnv.MNT_OPTIONS]:
                conList[0]['mnt_options'] = self.environment[
                    ohostedcons.StorageEnv.MNT_OPTIONS
                ]
            status = method(
                spUUID,
                self.storageType,
                conList
            )
            self.logger.debug(status)
            if status['status']['code'] != 0:
                raise RuntimeError(status['status']['message'])
            if not disconnect:
                for con in status['items']:
                    if con['status'] != 0:
                        raise RuntimeError(
                            _('Connection to storage server failed')
                        )

        if self._fake_SD_path:
            # We have to keep the loopback device mounted
            # and use the real file path cause VDSM forcefully
            # resolves it!
            fakeSDconList = [{
                'connection': self._fake_file,
                'spec': self._fake_file,
                'vfsType': self.VFSTYPE,
                'id': self.environment[
                    ohostedcons.StorageEnv.FAKE_MASTER_SD_CONNECTION_UUID
                ],
            }]
            status = method(
                spUUID,
                ohostedcons.VDSMConstants.POSIXFS_DOMAIN,
                fakeSDconList
            )
            self.logger.debug(status)
            if status['status']['code'] != 0:
                raise RuntimeError(status['status']['message'])
            if not disconnect:
                for con in status['items']:
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
            sdUUID,
            self.storageType,
            typeSpecificArgs,
            domainName,
            domainType,
            version
        )
        if status['status']['code'] != 0:
            raise RuntimeError(status['status']['message'])
        self.logger.debug(self.cli.repoStats())
        self.logger.debug(
            self.cli.getStorageDomainStats(sdUUID)
        )

    def _createFakeStorageDomain(self):
        self.logger.debug('createFakeStorageDomain')
        storageType = ohostedcons.VDSMConstants.POSIXFS_DOMAIN
        sdUUID = self.environment[ohostedcons.StorageEnv.FAKE_MASTER_SD_UUID]
        domainName = 'FakeHostedEngineStorageDomain'
        typeSpecificArgs = self._fake_file
        domainType = ohostedcons.VDSMConstants.DATA_DOMAIN
        version = 3
        status = self.cli.createStorageDomain(
            sdUUID,
            storageType,
            typeSpecificArgs,
            domainName,
            domainType,
            version
        )
        if status['status']['code'] != 0:
            raise RuntimeError(status['status']['message'])
        self.logger.debug(self.cli.repoStats())
        self.logger.debug(
            self.cli.getStorageDomainStats(sdUUID)
        )

    def _destroyFakeStorageDomain(self):
        self.logger.debug('_destroyFakeStorageDomain')
        status = self.cli.formatStorageDomain(
            storagedomainID=self.environment[
                ohostedcons.StorageEnv.FAKE_MASTER_SD_UUID
            ],
            autoDetach=True,
        )
        if status['status']['code'] != 0:
                raise RuntimeError(status['status']['message'])

    def _createStoragePool(self):
        self.logger.debug('createStoragePool')
        if self.environment[
            ohostedcons.StorageEnv.SP_UUID
        ] == ohostedcons.Const.BLANK_UUID:
            self.environment[
                ohostedcons.StorageEnv.SP_UUID
            ] = str(uuid.uuid4())
            self.logger.debug(
                'spUUID was blank, using a random valid UUID: {uuid}'.format(
                    uuid=self.environment[ohostedcons.StorageEnv.SP_UUID],
                )
            )
        spUUID = self.environment[ohostedcons.StorageEnv.SP_UUID]
        sdUUID = self.environment[ohostedcons.StorageEnv.SD_UUID]
        fakeSdUUID = self.environment[
            ohostedcons.StorageEnv.FAKE_MASTER_SD_UUID
        ]
        poolName = self.environment[
            ohostedcons.StorageEnv.STORAGE_DATACENTER_NAME
        ]
        masterDom = fakeSdUUID
        domList = [fakeSdUUID, sdUUID]
        mVer = 1
        self.logger.debug((
            'createStoragePool(args=['
            'storagepoolID={spUUID}, '
            'name={poolName}, '
            'masterSdUUID={masterDom}, '
            'masterVersion={mVer}, '
            'domainList={domList}, '
            'lockRenewalIntervalSec=None, '
            'leaseTimeSec=None, '
            'ioOpTimeoutSec=None, '
            'leaseRetries=None'
            '])'
        ).format(
            spUUID=spUUID,
            poolName=poolName,
            masterDom=masterDom,
            mVer=mVer,
            domList=domList,
        ))
        status = self.cli.createStoragePool(
            storagepoolID=spUUID,
            name=poolName,
            masterSdUUID=masterDom,
            masterVersion=mVer,
            domainList=domList,
            lockRenewalIntervalSec=None,
            leaseTimeSec=None,
            ioOpTimeoutSec=None,
            leaseRetries=None,
        )
        self.logger.debug(status)
        if status['status']['code'] != 0:
            raise RuntimeError(status['status']['message'])
        self.pool_exists = True
        self._pool_created_by_me = True

    def _destroyStoragePool(self):
        self.logger.debug('_destroyStoragePool')
        spUUID = self.environment[ohostedcons.StorageEnv.SP_UUID]
        ID = self.environment[ohostedcons.StorageEnv.HOST_ID]
        scsi_key = spUUID
        status = self.cli.destroyStoragePool(
            spUUID,
            ID,
            scsi_key
        )
        self.logger.debug(status)
        if status['status']['code'] != 0:
            raise RuntimeError(status['status']['message'])
        self.environment[
            ohostedcons.StorageEnv.SP_UUID
        ] = ohostedcons.Const.BLANK_UUID
        self._connected = False
        self.pool_exists = False

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
        fakeSdUUID = self.environment[
            ohostedcons.StorageEnv.FAKE_MASTER_SD_UUID
        ]
        ID = self.environment[ohostedcons.StorageEnv.HOST_ID]
        scsi_key = spUUID
        if self._fake_SD_path is not None:
            master = fakeSdUUID
        else:
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
                {fakeSdUUID: 'active', sdUUID: 'active'},
            ]
        self.logger.debug(debug_msg)
        status = method(*method_args)
        if status['status']['code'] != 0:
            raise RuntimeError(
                _(
                    'Dirty Storage Domain: {message}\n'
                    'Please clean the storage device and try again'
                ).format(
                    message=status['status']['message'],
                )
            )
        self._connected = not disconnect

    def _spmStart(self):
        self.logger.debug('spmStart')
        spUUID = self.environment[ohostedcons.StorageEnv.SP_UUID]
        prevID = -1
        prevLVER = -1
        scsiFencing = False
        maxHostID = ohostedcons.Const.MAX_HOST_ID
        version = 3
        status = self.cli.spmStart(
            storagepoolID=spUUID,
            prevID=prevID,
            prevLver=prevLVER,
            enableScsiFencing=scsiFencing,
            maxHostID=maxHostID,
            domVersion=version,
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

    def _activateStorageDomain(self, sdUUID):
        self.logger.debug('activateStorageDomain')
        spUUID = self.environment[ohostedcons.StorageEnv.SP_UUID]
        status = self.cli.activateStorageDomain(
            sdUUID,
            spUUID
        )
        if status['status']['code'] != 0:
            raise RuntimeError(status['status']['message'])
        heconflib.task_wait(self.cli, self.logger)
        self.logger.debug(self.cli.getSpmStatus(spUUID))
        info = self.cli.getStoragePoolInfo(spUUID)
        self.logger.debug(info)
        self.logger.debug(self.cli.repoStats())

    def _detachStorageDomain(self, sdUUID, newMasterSdUUID):
        self.logger.debug('detachStorageDomain')
        spUUID = self.environment[ohostedcons.StorageEnv.SP_UUID]
        master_ver = 1
        status = self.cli.detachStorageDomain(
            sdUUID,
            spUUID,
            newMasterSdUUID,
            master_ver
        )
        if status['status']['code'] != 0:
            raise RuntimeError(status['status']['message'])
        heconflib.task_wait(self.cli, self.logger)
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
        if 'poollist' in pools and pools['poollist']:
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
            ohostedcons.Defaults.DEFAULT_STORAGE_DOMAIN_NAME
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.STORAGE_DATACENTER_NAME,
            ohostedcons.Defaults.DEFAULT_STORAGE_DATACENTER_NAME
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.CONNECTION_UUID,
            str(uuid.uuid4())
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.FAKE_MASTER_SD_CONNECTION_UUID,
            str(uuid.uuid4())
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.SD_UUID,
            str(uuid.uuid4())
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.FAKE_MASTER_SD_UUID,
            str(uuid.uuid4())
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.SP_UUID,
            str(uuid.uuid4())
        )
        # TODO: provide a way to let the user customize it validating the input
        self.environment.setdefault(
            ohostedcons.StorageEnv.MNT_OPTIONS,
            None
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
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_STORAGE,
        ),
        before=(
            ohostedcons.Stages.CONFIG_STORAGE_NFS,
            ohostedcons.Stages.CONFIG_STORAGE_BLOCKD,
        ),
    )
    def _early_customization(self):
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
        self._selinux_enabled = selinux.is_selinux_enabled()
        # Here the execution flow go to specific plugin activated by domain
        # type.

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.CONFIG_STORAGE_LATE,
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

        if self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]:
            if self.storageType in (
                ohostedcons.VDSMConstants.ISCSI_DOMAIN,
                ohostedcons.VDSMConstants.FC_DOMAIN,
            ):
                # For iSCSI/FC we need to explicitly call getStorageDomainStats
                # to create/refresh the storage domain directory tree.
                result = self.cli.getStorageDomainStats(
                    self.environment[
                        ohostedcons.StorageEnv.SD_UUID
                    ],
                )
                self.logger.debug(
                    'getStorageDomainStats: {result}'.format(
                        result=result,
                    )
                )
                if result['status']['code'] != 0:
                    raise RuntimeError(
                        'Unable to get storage domain stats: {message}'.format(
                            message=result['status']['message'],
                        )
                    )

            # Scan for metadata, lockspace and configuration image uuids
            self._scan_images()

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        after=(
            ohostedcons.Stages.VDSMD_START,
        ),
        name=ohostedcons.Stages.STORAGE_AVAILABLE,
    )
    def _misc(self):
        self.cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        self._attach_loopback_device()
        self._storageServerConnection()
        self._check_existing_pools()
        if not self.domain_exists:
            self.logger.info(_('Creating Storage Domain'))
            self._createStorageDomain()
        if not self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]:
            if not self.pool_exists:
                self.logger.info(_('Creating Storage Pool'))
                self._createFakeStorageDomain()
                self._createStoragePool()
            self.logger.info(_('Connecting Storage Pool'))
            self._storagePoolConnection()
            self._spmStart()
            self._activateStorageDomain(
                self.environment[ohostedcons.StorageEnv.FAKE_MASTER_SD_UUID]
            )
            self._activateStorageDomain(
                self.environment[ohostedcons.StorageEnv.SD_UUID]
            )

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        name=ohostedcons.Stages.STORAGE_POOL_DESTROYED,
        after=(
            ohostedcons.Stages.VM_IMAGE_AVAILABLE,
            ohostedcons.Stages.OVF_IMPORTED,
        ),
        condition=lambda self: not self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
    )
    def _destroy_pool(self):
        self._detachStorageDomain(
            self.environment[ohostedcons.StorageEnv.SD_UUID],
            self.environment[ohostedcons.StorageEnv.FAKE_MASTER_SD_UUID],
        )
        self.logger.info(_('Destroying Storage Pool'))
        self._destroyStoragePool()
        self._destroyFakeStorageDomain()
        self._remove_loopback_device()
        self.logger.info(_('Start monitoring domain'))
        self._startMonitoringDomain()
        self._monitoring = True

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        condition=lambda self: not self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
        name=ohostedcons.Stages.IMAGES_REPREPARED,
        after=(
            ohostedcons.Stages.VDSCLI_RECONNECTED,
        ),
    )
    def _closeup_reprepare_images(self):
        self.logger.debug(_("Preparing again HE images"))
        img = image.Image(
            self.environment[ohostedcons.StorageEnv.DOMAIN_TYPE],
            self.environment[ohostedcons.StorageEnv.SD_UUID],
        )
        img.prepare_images()

    @plugin.event(
        stage=plugin.Stages.STAGE_CLEANUP,
        condition=lambda self: self.environment[
            otopicons.BaseEnv.ERROR
        ],
    )
    def _cleanup(self):
        if self.pool_exists and self._pool_created_by_me:
            try:
                self._destroyStoragePool()
                self._destroyFakeStorageDomain()
                self._remove_loopback_device()
            except RuntimeError:
                self.logger.debug('Not SPM?', exc_info=True)
        if self._monitoring:
            self._stopMonitoringDomain()


# vim: expandtab tabstop=4 shiftwidth=4
