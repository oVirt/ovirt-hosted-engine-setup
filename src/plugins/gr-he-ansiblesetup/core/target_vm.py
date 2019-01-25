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


"""Target VM plugin."""


import gettext
import netaddr

from otopi import plugin
from otopi import util

from ovirt_hosted_engine_setup import ansible_utils
from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """Target VM plugin."""

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        name=ohostedcons.Stages.ANSIBLE_CREATE_TARGET_VM,
        after=[
            ohostedcons.Stages.ANSIBLE_CREATE_SD,
            ohostedcons.Stages.ANSIBLE_CUSTOMIZE_DISK_SIZE,
        ],
    )
    def _closeup(self):
        ip_addr = None
        prefix = None
        dnslist = None
        if self.environment[ohostedcons.CloudInit.VM_STATIC_CIDR]:
            ip = netaddr.IPNetwork(
                self.environment[ohostedcons.CloudInit.VM_STATIC_CIDR]
            )
            ip_addr = str(ip.ip)
            prefix = str(ip.prefixlen)
            if self.environment[
                ohostedcons.CloudInit.VM_DNS
            ]:
                dnslist = [
                    d.strip()
                    for d
                    in self.environment[
                        ohostedcons.CloudInit.VM_DNS
                    ].split(',')
                ]

        domain_type = self.environment[
            ohostedcons.StorageEnv.DOMAIN_TYPE
        ]
        if (
            domain_type == ohostedcons.DomainTypes.NFS or
            domain_type == ohostedcons.DomainTypes.GLUSTERFS
        ):
            storage_domain_det = self.environment[
                ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
            ].split(':')
            if len(storage_domain_det) != 2:
                msg = _('Invalid connection path')
                self.logger.error(msg)
                raise RuntimeError(msg)
            storage_domain_address = storage_domain_det[0]
            storage_domain_path = storage_domain_det[1]
        else:
            storage_domain_address = self.environment[
                ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
            ]
            storage_domain_path = None

        target_vm_vars = {
            'he_fqdn': self.environment[
                ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
            ],
            'he_host_name': self.environment[
                ohostedcons.EngineEnv.APP_HOST_NAME
            ],
            'he_host_address': self.environment[
                ohostedcons.NetworkEnv.HOST_NAME
            ],
            'he_admin_password': self.environment[
                ohostedcons.EngineEnv.ADMIN_PASSWORD
            ],
            'he_appliance_password': self.environment[
                ohostedcons.CloudInit.ROOTPWD
            ],
            'he_local_vm_dir': self.environment[
                ohostedcons.CoreEnv.LOCAL_VM_DIR
            ],
            'he_storage_domain_name': self.environment[
                ohostedcons.StorageEnv.STORAGE_DOMAIN_NAME
            ],
            'he_vm_mac_addr': self.environment[
                ohostedcons.VMEnv.MAC_ADDR
            ],
            'he_vm_name': ohostedcons.Const.HOSTED_ENGINE_VM_NAME,
            'he_mem_size_MB': self.environment[ohostedcons.VMEnv.MEM_SIZE_MB],
            'he_vcpus': self.environment[ohostedcons.VMEnv.VCPUS],
            'he_time_zone': self.environment[ohostedcons.CloudInit.VM_TZ],
            'he_bridge_if': self.environment[
                ohostedcons.NetworkEnv.BRIDGE_NAME
            ],
            'he_local_vm_dir_path': self.environment[
                ohostedcons.CoreEnv.LOCAL_VM_DIR
            ],
            'he_storage_domain_addr': storage_domain_address,
            'he_storage_domain_path': storage_domain_path,
            'he_mount_options': self.environment[
                ohostedcons.StorageEnv.MNT_OPTIONS
            ],
            'he_domain_type': self.environment[
                ohostedcons.StorageEnv.DOMAIN_TYPE
            ],
            'he_gateway': self.environment[ohostedcons.NetworkEnv.GATEWAY],
            'he_iscsi_target': self.environment[
                ohostedcons.StorageEnv.ISCSI_TARGET
            ],
            'he_iscsi_username': self.environment[
                ohostedcons.StorageEnv.ISCSI_USER
            ],
            'he_iscsi_password': self.environment[
                ohostedcons.StorageEnv.ISCSI_PASSWORD
            ],
            'he_iscsi_portal_port': self.environment[
                ohostedcons.StorageEnv.ISCSI_PORT
            ],
            'he_iscsi_portal_addr': self.environment[
                ohostedcons.StorageEnv.ISCSI_IP_ADDR
            ],
            'he_iscsi_tpgt': self.environment[
                ohostedcons.StorageEnv.ISCSI_PORTAL
            ],
            'he_lun_id': self.environment[
                ohostedcons.StorageEnv.LUN_ID
            ],
            'he_cdrom_uuid': self.environment[ohostedcons.VMEnv.CDROM_UUID],
            'he_nic_uuid': self.environment[ohostedcons.VMEnv.NIC_UUID],
            'he_maxvcpus': self.environment[ohostedcons.VMEnv.MAXVCPUS],
            'he_emulated_machine': self.environment[
                ohostedcons.VMEnv.EMULATED_MACHINE
            ],
            'he_nfs_version': self.environment[
                ohostedcons.StorageEnv.NFS_VERSION
            ],
            'he_vm_ip_addr': ip_addr,
            'he_vm_ip_prefix': prefix,
            'he_dns_addr': dnslist,
            'he_vm_etc_hosts': self.environment[
                ohostedcons.CloudInit.VM_ETC_HOSTS
            ],
            'he_host_ip': self.environment[
                ohostedcons.CloudInit.HOST_IP
            ],
            'he_disk_size_GB': self.environment[
                ohostedcons.StorageEnv.IMAGE_SIZE_GB
            ],
            'he_smtp_server': self.environment[
                ohostedcons.NotificationsEnv.SMTP_SERVER
            ],
            'he_smtp_port': self.environment[
                ohostedcons.NotificationsEnv.SMTP_PORT
            ],
            'he_source_email': self.environment[
                ohostedcons.NotificationsEnv.SOURCE_EMAIL
            ],
            'he_dest_email': self.environment[
                ohostedcons.NotificationsEnv.DEST_EMAIL
            ],
            'he_appliance_ova': self.environment[ohostedcons.VMEnv.OVF],
            'he_cloud_init_domain_name': self.environment[
                ohostedcons.CloudInit.INSTANCE_DOMAINNAME
            ],
            'he_cloud_init_host_name': self.environment[
                ohostedcons.CloudInit.INSTANCE_HOSTNAME
            ],
            'he_root_ssh_pubkey': self.environment[
                ohostedcons.CloudInit.ROOT_SSH_PUBKEY
            ],
            'he_restore_from_file': self.environment[
                ohostedcons.CoreEnv.RESTORE_FROM_FILE
            ],
            'he_cluster': self.environment[
                ohostedcons.EngineEnv.HOST_CLUSTER_NAME
            ],
        }
        inventory_source = 'localhost, {fqdn}'.format(
            fqdn=self.environment[
                ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
            ]
        )
        ah = ansible_utils.AnsibleHelper(
            playbook_name=ohostedcons.FileLocations.HE_AP_CREATE_VM,
            extra_vars=target_vm_vars,
            inventory_source=inventory_source,
        )
        self.logger.info(_('Creating Target VM'))
        r = ah.run()
        self.logger.debug(r)


# vim: expandtab tabstop=4 shiftwidth=4
