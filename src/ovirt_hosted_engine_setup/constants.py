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


"""Constants."""


import os


from otopi import util


@util.export
@util.codegen
class FileLocations(object):
    #TODO: fix paths while packaging
    SYSCONFDIR = '/etc'
    LOCALSTATEDIR = '/var'
    DATADIR = '/usr/share'
    LIBEXECDIR = '/usr/libexec'
    OVIRT_HOSTED_ENGINE = 'ovirt-hosted-engine'
    OVIRT_HOSTED_ENGINE_SETUP = 'ovirt-hosted-engine-setup'
    VDS_CLIENT_DIR = os.path.join(
        DATADIR,
        'vdsm',
    )
    ENGINE_VM_TEMPLATE = os.path.join(
        DATADIR,
        OVIRT_HOSTED_ENGINE_SETUP,
        'templates',
        'vm.conf.in'
    )
    ENGINE_VM_CONF = os.path.join(
        SYSCONFDIR,
        OVIRT_HOSTED_ENGINE,
        'vm.conf'
    )
    OVIRT_HOSTED_ENGINE_TEMPLATE = os.path.join(
        DATADIR,
        OVIRT_HOSTED_ENGINE_SETUP,
        'templates',
        'hosted-engine.conf.in'
    )
    OVIRT_HOSTED_ENGINE_SETUP_CONF = os.path.join(
        SYSCONFDIR,
        OVIRT_HOSTED_ENGINE,
        'hosted-engine.conf'
    )
    VDSM_GEN_CERTS = os.path.join(
        LIBEXECDIR,
        'vdsm',
        'vdsm-gencerts.sh'
    )
    VDSMCERT = os.path.join(
        SYSCONFDIR,
        'pki',
        'vdsm',
        'certs'
        'vdsmcert.pem'
    )
    VDSM_CONF = os.path.join(
        SYSCONFDIR,
        'vdsm',
        'vdsm.conf'
    )
    LIBVIRT_SERVER_CERT = os.path.join(
        SYSCONFDIR,
        'pki',
        'vdsm',
        'libvirt-spice',
        'server-cert.pem'
    )
    LIBVIRT_QEMU_CONF = os.path.join(
        SYSCONFDIR,
        'libvirt',
        'qemu.conf'
    )


@util.export
@util.codegen
class Const(object):
    MINIMUM_SPACE_STORAGEDOMAIN_MB = 20480


@util.export
@util.codegen
class NetworkEnv(object):
    BRIDGE_IF = 'OVEHOSTED_NETWORK/bridgeIf'
    BRIDGE_NAME = 'OVEHOSTED_NETWORK/bridgeName'
    OVIRT_HOSTED_ENGINE_FQDN = 'OVEHOSTED_NETWORK/fqdn'


@util.export
@util.codegen
class HostEnv(object):
    ROOT_PASSWORD = 'OVEHOSTED_HOST/rootPassword'


@util.export
@util.codegen
class StorageEnv(object):
    STORAGE_DOMAIN_CONNECTION = 'OVEHOSTED_STORAGE/storageDomainConnection'
    STORAGE_DOMAIN_NAME = 'OVEHOSTED_STORAGE/storageDomainName'
    STORAGE_DATACENTER_NAME = 'OVEHOSTED_STORAGE/storageDatacenterName'
    CONNECTION_UUID = 'OVEHOSTED_STORAGE/connectionUUID'
    SD_UUID = 'OVEHOSTED_STORAGE/sdUUID'
    SP_UUID = 'OVEHOSTED_STORAGE/spUUID'
    IMG_UUID = 'OVEHOSTED_STORAGE/imgUUID'
    VOL_UUID = 'OVEHOSTED_STORAGE/volUUID'
    IMAGE_SIZE_GB = 'OVEHOSTED_STORAGE/imgSizeGB'
    IMAGE_DESC = 'OVEHOSTED_STORAGE/imgDesc'
    DOMAIN_TYPE = 'OVEHOSTED_STORAGE/domainType'


@util.export
@util.codegen
class VMEnv(object):
    VM_UUID = 'OVEHOSTED_VM/vmUUID'
    MEM_SIZE_MB = 'OVEHOSTED_VM/vmMemSizeMB'
    MAC_ADDR = 'OVEHOSTED_VM/vmMACAddr'
    BOOT = 'OVEHOSTED_VM/vmBoot'
    CDROM = 'OVEHOSTED_VM/vmCDRom'
    NAME = 'OVEHOSTED_VM/vmName'
    VM_PASSWD = 'OVEHOSTED_VDSM/passwd'
    VM_PASSWD_VALIDITY_SECS = 'OVEHOSTED_VDSM/passwdValiditySecs'


@util.export
@util.codegen
class VDSMEnv(object):
    VDSMD_SERVICE = 'OVEHOSTED_VDSM/serviceName'
    VDSM_UID = 'OVEHOSTED_VDSM/vdsmUid'
    KVM_GID = 'OVEHOSTED_VDSM/kvmGid'
    VDS_CLI = 'OVEHOSTED_VDSM/vdsClient'
    PKI_SUBJECT = 'OVEHOSTED_VDSM/pkiSubject'
    VDSM_CPU = 'OVEHOSTED_VDSM/cpu'


@util.export
@util.codegen
class Stages(object):
    CONFIG_STORAGE = 'ohosted.storage.configuration.available'
    VDSMD_START = 'ohosted.vdsm.started'
    VDSMD_PKI = 'ohosted.vdsm.pki.available'
    VDSMD_CONFIGURED = 'ohosted.vdsm.configured'
    STORAGE_AVAILABLE = 'ohosted.storage.available'
    VM_IMAGE_AVAILABLE = 'ohosted.vm.image.available'
    VM_CONFIGURED = 'ohosted.vm.state.configured'
    VM_RUNNING = 'ohosted.vm.state.running'
    BRIDGE_AVAILABLE = 'ohosted.network.bridge.available'
    LIBVIRT_CONFIGURED = 'ohosted.libvirt.configured'
    SAVE_CONFIG = 'ohosted.save.config'
    SSHD_START = 'ohosted.sshd.started'
    ENGINE_ALIVE = 'ohosted.engine.alive'


@util.export
@util.codegen
class Defaults(object):
    DEFAULT_STORAGE_DOMAIN_NAME = 'hosted_storage'
    DEFAULT_STORAGE_DATACENTER_NAME = 'hosted_datacenter'
    DEFAULT_VDSMD_SERVICE = 'vdsmd'
    DEFAULT_IMAGE_DESC = 'Hosted Engine Image'
    DEFAULT_IMAGE_SIZE_GB = 20  # based on minimum requirements.
    DEFAULT_MEM_SIZE_MB = 4096  # based on minimum requirements.
    DEFAULT_BOOT = 'cdrom'  # boot device - drive C or cdrom or pxe
    DEFAULT_CDROM = '/dev/null'
    DEFAULT_NAME = 'oVirt Hosted Engine'
    DEFAULT_BRIDGE_IF = 'em1'
    DEFAULT_BRIDGE_NAME = 'ovirtmgmt'
    DEFAULT_PKI_SUBJECT = '/C=EN/L=Test/O=Test/CN=Test'
    DEFAULT_VM_PASSWD_VALIDITY_SECS = "10800"  # 3 hours to for engine install


@util.export
@util.codegen
class Confirms(object):
    DEPLOY_PROCEED = 'DEPLOY_PROCEED'


# vim: expandtab tabstop=4 shiftwidth=4
