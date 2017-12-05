#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2013-2017 Red Hat, Inc.
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


import gettext
import os
import sys

from otopi import util

from ovirt_hosted_engine_setup import config


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


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
    summary=False,
    description=None,
):
    class decorator(classproperty):
        def __init__(self, o):
            super(decorator, self).__init__(o)
            self.__hosted_attrs__ = dict(
                answerfile=answerfile,
                summary=summary,
                description=description,
            )
    return decorator


@util.export
@util.codegen
class FileSystemTypes(object):
    NFS = 'nfs'
    GLUSTERFS = 'glusterfs'


@util.export
@util.codegen
class DomainTypes(object):
    NFS = 'nfs'
    NFS3 = 'nfs3'
    NFS4 = 'nfs4'
    GLUSTERFS = 'glusterfs'
    ISCSI = 'iscsi'
    FC = 'fc'


@util.export
@util.codegen
class NfsVersions(object):
    AUTO = 'auto'
    V3 = 'v3'
    V4 = 'v4'
    V4_1 = 'v4_1'
    V4_2 = 'v4_2'


@util.export
@util.codegen
class VolumeTypes(object):
    UNKNOWN_VOL = 0
    PREALLOCATED_VOL = 1
    SPARSE_VOL = 2


@util.export
@util.codegen
class VolumeFormat(object):
    UNKNOWN_FORMAT = 3
    COW_FORMAT = 4
    RAW_FORMAT = 5


@util.export
@util.codegen
class VDSMConstants(object):
    NFS_DOMAIN = 1
    FC_DOMAIN = 2
    ISCSI_DOMAIN = 3
    POSIXFS_DOMAIN = 6
    GLUSTERFS_DOMAIN = 7
    DATA_DOMAIN = 1


@util.export
@util.codegen
class StorageDomainType(object):
    UNKNOWN = 'UNKNOWN'
    NFS = 'NFS'
    FCP = 'FCP'
    ISCSI = 'ISCSI'
    LOCALFS = 'LOCALFS'
    CIFS = 'CIFS'
    SHAREDFS = 'SHAREDFS'
    GLUSTERFS = 'GLUSTERFS'


