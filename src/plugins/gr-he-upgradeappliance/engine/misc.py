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
VM new disk plugin.
"""


import gettext
import time

from ovirtsdk.infrastructure import brokers
from ovirtsdk.xml import params

from otopi import context as otopicontext
from otopi import plugin
from otopi import util

from vdsm.client import ServerError

from ovirt_setup_lib import dialog

from ovirt_hosted_engine_ha.lib import upgrade

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import engineapi
from ovirt_hosted_engine_setup import vm_status


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    VM misc plugin.
    """

    API_RETRIES = 3600  # one hour
    API_DELAY = 1

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._e_version = None

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.Upgrade.CONFIRM_UPGRADE_SUCCESS,
            None,
        )
        self.environment.setdefault(
            ohostedcons.Upgrade.CONFIRM_UPGRADE_DISK_RESIZE,
            None,
        )
        self.environment.setdefault(
            ohostedcons.Upgrade.UPGRADE_ABORT_ON_UNSUPPORTED_VER,
            None,
        )

    def _get_host_uuid(self):
        conn = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        try:
            hw_info = conn.Host.getHardwareInfo()
            self.logger.debug('hw_info: {h}'.format(h=hw_info))
        except ServerError as e:
            raise RuntimeError(
                'Unable to get host uuid: {message}'.format(
                    message=str(e),
                )
            )

        return hw_info['systemUUID']

    def _wait_disk_ready(self, engine_api, d_img_id, registering):
        self.logger.info(
            _(
                'Waiting for the engine to complete disk {op}. '
                'This may take several minutes...'
            ).format(
                op=_('registration') if registering else _('creation'),
            )
        )

        tries = self.API_RETRIES
        completed = False
        while not completed and tries > 0:
            tries -= 1
            try:
                state = engine_api.disks.get(id=d_img_id).status.state
            except Exception as exc:
                # Sadly all ovirtsdk errors inherit only from Exception
                self.logger.debug(
                    'Error fetching host state: {error}'.format(
                        error=str(exc),
                    )
                )
                state = ''
            self.logger.debug(
                'engine VM backup disk in {state} state'.format(
                    state=state,
                )
            )
            if 'failed' in state:
                self.logger.error(_(
                    'The engine VM backup disk was found in a '
                    'failed state. Please check engine logs.'
                ))
                tries = -1  # Error state
            elif state == 'ok':
                completed = True
                self.logger.info(_(
                    'The engine VM backup disk is now ready'
                ))
            else:
                if tries % 30 == 0:
                    self.logger.info(
                        _(
                            'Still waiting for engine VM '
                            'backup disk to be {op}. '
                            'This may take several minutes...'
                        ).format(
                            op=_('registered') if registering else _('created')
                        )
                    )
                time.sleep(self.API_DELAY)
        if not completed and tries == 0:
            self.logger.error(_(
                'Timed out while waiting for the disk to be created. '
                'Please check engine logs.'
            ))
            self.logger.error(
                _(
                    'Timed out while waiting for the disk to be {op}. '
                    'Please check engine logs.'
                ).format(
                    op=_('registered') if registering else _('created')
                )
            )
        return completed

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.CUSTOMIZATION_CA_ACQUIRED,
        ),
        name=ohostedcons.Stages.UPGRADE_CHECK_SPM_HOST,
    )
    def _check_spm(self):
        self.logger.info('Checking SPM status on this host')
        engine_api = engineapi.get_engine_api(self)
        self.logger.debug('Successfully connected to the engine')

        my_host_id = None
        my_host_uuid = self._get_host_uuid()
        for h in engine_api.hosts.list():
            if h.get_hardware_information().get_uuid() == my_host_uuid:
                my_host_id = h.get_id()
        if not my_host_id:
            raise(_(
                'Unable to find this host in the engine, '
                'please check the backup recovery'
            ))
        host_broker = engine_api.hosts.get(id=my_host_id)
        if not host_broker.get_spm().get_status().state == 'spm':
            self.logger.error(
                _(
                    'This host is not the SPM one, please select it as the '
                    'SPM from the engine or run this tool on the SPM host.'
                )
            )
            raise RuntimeError(
                _('Cannot run the upgrade tool if the host is not the SPM')
            )
        else:
            self.logger.info(_('This upgrade tool is running on the SPM host'))

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.UPGRADE_CHECK_SD_SPACE,
        after=(
            ohostedcons.Stages.CUSTOMIZATION_CA_ACQUIRED,
            ohostedcons.Stages.CONFIG_OVF_IMPORT,
        ),
    )
    def _check_sd_and_disk_space(self):
        engine_api = engineapi.get_engine_api(self)
        self.logger.debug('Successfully connected to the engine')
        sd_broker = engine_api.storagedomains.get(
            id=str(self.environment[ohostedcons.StorageEnv.SD_UUID])
        )
        if not sd_broker:
            raise RuntimeError(_(
                'Unable to find the hosted-engine storage domain in the engine'
            ))
        available = sd_broker.get_available()
        self.logger.debug('availalbe: {a}'.format(a=available))
        available_gib = sd_broker.get_available() / 1024 / 1024 / 1024
        engine_api.disconnect()
        required_gib = int(
            self.environment[ohostedcons.StorageEnv.IMAGE_SIZE_GB]
        )
        if required_gib > available_gib:
            self.logger.error(
                _(
                    'On the hosted-engine storage domain there is not enough '
                    'available space to create a new disk for backup '
                    'purposes and eventually extend the current disk to '
                    'fit the new appliance: '
                    'required {r}GiB - available {a}GiB. '
                    'Please extend the hosted-engine storage domain.'
                ).format(
                    r=required_gib,
                    a=available_gib,
                )
            )
            raise RuntimeError(_(
                'Not enough free space on the hosted-engine storage domain'
            ))
        else:
            self.logger.info(_(
                'The hosted-engine storage domain has enough free space to '
                'contain a new backup disk.'
            ))
        if int(
            self.environment[ohostedcons.StorageEnv.IMAGE_SIZE_GB]
        ) > int(
            self.environment[ohostedcons.Upgrade.BACKUP_SIZE_GB]
        ):
            self.logger.warning(
                _(
                    'On the hosted-engine disk there is not enough '
                    'available space to fit the new appliance '
                    'disk: '
                    'required {r}GiB - available {a}GiB. '
                ).format(
                    r=self.environment[ohostedcons.StorageEnv.IMAGE_SIZE_GB],
                    a=self.environment[ohostedcons.Upgrade.BACKUP_SIZE_GB],
                )
            )

            interactive = self.environment[
                ohostedcons.Upgrade.CONFIRM_UPGRADE_DISK_RESIZE
            ] is None
            if interactive:
                self.environment[
                    ohostedcons.Upgrade.CONFIRM_UPGRADE_DISK_RESIZE
                ] = self.dialog.queryString(
                    name=ohostedcons.Confirms.UPGRADE_DISK_RESIZE_PROCEED,
                    note=_(
                        'This upgrade tool can resize the hosted-engine VM '
                        'disk; before resizing a backup will be created.\n '
                        'Are you sure you want to continue? '
                        '(@VALUES@)[@DEFAULT@]: '
                    ),
                    prompt=True,
                    validValues=(_('Yes'), _('No')),
                    caseSensitive=False,
                    default=_('Yes')
                ) == _('Yes').lower()
            if self.environment[
                ohostedcons.Upgrade.CONFIRM_UPGRADE_DISK_RESIZE
            ]:
                self.environment[
                    ohostedcons.Upgrade.EXTEND_VOLUME
                ] = True
            else:
                raise RuntimeError(_(
                    'Not enough free space on the hosted-engine disk, '
                    'please extend it'
                ))
        else:
            self.environment[
                ohostedcons.Upgrade.EXTEND_VOLUME
            ] = False

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.UPGRADE_CHECK_UPGRADE_REQUIREMENTS,
        after=(
            ohostedcons.Stages.UPGRADE_CHECK_SD_SPACE,
        ),
    )
    def _check_upgrade_requirements(self):
        self.logger.info('Checking version requirements')
        upg = upgrade.Upgrade()
        if not upg.is_conf_file_uptodate():
            self.logger.error(_(
                'Hosted-engine configuration didn\'t correctly reach 3.6 '
                'level. Please successfully complete the upgrade to '
                '3.6 before proceeding with this upgrade. '
                )
            )
            raise RuntimeError(
                _('Unsupported hosted-engine configuration level')
            )
        self.logger.info(
            _('Checking metadata area')
        )
        vmstatus = vm_status.VmStatus()
        status = vmstatus.get_status()
        self.logger.debug('hosted-engine-status: {s}'.format(s=status))
        old_metadata = False
        for h in status['all_host_stats']:
            if 'stopped' not in status['all_host_stats'][h]:
                self.logger.error(_(
                    'Metadata for host {h} is incompatible with this tool.\n'
                    'Before proceeding with this upgrade, '
                    'please correctly upgrade it to 3.6 '
                    'or clean its metadata area with\n'
                    ' \'hosted-engine --clean-metadata --host-id={id}\'\n'
                    'if decommissioned or not anymore involved in HE.'
                ).format(
                    h=status['all_host_stats'][h]['hostname'],
                    id=status['all_host_stats'][h]['host-id'],
                ))
                old_metadata = True
        if old_metadata:
            raise RuntimeError(
                _('Host with unsupported metadata area')
            )
        self.logger.info(
            _('Hosted-engine configuration is at a compatible level')
        )
        engine_api = engineapi.get_engine_api(self)
        self.logger.debug('Successfully connected to the engine')
        elements = engine_api.clusters.list() + engine_api.datacenters.list()
        for e in elements:
            if isinstance(e, brokers.DataCenter):
                element_t = 'datacenter'
            else:
                element_t = 'cluster'

            version = e.get_version()
            release = '{ma}.{mi}'.format(
                ma=version.major,
                mi=version.minor,
            )
            if release not in ohostedcons.Const.UPGRADE_REQUIRED_CLUSTER_V:
                self.logger.error(
                    _(
                        '{t} {name} is at version {release} which is not '
                        'supported by this upgrade flow. '
                        'Please fix it before upgrading.'
                    ).format(
                        t=element_t.title(),
                        name=e.get_name(),
                        release=release,
                    )
                )
                raise RuntimeError(
                    _('Unsupported {t} level'.format(t=element_t))
                )
        self.logger.info(
            _('All the datacenters and clusters are at a compatible level')
        )
        e_major = engine_api.get_product_info().version.major
        e_minor = engine_api.get_product_info().version.minor
        if not e_major:
            # just for compatibility
            # see: bz#1405386
            e_major = engine_api.get_product_info().get_version().major
            e_minor = engine_api.get_product_info().get_version().minor
        if e_major is not None and e_minor is not None:
            self._e_version = '{ma}.{mi}'.format(
                ma=e_major,
                mi=e_minor,
            )

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.UPGRADE_CHECK_UPGRADE_VERSIONS,
        after=(
            ohostedcons.Stages.UPGRADE_CHECK_UPGRADE_REQUIREMENTS,
            ohostedcons.Stages.CONFIG_OVF_IMPORT,
        ),
    )
    def _check_upgrade_versions(self):
        supported = True
        if not self._e_version:
            self.logger.warning(_('Unable to detect engine version'))
            supported = False
        else:
            if (
                self._e_version not in
                ohostedcons.Const.UPGRADE_SUPPORTED_SOURCES
            ):
                supported = False
        if not self.environment[ohostedcons.VMEnv.APPLIANCE_VERSION]:
            self.logger.warning(_('Unable to detect appliance version'))
            supported = False
        else:
            a_version = '.'.join(self.environment[
                ohostedcons.VMEnv.APPLIANCE_VERSION
            ].split('-')[0].split('.')[:2])
            if a_version not in ohostedcons.Const.UPGRADE_SUPPORTED_TARGETS:
                supported = False
        if not supported:
            self.logger.warning(_('Unsupported upgrade path'))
            self.dialog.note(
                _(
                    'This procedure has been designed and tested only for '
                    'upgrading the engine VM from {sources} to {targets}.\n'
                    'Any other usage is highly experimental and potentially '
                    'dangerous:\n'
                    '  Current engine: {e_version}\n'
                    '  Selected appliance: {a_version}'
                ).format(
                    sources=ohostedcons.Const.UPGRADE_SUPPORTED_SOURCES,
                    targets=ohostedcons.Const.UPGRADE_SUPPORTED_TARGETS,
                    e_version=self._e_version if self._e_version
                    else _('unknown'),
                    a_version=self.environment[
                        ohostedcons.VMEnv.APPLIANCE_VERSION
                    ] if self.environment[
                        ohostedcons.VMEnv.APPLIANCE_VERSION
                    ] else _('unknown'),
                )
            )
            if self.environment[
                ohostedcons.Upgrade.UPGRADE_ABORT_ON_UNSUPPORTED_VER
            ] is None:
                self.environment[
                    ohostedcons.Upgrade.UPGRADE_ABORT_ON_UNSUPPORTED_VER
                ] = dialog.queryBoolean(
                    dialog=self.dialog,
                    name='UPGRADE_ABORT_ON_UNSUPPORTED_VER',
                    note=_(
                        'Do you want to abort the upgrade process? '
                        '(@VALUES@) [@DEFAULT@]: '
                    ),
                    prompt=True,
                    default=True,
                )
            if self.environment[
                ohostedcons.Upgrade.UPGRADE_ABORT_ON_UNSUPPORTED_VER
            ]:
                raise RuntimeError(
                    _('Upgrade aborted due to unsupported version')
                )
            else:
                self.logger.warning(_(
                    'Proceeding on an unsupported and highly experimental path'
                ))

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        name=ohostedcons.Stages.UPGRADE_BACKUP_DISK_CREATED,
    )
    def _create_disk(self):
        engine_api = engineapi.get_engine_api(self)
        now = time.localtime()
        p_sds = params.StorageDomains(
            storage_domain=[
                engine_api.storagedomains.get(
                    id=str(self.environment[ohostedcons.StorageEnv.SD_UUID])
                )
            ]
        )
        description = '{p}{t}'.format(
            p=ohostedcons.Const.BACKUP_DISK_PREFIX,
            t=time.strftime("%Y%m%d%H%M%S", now),
        )
        disk_param = params.Disk(
            name='virtio-disk0',
            description=description,
            comment=description,
            alias='virtio-disk0',
            storage_domains=p_sds,
            size=int(
                self.environment[ohostedcons.Upgrade.BACKUP_SIZE_GB]
            )*1024*1024*1024,
            interface='virtio',
            format='raw',
            sparse=False,
            bootable=True,
        )
        disk_broker = engine_api.disks.add(disk_param)
        d_img_id = disk_broker.get_id()
        d_vol_id = disk_broker.get_image_id()
        self.logger.debug('vol: {v}'.format(v=d_vol_id))
        self.logger.debug('img: {v}'.format(v=d_img_id))

        created = self._wait_disk_ready(
            engine_api,
            d_img_id,
            False,
        )
        if not created:
            raise RuntimeError(_(
                'Failed creating the new engine VM disk'
            ))
        self.environment[
            ohostedcons.Upgrade.BACKUP_IMG_UUID
        ] = d_img_id
        self.environment[
            ohostedcons.Upgrade.BACKUP_VOL_UUID
        ] = d_vol_id
        engine_api.disks.get(
            id=self.environment[ohostedcons.Upgrade.BACKUP_IMG_UUID]
        ).set_active(False)

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        after=(
            ohostedcons.Stages.UPGRADED_APPLIANCE_RUNNING,
        ),
        name=ohostedcons.Stages.UPGRADED_DATACENTER_UP,
    )
    def _wait_datacenter_up(self):
        engine_api = engineapi.get_engine_api(self)

        my_host_id = None
        my_host_uuid = self._get_host_uuid()
        for h in engine_api.hosts.list():
            if h.get_hardware_information().get_uuid() == my_host_uuid:
                my_host_id = h.get_id()
        if not my_host_id:
            raise(_(
                'Unable to find this host in the engine, '
                'please check the backup recovery'
            ))
        host_broker = engine_api.hosts.get(id=my_host_id)

        cluster_broker = engine_api.clusters.get(
            id=host_broker.get_cluster().get_id()
        )
        dc_broker = engine_api.datacenters.get(
            id=cluster_broker.get_data_center().get_id()
        )

        ready = False
        interactive = self.environment[
            ohostedcons.Upgrade.CONFIRM_UPGRADE_SUCCESS
        ] is None
        while not ready:
            dc_broker = engine_api.datacenters.get(
                id=cluster_broker.get_data_center().get_id()
            )
            host_broker = engine_api.hosts.get(id=my_host_id)
            dc_status = dc_broker.get_status().state
            host_status = host_broker.get_status().state
            if not (dc_status == 'up' and host_status == 'up'):
                if interactive:
                    rcontinue = self.dialog.queryString(
                        name=ohostedcons.Confirms.UPGRADE_PROCEED,
                        note=_(
                            'The datacenter or this host is still marked as '
                            'down.\nPlease check engine logs to ensure that '
                            'everything is fine.\n '
                            'Are you sure you want to continue? '
                            '(@VALUES@)[@DEFAULT@]: '
                        ),
                        prompt=True,
                        validValues=(_('Yes'), _('No')),
                        caseSensitive=False,
                        default=_('Yes')
                    ) == _('Yes').lower()
                    if not rcontinue:
                        raise otopicontext.Abort('Aborted by user')
                else:
                    raise RuntimeError(
                        _(
                            'This host is not active in the engine '
                            'after the restore'
                        )
                    )
            else:
                ready = True
        engine_api.disconnect()

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        after=(
            ohostedcons.Stages.UPGRADED_DATACENTER_UP,
        ),
        name=ohostedcons.Stages.UPGRADE_BACKUP_DISK_REGISTERED,
    )
    def _closeup(self):
        engine_api = engineapi.get_engine_api(self)
        sd_broker = engine_api.storagedomains.get(
            id=str(self.environment[ohostedcons.StorageEnv.SD_UUID])
        )
        # registering the backup disk since it has been created after
        # the engine backup was taken
        new_he_disk = None
        for ud in sd_broker.disks.list(unregistered=True):
            ud_id = ud.get_id()
            self.logger.debug('unregistered disk: {id}'.format(id=ud_id))
            if ud_id == self.environment[ohostedcons.Upgrade.BACKUP_IMG_UUID]:
                self.logger.debug('found the engine VM backup disk')
                new_he_disk = ud
        if not new_he_disk:
            raise RuntimeError(_('Unable to find the engine VM backup disk'))
        self.logger.info(_(
            'Registering the hosted-engine backup disk in the DB'
        ))
        new_disk_broker = sd_broker.disks.add(new_he_disk, unregistered=True)
        registered = self._wait_disk_ready(
            engine_api,
            new_disk_broker.get_id(),
            True,
        )
        if not registered:
            raise RuntimeError(_(
                'Failed registering the engine VM backup disk'
            ))
        engine_api.disconnect()


# vim: expandtab tabstop=4 shiftwidth=4
