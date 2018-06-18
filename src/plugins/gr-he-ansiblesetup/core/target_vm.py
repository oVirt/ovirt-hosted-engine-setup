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
            'FQDN': self.environment[
                ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
            ],
            'HOST_ADDRESS': self.environment[
                ohostedcons.NetworkEnv.HOST_NAME
            ],
            'HOST_NAME': self.environment[
                ohostedcons.EngineEnv.APP_HOST_NAME
            ],
            'ADMIN_PASSWORD': self.environment[
                ohostedcons.EngineEnv.ADMIN_PASSWORD
            ],
            'APPLIANCE_PASSWORD': self.environment[
                ohostedcons.CloudInit.ROOTPWD
            ],
            'STORAGE_DOMAIN_NAME': self.environment[
                ohostedcons.StorageEnv.STORAGE_DOMAIN_NAME
            ],
            'VM_MAC_ADDR': self.environment[
                ohostedcons.VMEnv.MAC_ADDR
            ],
            'VM_NAME': ohostedcons.Const.HOSTED_ENGINE_VM_NAME,
            'MEM_SIZE': self.environment[ohostedcons.VMEnv.MEM_SIZE_MB],
            'VCPUS': self.environment[ohostedcons.VMEnv.VCPUS],
            'CPU_SOCKETS': '1',
            'TIME_ZONE': self.environment[ohostedcons.CloudInit.VM_TZ],
            'BRIDGE': self.environment[ohostedcons.NetworkEnv.BRIDGE_NAME],
            'LOCAL_VM_DIR': self.environment[ohostedcons.CoreEnv.LOCAL_VM_DIR],
            'STORAGE_DOMAIN_ADDR': storage_domain_address,
            'STORAGE_DOMAIN_PATH': storage_domain_path,
            'MOUNT_OPTIONS': self.environment[
                ohostedcons.StorageEnv.MNT_OPTIONS
            ],
            'DOMAIN_TYPE': self.environment[
                ohostedcons.StorageEnv.DOMAIN_TYPE
            ],
            'GATEWAY': self.environment[ohostedcons.NetworkEnv.GATEWAY],
            'ISCSI_TARGET': self.environment[
                ohostedcons.StorageEnv.ISCSI_TARGET
            ],
            'ISCSI_USERNAME': self.environment[
                ohostedcons.StorageEnv.ISCSI_USER
            ],
            'ISCSI_PASSWORD': self.environment[
                ohostedcons.StorageEnv.ISCSI_PASSWORD
            ],
            'ISCSI_PORTAL_PORT': self.environment[
                ohostedcons.StorageEnv.ISCSI_PORT
            ],
            'ISCSI_PORTAL_ADDR': self.environment[
                ohostedcons.StorageEnv.ISCSI_IP_ADDR
            ],
            'ISCSI_TPGT': self.environment[
                ohostedcons.StorageEnv.ISCSI_PORTAL
            ],
            'LUN_ID': self.environment[
                ohostedcons.StorageEnv.LUN_ID
            ],
            'CONSOLE_TYPE': 'vnc',
            'CDROM_UUID': self.environment[ohostedcons.VMEnv.CDROM_UUID],
            'CDROM': '',
            'NIC_UUID': self.environment[ohostedcons.VMEnv.NIC_UUID],
            'VIDEO_DEVICE': 'vga',
            'GRAPHICS_DEVICE': 'vnc',
            'MAXVCPUS': self.environment[ohostedcons.VMEnv.MAXVCPUS],
            'EMULATED_MACHINE': self.environment[
                ohostedcons.VMEnv.EMULATED_MACHINE
            ],
            'NFS_VERSION': self.environment[
                ohostedcons.StorageEnv.NFS_VERSION
            ],
            'VM_IP_ADDR': ip_addr,
            'VM_IP_PREFIX': prefix,
            'DNS_ADDR': dnslist,
            'VM_ETC_HOSTS': self.environment[
                ohostedcons.CloudInit.VM_ETC_HOSTS
            ],
            'HOST_IP': self.environment[
                ohostedcons.CloudInit.HOST_IP
            ],
            'DISK_SIZE': self.environment[
                ohostedcons.StorageEnv.IMAGE_SIZE_GB
            ],
            'SMTP_SERVER': self.environment[
                ohostedcons.NotificationsEnv.SMTP_SERVER
            ],
            'SMTP_PORT': self.environment[
                ohostedcons.NotificationsEnv.SMTP_PORT
            ],
            'SOURCE_EMAIL': self.environment[
                ohostedcons.NotificationsEnv.SOURCE_EMAIL
            ],
            'DEST_EMAIL': self.environment[
                ohostedcons.NotificationsEnv.DEST_EMAIL
            ],
            'APPLIANCE_OVA': self.environment[ohostedcons.VMEnv.OVF],
            'CLOUD_INIT_DOMAIN_NAME': self.environment[
                ohostedcons.CloudInit.INSTANCE_DOMAINNAME
            ],
            'CLOUD_INIT_HOST_NAME': self.environment[
                ohostedcons.CloudInit.INSTANCE_HOSTNAME
            ],
            'ROOT_SSH_PUBKEY': self.environment[
                ohostedcons.CloudInit.ROOT_SSH_PUBKEY
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