@util.export
@util.codegen
class FileLocations(object):
    SYSCONFDIR = '/etc'
    DATADIR = '/usr/share'
    DOCDIR = config.DOCDIR
    LIBEXECDIR = '/usr/libexec'
    SD_MOUNT_PARENT_DIR = '/rhev/data-center/mnt'
    LOCALTIME = '/etc/localtime'
    TZ_PARENT_DIR = '/usr/share/zoneinfo'
    OVIRT_HOSTED_ENGINE = 'ovirt-hosted-engine'
    OVIRT_HOSTED_ENGINE_HA = 'ovirt-hosted-engine-ha'
    OVIRT_HOSTED_ENGINE_SETUP = 'ovirt-hosted-engine-setup'
    OVIRT_HOSTED_ENGINE_SETUP_LOGDIR = os.path.join(
        config.LOCALSTATEDIR,
        'log',
        OVIRT_HOSTED_ENGINE_SETUP,
    )

    OVIRT_HOSTED_ENGINE_SETUP_CONFIG_FILE = os.path.join(
        config.SYSCONFDIR,
        '%s.conf' % OVIRT_HOSTED_ENGINE_SETUP,
    )

    OVIRT_HOST_DEPLOY_CONF = os.path.join(
        config.SYSCONFDIR,
        'ovirt-host-deploy.conf.d',
    )

    ENGINE_VM_TEMPLATE = os.path.join(
        config.DATADIR,
        OVIRT_HOSTED_ENGINE_SETUP,
        'templates',
        'vm.conf.in'
    )
    ENGINE_VM_CONF = os.path.join(
        config.LOCALSTATEDIR,
        'run',
        OVIRT_HOSTED_ENGINE_HA,
        'vm.conf'
    )
    README_APPLIANCE = os.path.join(
        DOCDIR,
        'readme.appliance'
    )
    README_ROLLBACK = os.path.join(
        DOCDIR,
        'readme.rollback'
    )
    # TODO: Only for upgrades, remove after 3.6
    PREV_ENGINE_VM_CONF = os.path.join(
        config.SYSCONFDIR,
        OVIRT_HOSTED_ENGINE,
        'vm.conf'
    )
    OVIRT_APPLIANCES_DESC_DIR = os.path.join(
        config.SYSCONFDIR,
        OVIRT_HOSTED_ENGINE,
    )
    OVIRT_APPLIANCES_DESC_FILENAME_TEMPLATE = '*-appliance.conf'
    OVIRT_HOSTED_ENGINE_TEMPLATE = os.path.join(
        config.DATADIR,
        OVIRT_HOSTED_ENGINE_SETUP,
        'templates',
        'hosted-engine.conf.in'
    )
    OVIRT_HOSTED_ENGINE_SETUP_CONF = os.path.join(
        config.SYSCONFDIR,
        OVIRT_HOSTED_ENGINE,
        'hosted-engine.conf'
    )
    OVIRT_HOSTED_ENGINE_ANSWERS = os.path.join(
        config.SYSCONFDIR,
        OVIRT_HOSTED_ENGINE,
        'answers.conf'
    )
    OVIRT_HOSTED_ENGINE_LB_DIR = os.path.join(
        config.LOCALSTATEDIR,
        'lib',
        OVIRT_HOSTED_ENGINE_SETUP,
    )
    OVIRT_HOSTED_ENGINE_ANSWERS_ARCHIVE_DIR = os.path.join(
        config.LOCALSTATEDIR,
        'lib',
        OVIRT_HOSTED_ENGINE_SETUP,
        'answers'
    )
    HOSTED_ENGINE_IPTABLES_TEMPLATE = os.path.join(
        config.DATADIR,
        OVIRT_HOSTED_ENGINE_SETUP,
        'templates',
        'iptables.default.in'
    )
    HOSTED_ENGINE_IPTABLES_EXAMPLE = os.path.join(
        config.SYSCONFDIR,
        OVIRT_HOSTED_ENGINE,
        'iptables.example'
    )
    HOSTED_ENGINE_FIREWALLD_EXAMPLE_DIR = os.path.join(
        config.SYSCONFDIR,
        OVIRT_HOSTED_ENGINE,
        'firewalld'
    )
    HOSTED_ENGINE_FIREWALLD_TEMPLATES_DIR = os.path.join(
        config.DATADIR,
        OVIRT_HOSTED_ENGINE_SETUP,
        'templates',
        'firewalld',
    )

    VDSM_GEN_CERTS = os.path.join(
        LIBEXECDIR,
        'vdsm',
        'vdsm-gencerts.sh'
    )
    VDSM_CA_CERT = os.path.join(
        SYSCONFDIR,
        'pki',
        'vdsm',
        'certs',
        'cacert.pem'
    )
    SYS_CA_CERT = os.path.join(
        SYSCONFDIR,
        'pki',
        'CA',
        'cacert.pem'
    )
    SYS_CUSTOMCA_CERT = os.path.join(
        SYSCONFDIR,
        'pki',
        'CA',
        'ovirtcustomcacert.pem'
    )
    VDSMCERT = os.path.join(
        SYSCONFDIR,
        'pki',
        'vdsm',
        'certs',
        'vdsmcert.pem'
    )
    VDSMKEY = os.path.join(
        SYSCONFDIR,
        'pki',
        'vdsm',
        'keys',
        'vdsmkey.pem'
    )
    VDSM_CONF = os.path.join(
        SYSCONFDIR,
        'vdsm',
        'vdsm.conf'
    )
    LIBVIRT_SPICE_SERVER_CERT = os.path.join(
        SYSCONFDIR,
        'pki',
        'vdsm',
        'libvirt-spice',
        'server-cert.pem'
    )
    LIBVIRT_SPICE_CA_CERT = os.path.join(
        SYSCONFDIR,
        'pki',
        'vdsm',
        'libvirt-spice',
        'ca-cert.pem'
    )
    LIBVIRT_PKI = os.path.join(
        SYSCONFDIR,
        'pki',
        'libvirt'
    )
    LIBVIRT_PKI_PRIVATE = os.path.join(
        LIBVIRT_PKI,
        'private',
    )
    LIBVIRT_CLIENT_CERT = os.path.join(
        LIBVIRT_PKI,
        'clientcert.pem'
    )
    LIBVIRT_CLIENT_KEY = os.path.join(
        LIBVIRT_PKI_PRIVATE,
        'clientkey.pem'
    )
    LIBVIRT_SERVER_CERT = os.path.join(
        LIBVIRT_PKI,
        'servercert.pem'
    )
    LIBVIRT_SERVER_KEY = os.path.join(
        LIBVIRT_PKI_PRIVATE,
        'serverkey.pem'
    )
    LIBVIRT_QEMU_CONF = os.path.join(
        SYSCONFDIR,
        'libvirt',
        'qemu.conf'
    )
    ENGINE_HA_CONFDIR = os.path.join(
        SYSCONFDIR,
        OVIRT_HOSTED_ENGINE_HA
    )
    NOTIFY_CONF_FILE = os.path.join(  # TODO: Upgrades only, remove after 3.6
        ENGINE_HA_CONFDIR,
        'broker.conf'
    )
    HECONFD_VERSION = 'version'
    HECONFD_ANSWERFILE = 'fhanswers.conf'
    HECONFD_HECONF = 'hosted-engine.conf'
    HECONFD_BROKER_CONF = 'broker.conf'
    HECONFD_VM_CONF = 'vm.conf'

    LOCAL_VM_DIR = '/var/tmp/localvm'

    HOSTED_ENGINE_ANSIBLE_PATH = os.path.join(
        config.DATADIR,
        OVIRT_HOSTED_ENGINE_SETUP,
        'ansible',
    )

    HE_AP_CLEAN_ENVIRONMENT = 'clean_environment.yml'
    HE_AP_BOOTSTRAP_LOCAL_VM = 'bootstrap_local_vm.yml'
    HE_AP_CREATE_SD = 'create_storage_domain.yml'
    HE_AP_CREATE_VM = 'create_target_vm.yml'
    HE_AP_ISCSI_DISCOVER = 'iscsi_discover.yml'
    HE_AP_ISCSI_GETDEVICES = 'iscsi_getdevices.yml'
    HE_AP_FC_GETDEVICES = 'fc_getdevices.yml'


