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
import sys


from otopi import util


def ohostedattrsclass(o):
    sys.modules[o.__module__].__dict__.setdefault(
        '__hosted_attrs__', []
    ).append(o)
    return o


class classproperty(property):
    def __get__(self, cls, owner):
        return classmethod(self.fget).__get__(None, owner)()


def ohostedattrs(
    answerfile=False,
):
    class decorator(classproperty):
        def __init__(self, o):
            super(decorator, self).__init__(o)
            self.__hosted_attrs__ = dict(
                answerfile=answerfile,
            )
    return decorator


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
    OVIRT_HOSTED_ENGINE_ANSWERS = os.path.join(
        SYSCONFDIR,
        OVIRT_HOSTED_ENGINE,
        'answers.conf'
    )
    HOSTED_ENGINE_IPTABLES_TEMPLATE = os.path.join(
        DATADIR,
        OVIRT_HOSTED_ENGINE_SETUP,
        'templates',
        'iptables.default.in'
    )
    HOSTED_ENGINE_IPTABLES_EXAMPLE = os.path.join(
        SYSCONFDIR,
        OVIRT_HOSTED_ENGINE,
        'iptables.example'
    )
    HOSTED_ENGINE_FIREWALLD_EXAMPLE_DIR = os.path.join(
        SYSCONFDIR,
        OVIRT_HOSTED_ENGINE,
        'firewalld'
    )
    HOSTED_ENGINE_FIREWALLD_TEMPLATES_DIR = os.path.join(
        DATADIR,
        OVIRT_HOSTED_ENGINE_SETUP,
        'templates',
        'firewalld',
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
    LIBVIRT_CA_CERT = os.path.join(
        SYSCONFDIR,
        'pki',
        'vdsm',
        'libvirt-spice',
        'ca-cert.pem'
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
    FIRST_HOST_ID = 1
    HA_AGENT_SERVICE = 'ovirt-ha-agent'
    HA_BROCKER_SERVICE = 'ovirt-ha-broker'


@util.export
@util.codegen
class CoreEnv(object):
    ANSWER_FILE = 'OVEHOSTED_CORE/answerFile'
    REQUIREMENTS_CHECK_ENABLED = 'OVEHOSTED_CORE/checkRequirements'
    ADDITIONAL_HOST_ENABLED = 'OVEHOSTED_CORE/additionalHostEnabled'
    IS_ADDITIONAL_HOST = 'OVEHOSTED_CORE/isAdditionalHost'
    TEMPDIR = 'OVEHOSTED_CORE/tempDir'
    DEPLOY_PROCEED = 'OVEHOSTED_CORE/deployProceed'
    SCREEN_PROCEED = 'OVEHOSTED_CORE/screenProceed'


@util.export
@util.codegen
@ohostedattrsclass
class NetworkEnv(object):

    @ohostedattrs(
        answerfile=True,
    )
    def BRIDGE_IF(self):
        return 'OVEHOSTED_NETWORK/bridgeIf'

    @ohostedattrs(
        answerfile=True,
    )
    def OVIRT_HOSTED_ENGINE_FQDN(self):
        return 'OVEHOSTED_NETWORK/fqdn'
    FQDN_REVERSE_VALIDATION = 'OVEHOSTED_NETWORK/fqdnReverseValidation'

    @ohostedattrs(
        answerfile=True,
    )
    def BRIDGE_NAME(self):
        return 'OVEHOSTED_NETWORK/bridgeName'

    @ohostedattrs(
        answerfile=True,
    )
    def FIREWALL_MANAGER(self):
        return 'OVEHOSTED_NETWORK/firewallManager'

    @ohostedattrs(
        answerfile=True,
    )
    def GATEWAY(self):
        return 'OVEHOSTED_NETWORK/gateway'

    FIREWALLD_SERVICES = 'OVEHOSTED_NETWORK/firewalldServices'
    FIREWALLD_SUBST = 'OVEHOSTED_NETWORK/firewalldSubst'


@util.export
@util.codegen
class HostEnv(object):

    ROOT_PASSWORD = 'OVEHOSTED_HOST/rootPassword'


@util.export
@util.codegen
@ohostedattrsclass
class EngineEnv(object):

    ADMIN_PASSWORD = 'OVEHOSTED_ENGINE/adminPassword'

    @ohostedattrs(
        answerfile=True,
    )
    def APP_HOST_NAME(self):
        return 'OVEHOSTED_ENGINE/appHostName'


@util.export
@util.codegen
@ohostedattrsclass
class StorageEnv(object):
    @ohostedattrs(
        answerfile=True,
    )
    def HOST_ID(self):
        return 'OVEHOSTED_STORAGE/hostID'

    @ohostedattrs(
        answerfile=True,
    )
    def STORAGE_DOMAIN_CONNECTION(self):
        return 'OVEHOSTED_STORAGE/storageDomainConnection'

    @ohostedattrs(
        answerfile=True,
    )
    def STORAGE_DOMAIN_NAME(self):
        return 'OVEHOSTED_STORAGE/storageDomainName'

    @ohostedattrs(
        answerfile=True,
    )
    def STORAGE_DATACENTER_NAME(self):
        return 'OVEHOSTED_STORAGE/storageDatacenterName'

    @ohostedattrs(
        answerfile=True,
    )
    def CONNECTION_UUID(self):
        return 'OVEHOSTED_STORAGE/connectionUUID'

    @ohostedattrs(
        answerfile=True,
    )
    def SD_UUID(self):
        return 'OVEHOSTED_STORAGE/sdUUID'

    @ohostedattrs(
        answerfile=True,
    )
    def SP_UUID(self):
        return 'OVEHOSTED_STORAGE/spUUID'

    @ohostedattrs(
        answerfile=True,
    )
    def IMG_UUID(self):
        return 'OVEHOSTED_STORAGE/imgUUID'

    @ohostedattrs(
        answerfile=True,
    )
    def STORAGE_TYPE(self):
        return 'OVEHOSTED_STORAGE/storageType'

    @ohostedattrs(
        answerfile=True,
    )
    def VOL_UUID(self):
        return 'OVEHOSTED_STORAGE/volUUID'

    @ohostedattrs(
        answerfile=True,
    )
    def IMAGE_SIZE_GB(self):
        return 'OVEHOSTED_STORAGE/imgSizeGB'

    IMAGE_DESC = 'OVEHOSTED_STORAGE/imgDesc'

    @ohostedattrs(
        answerfile=True,
    )
    def DOMAIN_TYPE(self):
        return 'OVEHOSTED_STORAGE/domainType'


@util.export
@util.codegen
@ohostedattrsclass
class VMEnv(object):
    @ohostedattrs(
        answerfile=True,
    )
    def VM_UUID(self):
        return 'OVEHOSTED_VM/vmUUID'

    @ohostedattrs(
        answerfile=True,
    )
    def MEM_SIZE_MB(self):
        return 'OVEHOSTED_VM/vmMemSizeMB'

    @ohostedattrs(
        answerfile=True,
    )
    def VCPUS(self):
        return 'OVEHOSTED_VM/vmVCpus'

    MAC_ADDR = 'OVEHOSTED_VM/vmMACAddr'

    @ohostedattrs(
        answerfile=True,
    )
    def BOOT(self):
        return 'OVEHOSTED_VM/vmBoot'

    @ohostedattrs(
        answerfile=True,
    )
    def CDROM(self):
        return 'OVEHOSTED_VM/vmCDRom'

    @ohostedattrs(
        answerfile=True,
    )
    def OVF(self):
        return 'OVEHOSTED_VM/ovfArchive'

    NAME = 'OVEHOSTED_VM/vmName'
    VM_PASSWD = 'OVEHOSTED_VDSM/passwd'
    VM_PASSWD_VALIDITY_SECS = 'OVEHOSTED_VDSM/passwdValiditySecs'
    SUBST = 'OVEHOSTED_VM/subst'

    @ohostedattrs(
        answerfile=True,
    )
    def CONSOLE_TYPE(self):
        return 'OVEHOSTED_VDSM/consoleType'


@util.export
@util.codegen
@ohostedattrsclass
class VDSMEnv(object):
    VDSMD_SERVICE = 'OVEHOSTED_VDSM/serviceName'
    VDSM_UID = 'OVEHOSTED_VDSM/vdsmUid'
    KVM_GID = 'OVEHOSTED_VDSM/kvmGid'
    VDS_CLI = 'OVEHOSTED_VDSM/vdsClient'

    @ohostedattrs(
        answerfile=True,
    )
    def PKI_SUBJECT(self):
        return 'OVEHOSTED_VDSM/pkiSubject'

    @ohostedattrs(
        answerfile=True,
    )
    def SPICE_SUBJECT(self):
        return 'OVEHOSTED_VDSM/spicePkiSubject'

    VDSM_CPU = 'OVEHOSTED_VDSM/cpu'
    USE_SSL = 'OVEHOSTED_VDSM/useSSL'


@util.export
@util.codegen
class Stages(object):
    CONFIG_BOOT_DEVICE = 'ohosted.boot.configuration.available'
    CONFIG_STORAGE = 'ohosted.storage.configuration.available'
    CONFIG_ADDITIONAL_HOST = 'ohosted.core.additional.host'
    CONFIG_OVF_IMPORT = 'ohosted.configuration.ovf'
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
    OS_INSTALLED = 'ohosted.vm.state.os.installed'
    INSTALLED_VM_RUNNING = 'ohosted.vm.state.os.installed.running'
    ENGINE_ALIVE = 'ohosted.engine.alive'
    NET_FIREWALL_MANAGER_AVAILABLE = \
        'ohosted.network.firewallmanager.available'
    NET_FIREWALL_MANAGER_PROCESS_TEMPLATES = \
        'ohosted.network.firewallmanager.templates.available'
    VDSMD_CONF_LOADED = 'ohosted.vdsm.conf.loaded'
    HOST_ADDED = 'ohosted.engine.host.added'
    HA_START = 'ohosted.engine.ha.start'


@util.export
@util.codegen
class Defaults(object):
    DEFAULT_STORAGE_DOMAIN_NAME = 'hosted_storage'
    DEFAULT_STORAGE_DATACENTER_NAME = 'hosted_datacenter'
    DEFAULT_VDSMD_SERVICE = 'vdsmd'
    DEFAULT_IMAGE_DESC = 'Hosted Engine Image'
    DEFAULT_IMAGE_SIZE_GB = 25  # based on minimum requirements.
    DEFAULT_MEM_SIZE_MB = 4096  # based on minimum requirements.
    DEFAULT_BOOT = 'cdrom'  # boot device - drive C or cdrom or pxe
    DEFAULT_CDROM = '/dev/null'
    DEFAULT_NAME = 'oVirt Hosted Engine'
    DEFAULT_BRIDGE_IF = 'em1'
    DEFAULT_BRIDGE_NAME = 'ovirtmgmt'
    DEFAULT_PKI_SUBJECT = '/C=EN/L=Test/O=Test/CN=Test'
    DEFAULT_VM_PASSWD_VALIDITY_SECS = "10800"  # 3 hours to for engine install
    DEFAULT_VM_VCPUS = 2  # based on minimum requirements.


@util.export
@util.codegen
class Confirms(object):
    DEPLOY_PROCEED = 'DEPLOY_PROCEED'
    CPU_PROCEED = 'CPU_PROCEED'
    DISK_PROCEED = 'DISK_PROCEED'
    MEMORY_PROCEED = 'MEMORY_PROCEED'
    SCREEN_PROCEED = 'SCREEN_PROCEED'


# vim: expandtab tabstop=4 shiftwidth=4
