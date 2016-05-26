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

from otopi import plugin
from otopi import util
from otopi import context as otopicontext

from ovirtsdk.xml import params
from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import engineapi


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    VM new disk plugin.
    """

    API_RETRIES = 600
    API_DELAY = 1

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.Upgrade.CONFIRM_DISK_SWITCH,
            None,
        )

    def _get_host_uuid(self):
        conn = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        hw_info = conn.getVdsHardwareInfo()
        self.logger.debug('hw_info: {h}'.format(h=hw_info))
        if hw_info['status']['code'] != 0:
            raise RuntimeError(
                'Unable to get host uuid: {message}'.format(
                    message=hw_info['status']['message'],
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
                'engine VM disk in {state} state'.format(
                    state=state,
                )
            )
            if 'failed' in state:
                self.logger.error(_(
                    'The new engine VM disk was found in a '
                    'failed state. Please check engine logs.'
                ))
                tries = -1  # Error state
            elif state == 'ok':
                completed = True
                self.logger.info(_(
                    'The new engine VM disk is now ready'
                ))
            else:
                if tries % 30 == 0:
                    self.logger.info(
                        _(
                            'Still waiting for new engine VM '
                            'disk to be {op}. '
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
        stage=plugin.Stages.STAGE_VALIDATION,
        name=ohostedcons.Stages.UPGRADE_CHECK_SD_SPACE,
        after=(
            ohostedcons.Stages.VALIDATION_CA_ACQUIRED,
        ),
    )
    def _check_sd_space(self):
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
                    'available space to create a new disk for the new '
                    'appliance: required {r}GiB - available {a}GiB. '
                    'Please extend the hosted-engine storage domain.'
                ).format(
                    r=required_gib,
                    a=available_gib,
                )
            )
            raise RuntimeError(_(
                'Not enough free space on the hosted-engine storage domain'
            ))

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        name=ohostedcons.Stages.UPGRADE_DISK_CREATED,
        after=(
            ohostedcons.Stages.VALIDATION_CA_ACQUIRED,
        ),
    )
    def _create_disk(self):
        engine_api = engineapi.get_engine_api(self)

        p_sds = params.StorageDomains(
            storage_domain=[
                engine_api.storagedomains.get(
                    id=str(self.environment[ohostedcons.StorageEnv.SD_UUID])
                )
            ]
        )
        description = 'hosted-engine'
        if self.environment[ohostedcons.VMEnv.APPLIANCE_VERSION]:
            description = 'hosted-engine-{v}'.format(
                v=self.environment[ohostedcons.VMEnv.APPLIANCE_VERSION]
            )
        disk_param = params.Disk(
            name='virtio-disk0',
            description=description,
            comment=description,
            alias='virtio-disk0',
            storage_domains=p_sds,
            size=int(
                self.environment[ohostedcons.StorageEnv.IMAGE_SIZE_GB]
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
            ohostedcons.Upgrade.PREV_IMG_UUID
        ] = self.environment[ohostedcons.StorageEnv.IMG_UUID]
        self.environment[
            ohostedcons.Upgrade.PREV_VOL_UUID
        ] = self.environment[ohostedcons.StorageEnv.VOL_UUID]
        self.environment[ohostedcons.StorageEnv.IMG_UUID] = d_img_id
        self.environment[ohostedcons.StorageEnv.VOL_UUID] = d_vol_id

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        after=(
            ohostedcons.Stages.UPGRADED_APPLIANCE_RUNNING,
        ),
        name=ohostedcons.Stages.UPGRADED_DATACENTER_UP,
    )
    def _wait_datacenter_up(self):
        engine_api = engineapi.get_engine_api(self)
        cluster_broker = engine_api.clusters.get(
            name=self.environment[
                ohostedcons.EngineEnv.HOST_CLUSTER_NAME
            ]
        )
        dc_broker = engine_api.datacenters.get(
            id=cluster_broker.get_data_center().get_id()
        )
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
        ready = False
        interactive = self.environment[
            ohostedcons.Upgrade.CONFIRM_DISK_SWITCH
        ] is None
        while not ready:
            dc_broker = dc_broker.update()
            host_broker = host_broker.update()
            dc_status = dc_broker.get_status().state
            host_status = host_broker.get_status().state
            if not (dc_status == 'up' and host_status == 'up'):
                if interactive:
                    rcontinue = self.dialog.queryString(
                        name=ohostedcons.Confirms.UPGRADE_PROCEED,
                        note=_(
                            'The datacenter or this host is still marked as '
                            'down.\nPlease ensure that everything is ready '
                            'before definitively switching the disk of the '
                            'engine VM.\n'
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
        if self.environment[
            ohostedcons.Upgrade.CONFIRM_DISK_SWITCH
        ] is None:
            self.environment[
                ohostedcons.Upgrade.CONFIRM_DISK_SWITCH
            ] = self.dialog.queryString(
                name=ohostedcons.Confirms.UPGRADE_PROCEED,
                note=_(
                    'The engine VM is currently running with the new disk but '
                    'the hosted-engine configuration is still point to the '
                    'old one.\nPlease make sure that everything is fine on '
                    'the engine VM side before definitively switching the '
                    'disks.\n'
                    'Are you sure you want to continue? '
                    '(@VALUES@)[@DEFAULT@]: '
                ),
                prompt=True,
                validValues=(_('Yes'), _('No')),
                caseSensitive=False,
                default=_('Yes')
            ) == _('Yes').lower()
        if not self.environment[
            ohostedcons.Upgrade.CONFIRM_DISK_SWITCH
        ]:
            raise otopicontext.Abort('Aborted by user')

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        after=(
            ohostedcons.Stages.UPGRADED_DATACENTER_UP,
        ),
        name=ohostedcons.Stages.UPGRADED_DISK_SWITCHED,
    )
    def _closeup(self):
        engine_api = engineapi.get_engine_api(self)
        sd_broker = engine_api.storagedomains.get(
            id=str(self.environment[ohostedcons.StorageEnv.SD_UUID])
        )

        # registering the new disk since it has been created after the backup
        new_he_disk = None
        for ud in sd_broker.disks.list(unregistered=True):
            ud_id = ud.get_id()
            self.logger.debug('unregistered disk: {id}'.format(id=ud_id))
            if ud_id == self.environment[ohostedcons.StorageEnv.IMG_UUID]:
                self.logger.debug('found the new engine VM disk')
                new_he_disk = ud
        if not new_he_disk:
            raise RuntimeError(_('Unable to find the new engine VM disk'))
        self.logger.info(_('Registering the new hosted-engine disk in the DB'))
        new_disk_broker = sd_broker.disks.add(new_he_disk, unregistered=True)
        registered = self._wait_disk_ready(
            engine_api,
            new_disk_broker.get_id(),
            True,
        )
        if not registered:
            raise RuntimeError(_(
                'Failed registering the new engine VM disk'
            ))
        e_vm_b = engine_api.vms.get(
            id=str(self.environment[
                ohostedcons.VMEnv.VM_UUID
            ])
        )
        e_vm_b.set_disks([new_disk_broker, ])
        e_vm_b.update()
        # TODO: force OVF_STORE update!!!
        # it will require SDK4 and https://gerrit.ovirt.org/#/c/54537/
        self.logger.warning(
            "FIXME: please reduce the OVF_STORE update timeout with "
            "'engine-config -s OvfUpdateIntervalInMinutes=1', this script "
            "will wait 5 minutes."
        )
        time.sleep(300)
        engine_api.disconnect()


# vim: expandtab tabstop=4 shiftwidth=4