@util.export
@util.codegen
class Const(object):
    MINIMUM_SPACE_STORAGEDOMAIN_MB = 20480
    FIRST_HOST_ID = 1
    HA_AGENT_SERVICE = 'ovirt-ha-agent'
    HA_BROCKER_SERVICE = 'ovirt-ha-broker'
    HOSTED_ENGINE_VM_NAME = 'HostedEngine'
    CONF_IMAGE_DESC = 'HostedEngineConfigurationImage'
    # On block devices the VM image should be preallocated into the VG
    # The VG by itself introduces some overhead that we need to take care of
    # verifying  the image size before creating them
    # TODO get this values from VDSM APIs instead of hardcoding it
    # TODO now the overhead is > 4GBiB cause we are creating a storage domain
    # maybe we can do better
    STORAGE_DOMAIN_OVERHEAD_GIB = 5
    METADATA_CHUNK_SIZE = 4096
    MAX_HOST_ID = 250
    HA_NOTIF_SMTP_SERVER = 'smtp-server'
    HA_NOTIF_SMTP_PORT = 'smtp-port'
    HA_NOTIF_SMTP_SOURCE_EMAIL = 'source-email'
    HA_NOTIF_SMTP_DEST_EMAILS = 'destination-emails'
    BLANK_UUID = '00000000-0000-0000-0000-000000000000'
    VDSCLI_SSL_TIMEOUT = 900
    CLOUD_INIT_GENERATE = 'generate'
    CLOUD_INIT_SKIP = 'skip'
    CLOUD_INIT_EXISTING = 'existing'
    CLOUD_INIT_APPLIANCEANSWERS = '/root/ovirt-engine-answers'
    CLOUD_INIT_HEANSWERS = '/root/heanswers.conf'
    OVIRT_HE_CHANNEL_NAME = 'org.ovirt.hosted-engine-setup.0'
    OVIRT_HE_CHANNEL_PATH = '/var/lib/libvirt/qemu/channels/'
    VIRTIO_PORTS_PATH = '/dev/virtio-ports/'
    E_SETUP_SUCCESS_STRING = 'HE_APPLIANCE_ENGINE_SETUP_SUCCESS'
    E_SETUP_FAIL_STRING = 'HE_APPLIANCE_ENGINE_SETUP_FAIL'
    E_RESTORE_SUCCESS_STRING = 'HE_APPLIANCE_ENGINE_RESTORE_SUCCESS'
    E_RESTORE_FAIL_STRING = 'HE_APPLIANCE_ENGINE_RESTORE_FAIL'
    # sync with engine table storage_server_connections
    # (packaging/dbscripts/create_tables.sql)
    MAX_STORAGE_USERNAME_LENGTH = 50
    MAX_STORAGE_PASSWORD_LENGTH = 50
    UPGRADE_SUPPORTED_SOURCES = ['3.6']
    UPGRADE_SUPPORTED_TARGETS = ['4.0']
    UPGRADE_REQUIRED_CLUSTER_V = ['3.6', '4.0', '4.1']
    BACKUP_DISK_PREFIX = 'hosted-engine-backup-'
    APPLIANCE_RPM_NAME = '%s-appliance' % config.APPLIANCE_RPM_PREFIX
    APPLIANCE40_RPM_NAME = '%s-appliance' % config.APPLIANCE40_RPM_PREFIX
    VM_LIVELINESS_CHECK_TIMEOUT = 600
    ANSIBLE_R_OTOPI_PREFIX = 'otopi_'


@util.export
@util.codegen
@ohostedattrsclass
class CoreEnv(object):
    USER_ANSWER_FILE = 'OVEHOSTED_CORE/userAnswerFile'
    ETC_ANSWER_FILE = 'OVEHOSTED_CORE/etcAnswerFile'
    REQUIREMENTS_CHECK_ENABLED = 'OVEHOSTED_CORE/checkRequirements'
    UPGRADING_APPLIANCE = 'OVEHOSTED_CORE/upgradingAppliance'
    ANSIBLE_DEPLOYMENT = 'OVEHOSTED_CORE/ansibleDeployment'
    ROLLBACK_UPGRADE = 'OVEHOSTED_CORE/rollbackUpgrade'
    TEMPDIR = 'OVEHOSTED_CORE/tempDir'

    @ohostedattrs(
        answerfile=True,
    )
    def DEPLOY_PROCEED(self):
        return 'OVEHOSTED_CORE/deployProceed'

    @ohostedattrs(
        answerfile=True,
    )
    def UPGRADE_PROCEED(self):
        return 'OVEHOSTED_CORE/upgradeProceed'

    @ohostedattrs(
        answerfile=True,
    )
    def ROLLBACK_PROCEED(self):
        return 'OVEHOSTED_CORE/rollbackProceed'

    @ohostedattrs(
        answerfile=True,
    )
    def SCREEN_PROCEED(self):
        return 'OVEHOSTED_CORE/screenProceed'

    @ohostedattrs(
        answerfile=True,
    )
    def CONFIRM_SETTINGS(self):
        return 'OVEHOSTED_CORE/confirmSettings'

    SKIP_TTY_CHECK = 'OVEHOSTED_CORE/skipTTYCheck'
    NODE_SETUP = 'OVEHOSTED_CORE/nodeSetup'
    MISC_REACHED = 'OVEHOSTED_CORE/miscReached'


