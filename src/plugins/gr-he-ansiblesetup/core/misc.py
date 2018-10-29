#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2017 Red Hat, Inc.
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


"""Misc plugin."""


import gettext
import uuid

from otopi import context as otopicontext
from otopi import plugin
from otopi import util

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import ansible_utils


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """Misc plugin."""

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.VMEnv.LOCAL_VM_UUID,
            str(uuid.uuid4())
        )
        self.environment.setdefault(
            ohostedcons.CoreEnv.LOCAL_VM_DIR,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.ENABLE_HC_GLUSTER_SERVICE,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
        priority=plugin.Stages.PRIORITY_FIRST,
    )
    def _setup(self):
        self.dialog.note(
            _(
                'During customization use CTRL-D to abort.'
            )
        )
        interactive = self.environment[
            ohostedcons.CoreEnv.DEPLOY_PROCEED
        ] is None
        if interactive:
            restore_addition_1 = ''
            restore_addition_2 = ''
            if self.environment[
                ohostedcons.CoreEnv.RESTORE_FROM_FILE
            ] is not None:
                restore_addition_1 = _(
                    'The provided engine backup file will be restored there,\n'
                    'it\'s strongly recommended to run this tool on an host '
                    'that wasn\'t part of the environment going to be '
                    'restored.\nIf a reference to this host is already '
                    'contained in the backup file, it will be filtered out '
                    'at restore time.\n'
                )
                restore_addition_2 = _(
                    'The old hosted-engine storage domain will be renamed, '
                    'after checking that everything is correctly working '
                    'you can manually remove it.\n'
                    'Other hosted-engine hosts have to be reinstalled from '
                    'the engine to update their hosted-engine configuration.\n'
                )

            self.environment[
                ohostedcons.CoreEnv.DEPLOY_PROCEED
            ] = self.dialog.queryString(
                name=ohostedcons.Confirms.DEPLOY_PROCEED,
                note=_(
                    'Continuing will configure this host for serving as '
                    'hypervisor and will create a local VM with a '
                    'running engine.\n'
                    '{restore_addition_1}'
                    'The locally running engine will be used to configure '
                    'a new storage domain and create a VM there.\n'
                    'At the end the disk of the local VM will be moved to the '
                    'shared storage.\n'
                    '{restore_addition_2}'
                    'Are you sure you want to continue? '
                    '(@VALUES@)[@DEFAULT@]: '
                ).format(
                    restore_addition_1=restore_addition_1,
                    restore_addition_2=restore_addition_2,
                ),
                prompt=True,
                validValues=(_('Yes'), _('No')),
                caseSensitive=False,
                default=_('Yes')
            ) == _('Yes').lower()
        if not self.environment[ohostedcons.CoreEnv.DEPLOY_PROCEED]:
            raise otopicontext.Abort('Aborted by user')

        self.environment.setdefault(
            ohostedcons.CoreEnv.REQUIREMENTS_CHECK_ENABLED,
            True
        )

        self.environment[ohostedcons.CoreEnv.ANSIBLE_DEPLOYMENT] = True
        self.environment[ohostedcons.VMEnv.CDROM] = None

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_VM,
        ),
        before=(
            ohostedcons.Stages.CONFIG_CLOUD_INIT_OPTIONS,
            ohostedcons.Stages.DIALOG_TITLES_E_VM,
        ),
    )
    def _customization(self):
        restore_addition = ''
        if self.environment[
            ohostedcons.CoreEnv.RESTORE_FROM_FILE
        ] is not None:
            restore_addition = _(
                'Please note that if you are restoring a backup that contains '
                'info about other hosted-engine hosts,\n'
                'this value should exactly match the value used in the '
                'environment you are going to restore. '
            )

        if self.environment[
            ohostedcons.EngineEnv.HOST_DATACENTER_NAME
        ] is None:
            self.environment[
                ohostedcons.EngineEnv.HOST_DATACENTER_NAME
            ] = self.dialog.queryString(
                name='ovehosted_datacenter_name',
                note=_(
                    'Please enter the name of the datacenter where you want '
                    'to deploy this hosted-engine host. '
                    '{restore_addition}'
                    '[@DEFAULT@]: '
                ).format(
                    restore_addition=restore_addition,
                ),
                prompt=True,
                caseSensitive=True,
                default=ohostedcons.Defaults.DEFAULT_DATACENTER_NAME,
            )
        if self.environment[
            ohostedcons.EngineEnv.HOST_CLUSTER_NAME
        ] is None:
            self.environment[
                ohostedcons.EngineEnv.HOST_CLUSTER_NAME
            ] = self.dialog.queryString(
                name='ovehosted_cluster_name',
                note=_(
                    'Please enter the name of the cluster where you want '
                    'to deploy this hosted-engine host. '
                    '{restore_addition}'
                    '[@DEFAULT@]: '
                ).format(
                    restore_addition=restore_addition,
                ),
                prompt=True,
                caseSensitive=True,
                default=ohostedcons.Defaults.DEFAULT_CLUSTER_NAME,
            )

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        name=ohostedcons.Stages.ANSIBLE_BOOTSTRAP_LOCAL_VM,
    )
    def _closeup(self):
        # TODO: use just env values
        bootstrap_vars = {
            'APPLIANCE_OVA': self.environment[ohostedcons.VMEnv.OVF],
            'FQDN': self.environment[
                ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
            ],
            'VM_MAC_ADDR': self.environment[
                ohostedcons.VMEnv.MAC_ADDR
            ],
            'CLOUD_INIT_DOMAIN_NAME': self.environment[
                ohostedcons.CloudInit.INSTANCE_DOMAINNAME
            ],
            'CLOUD_INIT_HOST_NAME': self.environment[
                ohostedcons.CloudInit.INSTANCE_HOSTNAME
            ],
            'HOST_NAME': self.environment[
                ohostedcons.EngineEnv.APP_HOST_NAME
            ],
            'HOST_ADDRESS': self.environment[
                ohostedcons.NetworkEnv.HOST_NAME
            ],
            'LOCAL_VM_DIR_PATH': ohostedcons.FileLocations.LOCAL_VM_DIR_PATH,
            'LOCAL_VM_DIR_PREFIX': (
                ohostedcons.FileLocations.LOCAL_VM_DIR_PREFIX
            ),
            'ADMIN_PASSWORD': self.environment[
                ohostedcons.EngineEnv.ADMIN_PASSWORD
            ],
            'APPLIANCE_PASSWORD': self.environment[
                ohostedcons.CloudInit.ROOTPWD
            ],
            'TIME_ZONE': self.environment[ohostedcons.CloudInit.VM_TZ],
            'VM_NAME': ohostedcons.Const.HOSTED_ENGINE_VM_NAME,
            'MEM_SIZE': self.environment[ohostedcons.VMEnv.MEM_SIZE_MB],
            'CDROM_UUID': self.environment[ohostedcons.VMEnv.CDROM_UUID],
            'CDROM': '',
            'NIC_UUID': self.environment[ohostedcons.VMEnv.NIC_UUID],
            'CONSOLE_UUID': '',
            'CONSOLE_TYPE': 'vnc',
            'VIDEO_DEVICE': 'vga',
            'GRAPHICS_DEVICE': 'vnc',
            'VCPUS': self.environment[ohostedcons.VMEnv.VCPUS],
            'MAXVCPUS': self.environment[ohostedcons.VMEnv.MAXVCPUS],
            'CPU_SOCKETS': '1',
            'EMULATED_MACHINE': self.environment[
                ohostedcons.VMEnv.EMULATED_MACHINE
            ],
            'VM_UUID': self.environment[ohostedcons.VMEnv.LOCAL_VM_UUID],
            'VM_ETC_HOSTS': self.environment[
                ohostedcons.CloudInit.VM_ETC_HOSTS
            ],
            'ROOT_SSH_PUBKEY': self.environment[
                ohostedcons.CloudInit.ROOT_SSH_PUBKEY
            ],
            'HOST_IP': self.environment[
                ohostedcons.CloudInit.HOST_IP
            ],
            'ROOT_SSH_ACCESS': self.environment[
                ohostedcons.CloudInit.ROOT_SSH_ACCESS
            ].lower(),
            'ENABLE_LIBGFAPI': self.environment[
                ohostedcons.StorageEnv.ENABLE_LIBGFAPI
            ],
            'ENABLE_HC_GLUSTER_SERVICE': self.environment[
                ohostedcons.StorageEnv.ENABLE_HC_GLUSTER_SERVICE
            ],
            'BRIDGE_IF': self.environment[
                ohostedcons.NetworkEnv.BRIDGE_IF
            ],
            'RESTORE_FROM_FILE': self.environment[
                ohostedcons.CoreEnv.RESTORE_FROM_FILE
            ],
            'STORAGE_DOMAIN_NAME': self.environment[
                ohostedcons.StorageEnv.STORAGE_DOMAIN_NAME
            ],
            'DATA_CENTER': self.environment[
                ohostedcons.EngineEnv.HOST_DATACENTER_NAME
            ],
            'CLUSTER': self.environment[
                ohostedcons.EngineEnv.HOST_CLUSTER_NAME
            ],
        }
        inventory_source = 'localhost, {fqdn}'.format(
            fqdn=self.environment[
                ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
            ]
        )

        self.initial_clean_up(bootstrap_vars, inventory_source)

        ah = ansible_utils.AnsibleHelper(
            playbook_name=ohostedcons.FileLocations.HE_AP_BOOTSTRAP_LOCAL_VM,
            extra_vars=bootstrap_vars,
            inventory_source=inventory_source,
        )
        self.logger.info(_('Starting local VM'))
        r = ah.run()
        self.logger.debug(r)

        if (
            'otopi_localvm_dir' in r and
            'path' in r['otopi_localvm_dir']
        ):
            self.environment[
                ohostedcons.CoreEnv.LOCAL_VM_DIR
            ] = r['otopi_localvm_dir']['path']
        else:
            raise RuntimeError(_('Failed getting local_vm_dir'))

        try:
            vsize = r[
                'otopi_appliance_disk_size'
            ]['ansible_facts']['virtual_size']
            self.environment[
                ohostedcons.StorageEnv.OVF_SIZE_GB
            ] = int(vsize)/1024/1024/1024
        except KeyError:
            raise RuntimeError(_('Unable to get appliance disk size'))

        # TODO: get the CPU models list from /ovirt-engine/api/clusterlevels
        # once wrapped by ansible facts and filter it by host CPU architecture
        # in order to let the user choose the cluster CPU type in advance

    def initial_clean_up(self, bootstrap_vars, inventory_source):
        ah = ansible_utils.AnsibleHelper(
            playbook_name=ohostedcons.FileLocations.HE_AP_INITIAL_CLEAN,
            extra_vars=bootstrap_vars,
            inventory_source=inventory_source,
        )
        self.logger.info(_('Cleaning previous attempts'))
        r = ah.run()
        self.logger.debug(r)

    @plugin.event(
        stage=plugin.Stages.STAGE_CLEANUP,
    )
    def _cleanup(self):
        ah = ansible_utils.AnsibleHelper(
            playbook_name=ohostedcons.FileLocations.HE_AP_FINAL_CLEAN,
            extra_vars={
                'LOCAL_VM_DIR': self.environment[
                    ohostedcons.CoreEnv.LOCAL_VM_DIR
                ],
            },
            inventory_source='localhost,',
        )
        self.logger.info(_('Cleaning temporary resources'))
        r = ah.run()
        self.logger.debug(r)

# vim: expandtab tabstop=4 shiftwidth=4
