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

from ovirt_hosted_engine_setup import ansible_utils
from ovirt_hosted_engine_setup import constants as ohostedcons


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
        self.environment.setdefault(
            ohostedcons.CoreEnv.REQUIREMENTS_CHECK_ENABLED,
            True
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.FORCE_IPV4,
            False
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.FORCE_IPV6,
            False
        )
        self.environment.setdefault(
            ohostedcons.CoreEnv.RENEW_PKI_ON_RESTORE,
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

        if self.environment[
            ohostedcons.CoreEnv.RESTORE_FROM_FILE
        ] is not None and self.environment[
            ohostedcons.CoreEnv.RENEW_PKI_ON_RESTORE
        ] is None:
            self.environment[
                ohostedcons.CoreEnv.RENEW_PKI_ON_RESTORE
            ] = self.dialog.queryString(
                name='ovehosted_renew_pki',
                note=_(
                    'Renew engine CA on restore if needed? Please notice '
                    'that if you choose Yes, all hosts will have to be later '
                    'manually reinstalled from the engine. '
                    '(@VALUES@)[@DEFAULT@]: '
                ),
                prompt=True,
                validValues=(_('Yes'), _('No')),
                caseSensitive=False,
                default=_('No')
            ) == _('Yes').lower()

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        name=ohostedcons.Stages.ANSIBLE_BOOTSTRAP_LOCAL_VM,
    )
    def _closeup(self):
        # TODO: use just env values
        bootstrap_vars = {
            'he_appliance_ova': self.environment[ohostedcons.VMEnv.OVF],
            'he_fqdn': self.environment[
                ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
            ],
            'he_vm_mac_addr': self.environment[
                ohostedcons.VMEnv.MAC_ADDR
            ],
            'he_cloud_init_domain_name': self.environment[
                ohostedcons.CloudInit.INSTANCE_DOMAINNAME
            ],
            'he_cloud_init_host_name': self.environment[
                ohostedcons.CloudInit.INSTANCE_HOSTNAME
            ],
            'he_host_name': self.environment[
                ohostedcons.EngineEnv.APP_HOST_NAME
            ],
            'he_host_address': self.environment[
                ohostedcons.NetworkEnv.HOST_NAME
            ],
            'he_local_vm_dir_path': (
                ohostedcons.FileLocations.LOCAL_VM_DIR_PATH
            ),
            'he_local_vm_dir_prefix': (
                ohostedcons.FileLocations.LOCAL_VM_DIR_PREFIX
            ),
            'he_admin_password': self.environment[
                ohostedcons.EngineEnv.ADMIN_PASSWORD
            ],
            'he_appliance_password': self.environment[
                ohostedcons.CloudInit.ROOTPWD
            ],
            'he_time_zone': self.environment[ohostedcons.CloudInit.VM_TZ],
            'he_cdrom_uuid': self.environment[ohostedcons.VMEnv.CDROM_UUID],
            'he_nic_uuid': self.environment[ohostedcons.VMEnv.NIC_UUID],
            'he_maxvcpus': self.environment[ohostedcons.VMEnv.MAXVCPUS],
            'he_vm_name': ohostedcons.Const.HOSTED_ENGINE_VM_NAME,
            'he_mem_size_MB': self.environment[ohostedcons.VMEnv.MEM_SIZE_MB],
            'he_vcpus': self.environment[ohostedcons.VMEnv.VCPUS],
            'he_emulated_machine': self.environment[
                ohostedcons.VMEnv.EMULATED_MACHINE
            ],
            'he_vm_uuid': self.environment[ohostedcons.VMEnv.LOCAL_VM_UUID],
            'he_vm_etc_hosts': self.environment[
                ohostedcons.CloudInit.VM_ETC_HOSTS
            ],
            'he_root_ssh_pubkey': self.environment[
                ohostedcons.CloudInit.ROOT_SSH_PUBKEY
            ],
            'he_root_ssh_access': self.environment[
                ohostedcons.CloudInit.ROOT_SSH_ACCESS
            ].lower(),
            'he_apply_openscap_profile': self.environment[
                ohostedcons.CloudInit.APPLY_OPENSCAP_PROFILE
            ],
            'he_enable_libgfapi': self.environment[
                ohostedcons.StorageEnv.ENABLE_LIBGFAPI
            ],
            'he_enable_hc_gluster_service': self.environment[
                ohostedcons.StorageEnv.ENABLE_HC_GLUSTER_SERVICE
            ],
            'he_bridge_if': self.environment[
                ohostedcons.NetworkEnv.BRIDGE_IF
            ],
            'he_restore_from_file': self.environment[
                ohostedcons.CoreEnv.RESTORE_FROM_FILE
            ],
            'he_storage_domain_name': self.environment[
                ohostedcons.StorageEnv.STORAGE_DOMAIN_NAME
            ],
            'he_data_center': self.environment[
                ohostedcons.EngineEnv.HOST_DATACENTER_NAME
            ],
            'he_cluster': self.environment[
                ohostedcons.EngineEnv.HOST_CLUSTER_NAME
            ],
            'he_requirements_check_enabled': self.environment[
                ohostedcons.CoreEnv.REQUIREMENTS_CHECK_ENABLED
            ],
            'he_memory_requirements_check_enabled': self.environment[
                ohostedcons.CoreEnv.MEM_REQUIREMENTS_CHECK_ENABLED
            ],
            'he_force_ip4': self.environment[
                ohostedcons.NetworkEnv.FORCE_IPV4
            ],
            'he_force_ip6': self.environment[
                ohostedcons.NetworkEnv.FORCE_IPV6
            ],
            'he_network_test': self.environment[
                ohostedcons.NetworkEnv.NETWORK_TEST
            ],
            'he_tcp_t_address': self.environment[
                ohostedcons.NetworkEnv.NETWORK_TEST_TCP_ADDRESS
            ],
            'he_tcp_t_port': self.environment[
                ohostedcons.NetworkEnv.NETWORK_TEST_TCP_PORT
            ]
        }

        if self.environment[
            ohostedcons.CoreEnv.RENEW_PKI_ON_RESTORE
        ] is not None:
            bootstrap_vars['he_pki_renew_on_restore'] = self.environment[
                ohostedcons.CoreEnv.RENEW_PKI_ON_RESTORE
            ]

        inventory_source = 'localhost,{fqdn}'.format(
            fqdn=self.environment[
                ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
            ]
        )

        self.initial_clean_up(bootstrap_vars, inventory_source)

        ah = ansible_utils.AnsibleHelper(
            tags=ohostedcons.Const.HE_TAG_BOOTSTRAP_LOCAL_VM,
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
            tags=ohostedcons.Const.HE_TAG_INITIAL_CLEAN,
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
            tags=ohostedcons.Const.HE_TAG_FINAL_CLEAN,
            extra_vars={
                'he_local_vm_dir': self.environment[
                    ohostedcons.CoreEnv.LOCAL_VM_DIR
                ],
            },
            inventory_source='localhost,',
        )
        self.logger.info(_('Cleaning temporary resources'))
        r = ah.run()
        self.logger.debug(r)

# vim: expandtab tabstop=4 shiftwidth=4