@util.export
@util.codegen
@ohostedattrsclass
class NetworkEnv(object):

    @ohostedattrs(
        summary=True,
        description=_('Bridge interface'),
    )
    def BRIDGE_IF(self):
        return 'OVEHOSTED_NETWORK/bridgeIf'

    @ohostedattrs(
        summary=True,
        description=_('Host address'),
    )
    def HOST_NAME(self):
        return 'OVEHOSTED_NETWORK/host_name'

    @ohostedattrs(
        answerfile=True,
        summary=True,
        description=_('Engine FQDN'),
    )
    def OVIRT_HOSTED_ENGINE_FQDN(self):
        return 'OVEHOSTED_NETWORK/fqdn'
    FQDN_REVERSE_VALIDATION = 'OVEHOSTED_NETWORK/fqdnReverseValidation'

    @ohostedattrs(
        answerfile=True,
        summary=True,
        description=_('Bridge name'),
    )
    def BRIDGE_NAME(self):
        return 'OVEHOSTED_NETWORK/bridgeName'

    @ohostedattrs(
        answerfile=True,
        summary=True,
        description=_('Firewall manager'),
    )
    def FIREWALL_MANAGER(self):
        return 'OVEHOSTED_NETWORK/firewallManager'

    @ohostedattrs(
        answerfile=True,
        summary=True,
        description=_('Gateway address'),
    )
    def GATEWAY(self):
        return 'OVEHOSTED_NETWORK/gateway'

    FIREWALLD_SERVICES = 'OVEHOSTED_NETWORK/firewalldServices'
    FIREWALLD_SUBST = 'OVEHOSTED_NETWORK/firewalldSubst'

    @ohostedattrs(
        summary=True,
        description=_('SSH daemon port'),
    )
    def SSHD_PORT(self):
        return 'OVEHOSTED_NETWORK/sshdPort'

    PROMPT_REQUIRED_NETWORKS = 'OVEHOSTED_NETWORK/promptRequiredNetworks'
    REFUSE_DEPLOYING_WITH_NM = 'OVEHOSTED_NETWORK/refuseDeployingWithNM'
    ALLOW_INVALID_BOND_MODES = 'OVEHOSTED_NETWORK/allowInvalidBondModes'


@util.export
@util.codegen
@ohostedattrsclass
class EngineEnv(object):

    ADMIN_PASSWORD = 'OVEHOSTED_ENGINE/adminPassword'
    ADMIN_USERNAME = 'OVEHOSTED_ENGINE/adminUsername'
    INTERACTIVE_ADMIN_PASSWORD = 'OVEHOSTED_ENGINE/interactiveAdminPassword'

    @ohostedattrs(
        summary=True,
        description=_('Host name for web application'),
    )
    def APP_HOST_NAME(self):
        return 'OVEHOSTED_ENGINE/appHostName'

    @ohostedattrs(
        answerfile=True,
    )
    def HOST_CLUSTER_NAME(self):
        return 'OVEHOSTED_ENGINE/clusterName'

    TEMPORARY_CERT_FILE = 'OVEHOSTED_ENGINE/temporaryCertificate'
    PROMPT_NON_OPERATIONAL = 'OVEHOSTED_ENGINE/promptNonOperational'
    ENGINE_SETUP_TIMEOUT = 'OVEHOSTED_ENGINE/engineSetupTimeout'

    @ohostedattrs(
        answerfile=True,
    )
    def INSECURE_SSL(self):
        return 'OVEHOSTED_ENGINE/insecureSSL'


@util.export
@util.codegen
@ohostedattrsclass
class StorageEnv(object):
    @ohostedattrs(
        summary=True,
        description=_('Host ID'),
    )
    def HOST_ID(self):
        return 'OVEHOSTED_STORAGE/hostID'

    @ohostedattrs(
        answerfile=True,
        summary=True,
        description=_('Storage connection'),
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

    FAKE_MASTER_SD_UUID = 'OVEHOSTED_STORAGE/fakeMasterSdUUID'
    FAKE_MASTER_SD_CONNECTION_UUID = 'OVEHOSTED_STORAGE/fakeMasterSdConnUUID'

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
    def VOL_UUID(self):
        return 'OVEHOSTED_STORAGE/volUUID'

    @ohostedattrs(
        answerfile=True,
    )
    def VG_UUID(self):
        return 'OVEHOSTED_STORAGE/vgUUID'

    GUID = 'OVEHOSTED_STORAGE/GUID'

    @ohostedattrs(
        answerfile=True,
        summary=True,
        description=_('Image size GB'),
    )
    def IMAGE_SIZE_GB(self):
        return 'OVEHOSTED_STORAGE/imgSizeGB'

    QCOW_SIZE_GB = 'OVEHOSTED_STORAGE/qcowSizeGB'
    OVF_SIZE_GB = 'OVEHOSTED_STORAGE/ovfSizeGB'

    IMAGE_DESC = 'OVEHOSTED_STORAGE/imgDesc'

    @ohostedattrs(
        answerfile=True,
        summary=True,
        description=_('Storage Domain type'),
    )
    def DOMAIN_TYPE(self):
        return 'OVEHOSTED_STORAGE/domainType'

    @ohostedattrs(
        answerfile=True,
        summary=True,
        description=_('NFS Version'),
    )
    def NFS_VERSION(self):
        return 'OVEHOSTED_STORAGE/nfsVersion'

    @ohostedattrs(
        answerfile=True,
    )
    def MNT_OPTIONS(self):
        return 'OVEHOSTED_STORAGE/mntOptions'

    @ohostedattrs(
        answerfile=True,
    )
    def ENABLE_HC_GLUSTER_SERVICE(self):
        return 'OVEHOSTED_ENGINE/enableHcGlusterService'

    ENABLE_LIBGFAPI = 'OVEHOSTED_ENGINE/enableLibgfapi'

    @ohostedattrs(
        answerfile=True,
        summary=True,
        description=_('iSCSI Portal IP Address'),
    )
    def ISCSI_IP_ADDR(self):
        return 'OVEHOSTED_STORAGE/iSCSIPortalIPAddress'

    @ohostedattrs(
        answerfile=True,
        summary=True,
        description=_('iSCSI Portal port'),
    )
    def ISCSI_PORT(self):
        return 'OVEHOSTED_STORAGE/iSCSIPortalPort'

    @ohostedattrs(
        answerfile=True,
        summary=True,
        description=_('iSCSI Target Portal Group Tag'),
    )
    def ISCSI_PORTAL(self):
        return 'OVEHOSTED_STORAGE/iSCSIPortal'

    @ohostedattrs(
        answerfile=True,
        summary=True,
        description=_('iSCSI Portal user'),
    )
    def ISCSI_USER(self):
        return 'OVEHOSTED_STORAGE/iSCSIPortalUser'

    @ohostedattrs(
        answerfile=True,
        summary=True,
        description=_('iSCSI Target Name'),
    )
    def ISCSI_TARGET(self):
        return 'OVEHOSTED_STORAGE/iSCSITargetName'

    @ohostedattrs(
        answerfile=True,
        summary=True,
        description=_('LUN ID'),
    )
    def LUN_ID(self):
        return 'OVEHOSTED_STORAGE/LunID'

    ISCSI_PASSWORD = 'OVEHOSTED_STORAGE/iSCSIPortalPassword'

    BDEVICE_SIZE_GB = 'OVEHOSTED_STORAGE/blockDeviceSizeGB'

    @ohostedattrs(
        answerfile=True,
    )
    def METADATA_VOLUME_UUID(self):
        return 'OVEHOSTED_STORAGE/metadataVolumeUUID'

    @ohostedattrs(
        answerfile=True,
    )
    def METADATA_IMAGE_UUID(self):
        return 'OVEHOSTED_STORAGE/metadataImageUUID'

    @ohostedattrs(
        answerfile=True,
    )
    def LOCKSPACE_VOLUME_UUID(self):
        return 'OVEHOSTED_STORAGE/lockspaceVolumeUUID'

    @ohostedattrs(
        answerfile=True,
    )
    def LOCKSPACE_IMAGE_UUID(self):
        return 'OVEHOSTED_STORAGE/lockspaceImageUUID'

    FORCE_CREATEVG = 'OVEHOSTED_ENGINE/forceCreateVG'

    ANSWERFILE_CONTENT = 'OVEHOSTED_STORAGE/storageAnswerFileContent'
    HECONF_CONTENT = 'OVEHOSTED_STORAGE/storageHEConfContent'
    BROKER_CONF_CONTENT = 'OVEHOSTED_STORAGE/brokerConfContent'
    VM_CONF_CONTENT = 'OVEHOSTED_STORAGE/vmConfContent'
    CONF_IMAGE_SIZE_GB = 'OVEHOSTED_STORAGE/confImageSizeGB'

    @ohostedattrs(
        answerfile=True,
    )
    def CONF_IMG_UUID(self):
        return 'OVEHOSTED_STORAGE/confImageUUID'

    @ohostedattrs(
        answerfile=True,
    )
    def CONF_VOL_UUID(self):
        return 'OVEHOSTED_STORAGE/confVolUUID'


@util.export
@util.codegen
@ohostedattrsclass
class VMEnv(object):
    @ohostedattrs(
        answerfile=True,
    )
    def VM_UUID(self):
        return 'OVEHOSTED_VM/vmUUID'

    LOCAL_VM_UUID = 'OVEHOSTED_VM/localVmUUID'

    @ohostedattrs(
        answerfile=True,
        summary=True,
        description=_('Memory size MB'),
    )
    def MEM_SIZE_MB(self):
        return 'OVEHOSTED_VM/vmMemSizeMB'

    @ohostedattrs(
        answerfile=True,
        summary=True,
        description=_('Number of CPUs'),
    )
    def VCPUS(self):
        return 'OVEHOSTED_VM/vmVCpus'

    MAXVCPUS = 'OVEHOSTED_VM/maxVCpus'

    APPLIANCEVCPUS = 'OVEHOSTED_VM/applianceVCpus'

    APPLIANCEMEM = 'OVEHOSTED_VM/applianceMem'

    @ohostedattrs(
        answerfile=True,
        summary=True,
        description=_('MAC address'),
    )
    def MAC_ADDR(self):
        return 'OVEHOSTED_VM/vmMACAddr'

    @ohostedattrs(
        answerfile=True,
    )
    def NIC_UUID(self):
        return 'OVEHOSTED_VM/nicUUID'

    @ohostedattrs(
        answerfile=True,
        summary=True,
        description=_('ISO image (cdrom cloud-init)'),
    )
    def CDROM(self):
        return 'OVEHOSTED_VM/vmCDRom'

    @ohostedattrs(
        answerfile=True,
    )
    def CDROM_UUID(self):
        return 'OVEHOSTED_VM/cdromUUID'

    @ohostedattrs(
        answerfile=True,
    )
    def CONSOLE_UUID(self):
        return 'OVEHOSTED_VM/consoleUUID'

    @ohostedattrs(
        answerfile=True,
    )
    def EMULATED_MACHINE(self):
        return 'OVEHOSTED_VM/emulatedMachine'

    @ohostedattrs(
        answerfile=True,
        summary=True,
        description=_('OVF archive (for disk boot)'),
    )
    def OVF(self):
        return 'OVEHOSTED_VM/ovfArchive'

    @ohostedattrs(
        summary=True,
        description=_('Appliance version'),
    )
    def APPLIANCE_VERSION(self):
        return 'OVEHOSTED_VM/applianceVersion'

    VM_PASSWD = 'OVEHOSTED_VDSM/passwd'
    VM_PASSWD_VALIDITY_SECS = 'OVEHOSTED_VDSM/passwdValiditySecs'
    SUBST = 'OVEHOSTED_VM/subst'

    @ohostedattrs(
        answerfile=True,
        summary=True,
        description=_('Console type'),
    )
    def CONSOLE_TYPE(self):
        return 'OVEHOSTED_VDSM/consoleType'

    @ohostedattrs(
        answerfile=True,
        summary=True,
        description=_('Restart engine VM after engine-setup'),
    )
    def AUTOMATE_VM_SHUTDOWN(self):
        return 'OVEHOSTED_VM/automateVMShutdown'

    ACCEPT_DOWNLOAD_EAPPLIANCE_RPM = 'OVEHOSTED_VM/acceptDownloadEApplianceRPM'


@util.export
@util.codegen
@ohostedattrsclass
class CloudInit(object):
    @ohostedattrs(
        answerfile=True,
    )
    def GENERATE_ISO(self):
        return 'OVEHOSTED_VM/cloudInitISO'

    ROOTPWD = 'OVEHOSTED_VM/cloudinitRootPwd'
    HOST_IP = 'OVEHOSTED_VM/cloudinitHostIP'

    @ohostedattrs(
        answerfile=True,
    )
    def ROOT_SSH_ACCESS(self):
        return 'OVEHOSTED_VM/rootSshAccess'

    @ohostedattrs(
        answerfile=True,
    )
    def ROOT_SSH_PUBKEY(self):
        return 'OVEHOSTED_VM/rootSshPubkey'

    @ohostedattrs(
        answerfile=True,
    )
    def INSTANCE_HOSTNAME(self):
        return 'OVEHOSTED_VM/cloudinitInstanceHostName'

    @ohostedattrs(
        answerfile=True,
    )
    def INSTANCE_DOMAINNAME(self):
        return 'OVEHOSTED_VM/cloudinitInstanceDomainName'

    @ohostedattrs(
        answerfile=True,
    )
    def EXECUTE_ESETUP(self):
        return 'OVEHOSTED_VM/cloudinitExecuteEngineSetup'

    @ohostedattrs(
        answerfile=True,
    )
    def VM_STATIC_CIDR(self):
        return 'OVEHOSTED_VM/cloudinitVMStaticCIDR'

    @ohostedattrs(
        answerfile=True,
    )
    def VM_DNS(self):
        return 'OVEHOSTED_VM/cloudinitVMDNS'

    @ohostedattrs(
        answerfile=True,
    )
    def VM_ETC_HOSTS(self):
        return 'OVEHOSTED_VM/cloudinitVMETCHOSTS'

    @ohostedattrs(
        answerfile=True,
        summary=True,
        description=_('Engine VM timezone'),
    )
    def VM_TZ(self):
        return 'OVEHOSTED_VM/cloudinitVMTZ'


@util.export
@util.codegen
@ohostedattrsclass
class VDSMEnv(object):
    VDSMD_SERVICE = 'OVEHOSTED_VDSM/serviceName'
    VDSM_UID = 'OVEHOSTED_VDSM/vdsmUid'
    KVM_GID = 'OVEHOSTED_VDSM/kvmGid'
    VDS_CLI = 'OVEHOSTED_VDSM/vdscli'

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

    @ohostedattrs(
        answerfile=True,
    )
    def CA_SUBJECT(self):
        return 'OVEHOSTED_VDSM/caSubject'

    @ohostedattrs(
        answerfile=True,
        summary=True,
        description=_('CPU Type'),
    )
    def VDSM_CPU(self):
        return 'OVEHOSTED_VDSM/cpu'

    ENGINE_CPU = 'OVEHOSTED_VDSM/engineCpu'
    USE_SSL = 'OVEHOSTED_VDSM/useSSL'


@util.export
@util.codegen
class SanlockEnv(object):
    SANLOCK_SERVICE = 'OVEHOSTED_SANLOCK/serviceName'
    LOCKSPACE_NAME = 'OVEHOSTED_SANLOCK/lockspaceName'


@util.export
@util.codegen
@ohostedattrsclass
class NotificationsEnv(object):
    @ohostedattrs(
        answerfile=True,
    )
    def SMTP_SERVER(self):
        return 'OVEHOSTED_NOTIF/smtpServer'

    @ohostedattrs(
        answerfile=True,
    )
    def SMTP_PORT(self):
        return 'OVEHOSTED_NOTIF/smtpPort'

    @ohostedattrs(
        answerfile=True,
    )
    def SOURCE_EMAIL(self):
        return 'OVEHOSTED_NOTIF/sourceEmail'

    @ohostedattrs(
        answerfile=True,
    )
    def DEST_EMAIL(self):
        return 'OVEHOSTED_NOTIF/destEmail'

    DEFAULT_SMTP_SERVER = 'localhost'
    DEFAULT_SMTP_PORT = 25
    DEFAULT_SOURCE_EMAIL = 'root@localhost'
    DEFAULT_DEST_EMAIL = 'root@localhost'


@util.export
@util.codegen
class Stages(object):
    CONFIG_STORAGE_EARLY = 'ohosted.storage.configuration.early'
    CONFIG_STORAGE_LATE = 'ohosted.storage.configuration.late'
    CONFIG_STORAGE_BLOCKD = 'ohosted.storage.blockd.configuration.available'
    CONFIG_STORAGE_NFS = 'ohosted.storage.nfs.configuration.available'
    CONFIG_STORAGE_HC = 'ohosted.storage.hc.configuration.available'
    CONFIG_GATEWAY = 'ohosted.networking.gateway.configuration.available'
    CONFIG_CLOUD_INIT_OPTIONS = 'ohosted.boot.configuration.cloud_init_options'
    CONFIG_CLOUD_INIT_VM_NETWORKING = \
        'ohosted.boot.configuration.cloud_init_vm_networking'
    CONFIG_BACKUP_FILE = 'ohosted.configuration.backupfile'
    REQUIRE_ANSWER_FILE = 'ohosted.core.require.answerfile'
    CONFIG_OVF_IMPORT = 'ohosted.configuration.ovf'
    VDSMD_START = 'ohosted.vdsm.started'
    VDSMD_PKI = 'ohosted.vdsm.pki.available'
    VDSMD_CONFIGURED = 'ohosted.vdsm.configured'
    VDSMD_LATE_SETUP_READY = 'ohosted.vdsm.late_setup_ready'
    SANLOCK_INITIALIZED = 'ohosted.sanlock.initialized'
    STORAGE_AVAILABLE = 'ohosted.storage.available'
    IMAGES_REPREPARED = 'ohosted.storage.imagesreprepared'
    VM_IMAGE_AVAILABLE = 'ohosted.vm.image.available'
    OVF_IMPORTED = 'ohosted.vm.ovf.imported'
    BACKUP_INJECTED = 'ohosted.vm.backup.injected'
    STORAGE_POOL_DESTROYED = 'ohosted.storage.pool.destroyed'
    VM_CONFIGURED = 'ohosted.vm.state.configured'
    VM_RUNNING = 'ohosted.vm.state.running'
    VM_SHUTDOWN = 'ohosted.vm.state.shutdown'
    ENGINE_VM_UP_CHECK = 'ohosted.engine.vm.up.check'
    BRIDGE_AVAILABLE = 'ohosted.network.bridge.available'
    BRIDGE_DETECTED = 'ohosted.network.bridge.detected'
    GOT_HOSTNAME_FIRST_HOST = 'ohosted.network.hostname.got'
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
    NET_FIREWALL_FIRST_STAGE_CONFIGURED = \
        'ohosted.network.firewallmanager.fsconfigured'
    VDSMD_CONF_LOADED = 'ohosted.vdsm.conf.loaded'
    HOST_ADDED = 'ohosted.engine.host.added'
    VDSCLI_RECONNECTED = 'ohosted.engine.vdscli.reconnected'
    HA_START = 'ohosted.engine.ha.start'
    VDSM_LIBVIRT_CONFIGURED = 'ohosted.vdsm.libvirt.configured'
    NODE_FILES_PERSIST_S = 'ohosted.node.files.persist.start'
    NODE_FILES_PERSIST_E = 'ohosted.node.files.persist.end'
    CONF_VOLUME_AVAILABLE = 'ohosted.conf.volume.available'
    EXISTING_CONF_VOLUME_DETECTED = 'ohosted.conf.existing_volume.detected'
    BROKER_CONF_AVAILABLE = 'ohosted.notifications.broker.conf.available'
    ANSWER_FILE_AVAILABLE = 'ohosted.notifications.answerfile.available'
    CONF_IMAGE_AVAILABLE = 'ohosted.notifications.confimage.available'
    UPGRADED_APPLIANCE_RUNNING = 'ohosted.vm.state.upgraded.appliance.running'
    CHECK_MAINTENANCE_MODE = 'ohosted.core.check.maintenance.mode'
    CUSTOMIZATION_CA_ACQUIRED = 'ohosted.engine.ca.acquired.customization'
    CUSTOMIZATION_CPU_MODEL = 'ohosted.vm.cpu.model.customization'
    CUSTOMIZATION_CPU_NUMBER = 'ohosted.vm.cpu.model.number'
    CUSTOMIZATION_MAC_ADDRESS = 'ohosted.vm.mac.customization'
    CLOSEUP_CA_ACQUIRED = 'ohosted.engine.ca.acquired.closeup'
    UPGRADE_CHECK_SD_SPACE = 'ohosted.upgrade.check.sd.space'
    UPGRADE_CHECK_SPM_HOST = 'ohosted.upgrade.check.spm.host'
    UPGRADE_CHECK_UPGRADE_REQUIREMENTS = 'ohosted.upgrade.check.upgrade.req'
    UPGRADE_CHECK_UPGRADE_VERSIONS = 'ohosted.upgrade.check.upgrade.ver'
    UPGRADE_BACKUP_DISK_CREATED = 'ohosted.upgrade.backup.disk.created'
    UPGRADE_VM_SHUTDOWN = 'ohosted.upgrade.vm.state.shutdown'
    UPGRADE_DISK_BACKUP_SAVED = 'ohosted.upgrade.disk.backup.saved'
    UPGRADE_DISK_EXTENDED = 'ohosted.upgrade.disk.extended'
    UPGRADE_BACKUP_DISK_REGISTERED = 'ohosted.upgrade.backup.disk.registered'
    UPGRADED_DATACENTER_UP = 'ohosted.upgrade.datacenter.up'

    DIALOG_TITLES_S_VM = 'ohosted.dialog.titles.vm.start'
    DIALOG_TITLES_E_VM = 'ohosted.dialog.titles.vm.end'
    DIALOG_TITLES_S_NETWORK = 'ohosted.dialog.titles.network.start'
    DIALOG_TITLES_E_NETWORK = 'ohosted.dialog.titles.network.end'
    DIALOG_TITLES_S_ENGINE = 'ohosted.dialog.titles.engine.start'
    DIALOG_TITLES_E_ENGINE = 'ohosted.dialog.titles.engine.end'
    DIALOG_TITLES_S_STORAGE = 'ohosted.dialog.titles.storage.start'
    DIALOG_TITLES_E_STORAGE = 'ohosted.dialog.titles.storage.end'

    ANSIBLE_BOOTSTRAP_LOCAL_VM = 'ohosted.ansible.bootstrap.local.vm'
    ANSIBLE_CREATE_SD = 'ohosted.ansible.create.storage.domain'
    ANSIBLE_CREATE_TARGET_VM = 'ohosted.ansible.create.target.vm'
    ANSIBLE_CUSTOMIZE_DISK_SIZE = 'ohosted.ansible.disk.customized'


@util.export
@util.codegen
class Defaults(object):
    DEFAULT_STORAGE_DOMAIN_NAME = 'hosted_storage'
    DEFAULT_STORAGE_DATACENTER_NAME = 'hosted_datacenter'
    DEFAULT_VDSMD_SERVICE = 'vdsmd'
    DEFAULT_SYSTEM_USER_VDSM = 'vdsm'
    DEFAULT_SYSTEM_GROUP_KVM = 'kvm'
    DEFAULT_SANLOCK_SERVICE = 'sanlock'
    DEFAULT_LOCKSPACE_NAME = 'hosted-engine'
    DEFAULT_IMAGE_DESC = 'Hosted Engine Image'
    DEFAULT_IMAGE_SIZE_GB = 25  # based on minimum requirements.
    MINIMAL_MEM_SIZE_MB = 4096  # based on minimum requirements.
    DEFAULT_CONF_IMAGE_SIZE_GB = 1
    DEFAULT_CDROM = '/dev/null'
    DEFAULT_BRIDGE_IF = 'em1'
    DEFAULT_BRIDGE_NAME = 'ovirtmgmt'
    DEFAULT_PKI_SUBJECT = '/C=EN/L=Test/O=Test/CN=Test'
    DEFAULT_CA_SUBJECT = '/C=EN/L=Test/O=Test/CN=TestCA'  # must be != above
    DEFAULT_VM_PASSWD_VALIDITY_SECS = 10800  # 3 hours to for engine install
    DEFAULT_VM_VCPUS = 2  # based on minimum requirements.
    DEFAULT_SSHD_PORT = 22
    DEFAULT_EMULATED_MACHINE = 'pc'
    DEFAULT_RHEL_EMULATED_MACHINE = 'pc-i440fx-rhel7.3.0'
    DEFAULT_ISCSI_PORT = 3260
    DEFAULT_ENGINE_SETUP_TIMEOUT = 1800
    DEFAULT_ENGINE_API_TIMEOUT = 30
    DEFAULT_ENGINE_API_RETRY_ATTEMPTS = 5
    DEFAULT_STATE_TRANS_NOTIFICATION = 'maintenance|start|stop|migrate|up|down'
    DEFAULT_TEMPDIR = '/var/tmp'
    DEFAULT_ADMIN_USERNAME = 'admin@internal'


@util.export
@util.codegen
class Confirms(object):
    DEPLOY_PROCEED = 'DEPLOY_PROCEED'
    UPGRADE_PROCEED = 'UPGRADE_PROCEED'
    ROLLBACK_PROCEED = 'ROLLBACK_PROCEED'
    CPU_PROCEED = 'CPU_PROCEED'
    DISK_PROCEED = 'DISK_PROCEED'
    MEMORY_PROCEED = 'MEMORY_PROCEED'
    SCREEN_PROCEED = 'SCREEN_PROCEED'
    SETTINGS = 'SETTINGS_PROCEED'
    UPGRADE_DISK_RESIZE_PROCEED = 'UPGRADE_DISK_RESIZE_PROCEED'
    LM_VOLUMES_UPGRADE_PROCEED = 'LM_VOLUME_UPGRADE_PROCEED'


@util.export
@util.codegen
class FirstHostEnv(object):
    SKIP_SHARED_STORAGE_ANSWERF = 'OVEHOSTED_FIRST_HOST/skipSharedStorageAF'
    DEPLOY_WITH_HE_35_HOSTS = 'OVEHOSTED_FIRST_HOST/deployWithHE35Hosts'


@util.export
@util.codegen
class Upgrade(object):
    BACKUP_FILE = 'OVEHOSTED_UPGRADE/backupFileName'
    DST_BACKUP_FILE = 'OVEHOSTED_UPGRADE/dstBackupFileName'
    RESTORE_DWH = 'OVEHOSTED_UPGRADE/restoreDwh'
    RESTORE_REPORTS = 'OVEHOSTED_UPGRADE/restoreReports'
    CONFIRM_UPGRADE_SUCCESS = 'OVEHOSTED_UPGRADE/confirmUpgradeSuccess'
    CONFIRM_UPGRADE_DISK_RESIZE = 'OVEHOSTED_UPGRADE/confirmUpgradeDiskResize'

    BACKUP_IMG_UUID = 'OVEHOSTED_UPGRADE/backupImgUUID'
    BACKUP_VOL_UUID = 'OVEHOSTED_UPGRADE/backupVolUUID'
    BACKUP_SIZE_GB = 'OVEHOSTED_UPGRADE/backupImgSizeGB'
    EXTEND_VOLUME = 'OVEHOSTED_UPGRADE/extend_volume'
    UPGRADE_CREATE_LM_VOLUMES = 'OVEHOSTED_UPGRADE/createLMVolumes'
    LM_VOLUMES_UPGRADE_PROCEED = 'OVEHOSTED_UPGRADE/LMVolumesUpgradeProceed'
    UPGRADE_ABORT_ON_UNSUPPORTED_VER = 'OVEHOSTED_UPGRADE/abortUnsupportedVer'


@util.export
@util.codegen
class AnsibleCallback(object):
    DEBUG = 'OVEHOSTED_AC/debug'
    WARNING = 'OVEHOSTED_AC/warning'
    ERROR = 'OVEHOSTED_AC/error'
    INFO = 'OVEHOSTED_AC/info'
    RESULT = 'OVEHOSTED_AC/result'
    TYPE = 'OVEHOSTED_AC/type'
    BODY = 'OVEHOSTED_AC/body'
    OTOPI_CALLBACK_OF = 'OTOPI_CALLBACK_OF'
    CALLBACK_NAME = '1_otopi_json'


# vim: expandtab tabstop=4 shiftwidth=4
