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


"""
VM disk import plugin.
"""


import configparser
import gettext
import glob
import guestfs
import hashlib
import json
import math
import os
import shutil
import tarfile
import tempfile


from io import StringIO

from otopi import plugin
from otopi import transaction
from otopi import util

from vdsm.client import ServerError

from ovirt_setup_lib import dialog

from ovirt_hosted_engine_ha.lib import heconflib

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import domains as ohosteddomains
from ovirt_hosted_engine_setup import util as ohostedutil
from ovirt_hosted_engine_setup.ovf import ovfenvelope


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


# TODO: avoid the transaction or complete it
# now there is just one element without any rollback action
class ImageTransaction(transaction.TransactionElement):
    """Image transaction element."""

    def __init__(self, parent, tar, src, dst, backup_src):
        super(ImageTransaction, self).__init__()
        self._parent = parent
        self._tar = tar
        self._src = src
        self._dst = dst
        self._backup_src = backup_src
        self._prepared = False

    def __str__(self):
        return _("Image Transaction")

    def _get_volume_path(self):
        """
        Return path of the volume file inside the domain
        """
        return heconflib.get_volume_path(
            self._parent.environment[ohostedcons.StorageEnv.SP_UUID],
            self._parent.environment[ohostedcons.StorageEnv.SD_UUID],
            self._parent.environment[ohostedcons.StorageEnv.IMG_UUID],
            self._parent.environment[ohostedcons.StorageEnv.VOL_UUID]
        )

    def _validate_volume(self):
        self._parent.logger.info(
            _('Validating pre-allocated volume size')
        )
        _rc, stdout, _stderr = self._parent.execute(
            (
                self._parent.command.get('sudo'),
                '-u',
                'vdsm',
                '-g',
                'kvm',
                self._parent.command.get('qemu-img'),
                'info',
                '--output',
                'json',
                self._dst,
            ),
            raiseOnError=True
        )
        info = json.decoder.JSONDecoder().decode('\n'.join(stdout))
        source_size = int(info['virtual-size'])

        cli = self._parent.environment[ohostedcons.VDSMEnv.VDS_CLI]
        try:
            size = cli.Volume.getSize(
                volumeID=self._parent.environment[
                    ohostedcons.StorageEnv.VOL_UUID
                ],
                storagepoolID=self._parent.environment[
                    ohostedcons.StorageEnv.SP_UUID
                ],
                storagedomainID=self._parent.environment[
                    ohostedcons.StorageEnv.SD_UUID
                ],
                imageID=self._parent.environment[
                    ohostedcons.StorageEnv.IMG_UUID
                ],
            )
        except ServerError as e:
            raise RuntimeError(str(e))

        destination_size = int(size['apparentsize'])
        if destination_size < source_size:
            raise RuntimeError(
                _(
                    'Error on volume size: the selected image (size {source}) '
                    'doesn\'t fit the target volume (size {destination})'
                ).format(
                    source=source_size,
                    destination=destination_size,
                )
            )

    def _uploadVolume(self):
        source = self._dst
        try:
            destination = self._get_volume_path()
        except RuntimeError as e:
            return (1, str(e))
        return ohostedutil.transferImage(self._parent, source, destination)

    def _injectBackup(self):
        try:
            destination = self._get_volume_path()
        except RuntimeError as e:
            return (1, str(e))
        # NFS mounts using root_squash will fail if accessed with root user.
        # Dropping root privileges and moving to vdsm user.
        prev_xdg_runtime_dir = os.getenv('XDG_RUNTIME_DIR', None)
        try:
            os.setresgid(
                self._parent.environment[ohostedcons.VDSMEnv.KVM_GID],
                self._parent.environment[ohostedcons.VDSMEnv.KVM_GID],
                -1
            )
            os.setresuid(
                self._parent.environment[ohostedcons.VDSMEnv.VDSM_UID],
                self._parent.environment[ohostedcons.VDSMEnv.VDSM_UID],
                -1
            )
            # $XDG_RUNTIME_DIR is not set if the current user is not the
            # original user of the session
            os.unsetenv('XDG_RUNTIME_DIR')
        except OSError as os_err:
            self._parent.logger.error('Unable to drop root privileges')
            self._parent.logger.debug('exception', exc_info=True)
            raise os_err

        try:
            g = guestfs.GuestFS(python_return_dict=True)
            g.set_backend('direct')
            g.add_drive_opts(filename=destination, format='raw', readonly=0)
            self.logger.debug(
                'disk added from {path}'.format(path=destination)
            )
            try:
                g.launch()
                self._parent.logger.debug('guestfs launched')
                g.mount('/dev/sda1', '/')
                self._parent.logger.debug('disk mounted')
                g.upload(
                    self._backup_src,
                    self._parent.environment[
                        ohostedcons.Upgrade.DST_BACKUP_FILE
                    ]
                )
                self._parent.logger.debug('backup file uploaded')
                g.umount('/')
                self._parent.logger.debug('disk unmounted')
            finally:
                g.shutdown()
        finally:
            g.close()
        try:
            # regain root privileges
            os.setresgid(0, 0, -1)
            os.setresuid(0, 0, -1)
            if prev_xdg_runtime_dir:
                os.environ['XDG_RUNTIME_DIR'] = prev_xdg_runtime_dir
        except OSError as os_err:
            self._parent.logger.error('Unable to regain root privileges')
            self._parent.logger.debug('exception', exc_info=True)
            raise os_err
        return (0, 'OK')

    def prepare(self):
        self._parent.logger.info(
            _(
                'Extracting disk image from OVF archive '
                '(could take a few minutes depending on archive size)'
            )
        )
        try:
            tar = tarfile.open(self._tar, 'r:gz')
            src_file_obj = tar.extractfile(self._src)
            dst_file_obj = open(self._dst, 'wb')
            try:
                shutil.copyfileobj(src_file_obj, dst_file_obj)
                dst_file_obj.truncate()
                dst_file_obj.flush()
            finally:
                dst_file_obj.close()
            os.chown(
                self._dst,
                self._parent.environment[ohostedcons.VDSMEnv.VDSM_UID],
                self._parent.environment[ohostedcons.VDSMEnv.KVM_GID]
            )
            os.chmod(self._dst, 0644)
            self._prepared = True
        finally:
            src_file_obj.close()
            tar.close()
        self._validate_volume()

    def abort(self):
        self._parent.logger.info(
            _('Image not uploaded to data domain')
        )

    def commit(self):
        self._parent.logger.info(
            _(
                'Uploading volume to data domain '
                '(could take a few minutes depending on archive size)'
            )
        )
        status, message = self._uploadVolume()
        if status != 0:
            raise RuntimeError(message)
        if self._backup_src:
            self._parent.logger.info(_('Injecting engine backup'))
            self._injectBackup()
            self._parent.logger.info(_('Backup successfully injected'))
        self._parent.logger.info(_('Image successfully imported from OVF'))


@util.export
class Plugin(plugin.PluginBase):
    """
    VM disk import plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._source_image = None
        self._image_path = None
        self._ovf_mem_size_mb = None
        self._appliances = []
        self._install_appliance = False
        self._appliance_rpm_name = ohostedcons.Const.APPLIANCE_RPM_NAME

    def _detect_appliances(self):
        self._appliances = []
        config = configparser.ConfigParser()
        config.optionxform = str
        confdir = os.path.join(
            ohostedcons.FileLocations.OVIRT_APPLIANCES_DESC_DIR,
            ohostedcons.FileLocations.OVIRT_APPLIANCES_DESC_FILENAME_TEMPLATE,
        )
        conffiles = glob.glob(confdir)
        fakesection = 'appliance'
        keys = ['description', 'version', 'path', 'sha1sum']
        for cf in conffiles:
            self.logger.debug('parsing: ' + cf)
            with open(cf) as stream:
                fakefile = StringIO(
                    u'[{s}]\n'.format(s=fakesection) + stream.read()
                )
                config.readfp(fakefile)
            if set(
                [config.has_option(fakesection, k) for k in keys]
            ) == set([True]):
                app = {k: config.get(fakesection, k) for k in keys}
                app.update(
                    {'index': str(len(self._appliances) + 1)}
                )
                self._appliances.append(app)
            else:
                self.logger.error('error parsing: ' + cf)
        self.logger.debug('available appliances: ' + str(self._appliances))

    def _file_hash(self, filename):
        h = hashlib.sha1()
        with open(filename, 'rb') as file:
            chunk = 0
            while chunk != b'':
                chunk = file.read(1024)
                h.update(chunk)
        self.logger.debug(
            "calculated sha1sum for '{f}': {h}".format(
                f=filename,
                h=h.hexdigest(),
            )
        )
        return h.hexdigest()

    def _parse_ovf(self, tar, ovf_xml):
        valid = True
        tmpdir = tempfile.mkdtemp()
        try:
            self.logger.debug(
                'Extracting {filename} in {tmpdir}'.format(
                    filename=ovf_xml,
                    tmpdir=tmpdir,
                )
            )
            tar.extract(
                member=ovf_xml,
                path=tmpdir,
            )
            self.logger.debug(str(os.listdir(tmpdir)))
            tree = ovfenvelope.etree_.parse(
                os.path.join(
                    tmpdir,
                    ovf_xml,
                )
            )
            self.logger.debug('Configuring Disk')
            disk = tree.find('Section/Disk')
            self.environment[
                ohostedcons.StorageEnv.OVF_SIZE_GB
            ] = int(
                disk.attrib['{http://schemas.dmtf.org/ovf/envelope/1/}size']
            )
            try:
                self.environment[
                    ohostedcons.StorageEnv.IMAGE_DESC
                ] = disk.attrib[
                    '{http://schemas.dmtf.org/ovf/envelope/1/}disk-alias'
                ]
            except KeyError:
                self.logger.debug(
                    _(
                        'OVF does not contain a valid image description, '
                        'using default.'
                    )
                )
            self._source_image = os.path.join(
                'images',
                disk.attrib[
                    '{http://schemas.dmtf.org/ovf/envelope/1/}fileRef'
                ],
            )
            self.environment[
                ohostedcons.StorageEnv.QCOW_SIZE_GB
            ] = int(
                math.ceil(
                    tar.getmember(
                        self._source_image
                    ).size / 1024. / 1024. / 1024.
                )
            )
            self.logger.debug('Configuring CPUs')
            num_of_sockets = int(
                tree.find(
                    'Content/Section/Item/{'
                    'http://schemas.dmtf.org/wbem/wscim/1/cim-schema'
                    '/2/CIM_ResourceAllocationSettingData'
                    '}num_of_sockets'
                ).text
            )
            cpu_per_socket = int(
                tree.find(
                    'Content/Section/Item/{'
                    'http://schemas.dmtf.org/wbem/wscim/1/cim-schema'
                    '/2/CIM_ResourceAllocationSettingData'
                    '}cpu_per_socket'
                ).text
            )
            self.environment[
                ohostedcons.VMEnv.APPLIANCEVCPUS
            ] = str(num_of_sockets * cpu_per_socket)
            self.logger.debug('Configuring memory')
            unit = tree.find(
                'Content/Section/Item/{'
                'http://schemas.dmtf.org/wbem/wscim/1/cim-schema'
                '/2/CIM_ResourceAllocationSettingData'
                '}AllocationUnits'
            ).text
            if unit != 'MegaBytes':
                raise RuntimeError(
                    _('Unsupported unit type: {unit}').format(
                        unit=unit,
                    )
                )
            self._ovf_mem_size_mb = tree.find(
                'Content/Section/Item/{'
                'http://schemas.dmtf.org/wbem/wscim/1/cim-schema'
                '/2/CIM_ResourceAllocationSettingData'
                '}VirtualQuantity'
            ).text
            try:
                # ensure that appliance memory is stored as integer
                self.environment[
                    ohostedcons.VMEnv.APPLIANCEMEM
                ] = int(self._ovf_mem_size_mb)
            except ValueError:
                self.logger.warning(_('Failed to read appliance memory'))
                self.environment[
                    ohostedcons.VMEnv.APPLIANCEMEM
                ] = None

        except Exception as e:
            self.logger.debug(
                'Error parsing OVF file',
                exc_info=True,
            )
            self.logger.error(e)
            valid = False
        shutil.rmtree(tmpdir)
        return valid

    def _check_ovf(self, path):
        if not os.path.exists(path):
            self.logger.error(_('The specified file does not exists'))
            success = False
        else:
            # Decode ovf file content
            tar = tarfile.open(path, 'r:gz')
            try:
                ovf_xml = None
                self.logger.info(
                    _(
                        'Checking OVF archive content '
                        '(could take a few minutes depending on archive size)'
                    )
                )
                for filename in tar.getnames():
                    self.logger.debug(filename)
                    if (
                        filename.startswith('master') and
                        os.path.splitext(filename)[1] == '.ovf'
                    ):
                        ovf_xml = filename
                        break
                if ovf_xml is None:
                    self.logger.error(
                        _(
                            'The OVF archive does not have a required '
                            'OVF XML file.'
                        )
                    )
                    success = False
                else:
                    self.logger.info(
                        _(
                            'Checking OVF XML content '
                            '(could take a few minutes depending on '
                            'archive size)'
                        )
                    )
                    success = self._parse_ovf(tar, ovf_xml)
            finally:
                tar.close()
        return success

    def _get_image_path(self, imageID, volumeID):
        cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        try:
            pathDict = cli.Image.prepare(
                storagepoolID=ohostedcons.Const.BLANK_UUID,
                storagedomainID=self.environment[
                    ohostedcons.StorageEnv.SD_UUID
                ],
                imageID=imageID,
                volumeID=volumeID,
            )
            self.logger.debug('_get_image_path: {s}'.format(s=pathDict))
        except ServerError as e:
            raise RuntimeError(
                _('Failed preparing the disk: {m}').format(
                    m=str(e),
                )
            )

        if 'path' not in pathDict:
            raise RuntimeError(
                _('Unable to get the disk path')
            )
        return pathDict['path']

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.VMEnv.OVF,
            None
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.ACCEPT_DOWNLOAD_EAPPLIANCE_RPM,
            None
        )
        self.environment.setdefault(
            ohostedcons.CoreEnv.TEMPDIR,
            os.getenv('TMPDIR', ohostedcons.Defaults.DEFAULT_TEMPDIR)
        )
        self.environment.setdefault(
            ohostedcons.Upgrade.BACKUP_FILE,
            None
        )
        self.environment.setdefault(
            ohostedcons.Upgrade.DST_BACKUP_FILE,
            None
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.APPLIANCE_VERSION,
            None
        )
        self.environment.setdefault(
            ohostedcons.Upgrade.BACKUP_IMG_UUID,
            None,
        )
        self.environment.setdefault(
            ohostedcons.Upgrade.BACKUP_VOL_UUID,
            None,
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.OVF_SIZE_GB,
            None,
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
        condition=lambda self: not self.environment[
            ohostedcons.CoreEnv.ANSIBLE_DEPLOYMENT
        ],
    )
    def _setup(self):
        self.command.detect('sudo')
        self.command.detect('qemu-img')
        if self.environment[ohostedcons.CoreEnv.UPGRADING_APPLIANCE]:
            self._appliance_rpm_name = ohostedcons.Const.APPLIANCE40_RPM_NAME
        self.logger.info(_('Detecting available oVirt engine appliances'))
        self._detect_appliances()
        if not self._appliances:
            self.dialog.note(
                _(
                    'The engine appliance is now required to deploy '
                    'hosted-engine.\n'
                    'You could get it installing '
                    '{appliance_rpm_name} rpm\n'
                    'or provide a path to OVF archive at the '
                    '\'VM Configuration\' stage.'
                ).format(
                    appliance_rpm_name=self._appliance_rpm_name,
                )
            )
            if self.environment[
                ohostedcons.VMEnv.ACCEPT_DOWNLOAD_EAPPLIANCE_RPM
            ] is not None:
                self._install_appliance = self.environment[
                    ohostedcons.VMEnv.ACCEPT_DOWNLOAD_EAPPLIANCE_RPM
                ]
            else:
                self._install_appliance = dialog.queryBoolean(
                    dialog=self.dialog,
                    name='OVEHOSTED_INSTALL_OVIRT_ENGINE_APPLIANCE',
                    note=_(
                        'Do you want to install {appliance_rpm_name} rpm? '
                        '(@VALUES@) [@DEFAULT@]: '
                    ).format(
                        appliance_rpm_name=self._appliance_rpm_name,
                    ),
                    prompt=True,
                    default=True,
                )

    @plugin.event(
        stage=plugin.Stages.STAGE_INTERNAL_PACKAGES,
        condition=lambda self: self._install_appliance,
    )
    def _internal_packages(self):
        self.logger.info(_('Installing the oVirt engine appliance'))
        self.packager.install(
            packages=(self._appliance_rpm_name,)
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_LATE_SETUP,
        condition=lambda self: self._install_appliance,
    )
    def _late_setup(self):
        self._detect_appliances()
        if not self._appliances:
            raise RuntimeError(
                _('Cannot deploy without oVirt engine appliance')
            )

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_VM,
            ohostedcons.Stages.UPGRADE_CHECK_SPM_HOST,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_VM,
        ),
        condition=lambda self: (
            not self.environment[ohostedcons.CoreEnv.ROLLBACK_UPGRADE] and
            not self.environment[ohostedcons.CoreEnv.ANSIBLE_DEPLOYMENT]
        ),
        name=ohostedcons.Stages.CONFIG_OVF_IMPORT,
    )
    def _customization(self):
        interactive = self.environment[
            ohostedcons.VMEnv.OVF
        ] is None
        if interactive:
            if self._appliances:
                directlyOVA = str(len(self._appliances) + 1)
                app_list = ''
                for entry in self._appliances:
                    app_list += _(
                        '\t[{i}] - {description} - {version}\n'
                    ).format(
                        i=entry['index'],
                        description=entry['description'],
                        version=entry['version'],
                    )
                app_list += (
                    _('\t[{i}] - Directly select an OVA file\n').format(
                        i=directlyOVA,
                    )
                )

        valid = False
        while not valid:
            appliance_ver = None
            if not interactive:
                ova_path = self.environment[ohostedcons.VMEnv.OVF]
            else:
                ova_path = ''
                if self._appliances:
                    self.dialog.note(
                        _(
                            'The following appliance have been '
                            'found on your system:\n'
                            '{app_list}'
                        ).format(
                            app_list=app_list,
                        )
                    )
                    sapp = self.dialog.queryString(
                        name='OVEHOSTED_BOOT_DISK_APPLIANCE',
                        note=_(
                            'Please select an appliance '
                            '(@VALUES@) [@DEFAULT@]: '
                        ),
                        prompt=True,
                        caseSensitive=True,
                        default='1',
                        validValues=[
                            str(i + 1) for i in range(
                                len(self._appliances) + 1
                            )
                        ],
                    )
                    if sapp != directlyOVA:
                        ova_path = self._appliances[int(sapp) - 1]['path']
                        appliance_ver = self._appliances[
                            int(sapp) - 1
                        ]['version']
                        self.logger.info(_('Verifying its sha1sum'))
                        if (
                            self._file_hash(ova_path) !=
                            self._appliances[int(sapp) - 1]['sha1sum']
                        ):
                            self.logger.error(
                                _(
                                    "The selected appliance is invalid: the "
                                    "sha1sum of the selected file ('{p}') "
                                    "doesn't match the expected value."
                                ).format(p=ova_path)
                            )
                            continue
                if not ova_path:
                    ova_path = self.dialog.queryString(
                        name='OVEHOSTED_VMENV_OVF',
                        note=_(
                            'Please specify path to OVF archive '
                            'you would like to use [@DEFAULT@]: '
                        ),
                        prompt=True,
                        caseSensitive=True,
                        default=str(self.environment[
                            ohostedcons.VMEnv.OVF
                        ]),
                    )
            valid = self._check_ovf(ova_path)
            if valid:
                self.environment[ohostedcons.VMEnv.OVF] = ova_path
                self.environment[
                    ohostedcons.VMEnv.APPLIANCE_VERSION
                ] = appliance_ver
            else:
                if interactive:
                    self.logger.error(
                        _(
                            'The specified OVF archive is not a valid OVF '
                            'archive.'
                        )
                    )
                else:
                    raise RuntimeError(
                        _(
                            'The specified OVF archive is not '
                            'readable. Please ensure that {filepath} '
                            'could be read'
                        ).format(
                            filepath=self.environment[
                                ohostedcons.VMEnv.OVF
                            ]
                        )
                    )

        valid = False
        checker = ohosteddomains.DomainChecker()
        while not valid:
            vdsmPermissionsErrorMessage = None
            spaceErrorMessage = None
            tempDirCheck = ohostedutil.checkUserPermissions(
                self,
                'vdsm',
                'ls %s' % self.environment[ohostedcons.CoreEnv.TEMPDIR]
            )
            if tempDirCheck is not True:
                vdsmPermissionsErrorMessage = _(
                    'vdsm user has no read permissions on'
                    ' {tmpdir}, please choose another. {errmsg}'
                ).format(
                    tmpdir=self.environment[
                        ohostedcons.CoreEnv.TEMPDIR],
                    errmsg=tempDirCheck,
                )

            spaceCheck = False
            try:
                checker.check_available_space(
                    self.environment[ohostedcons.CoreEnv.TEMPDIR],
                    int(
                        self.environment[ohostedcons.StorageEnv.QCOW_SIZE_GB]
                    ) * 1024
                )
                spaceCheck = True
            except ohosteddomains.InsufficientSpaceError as e:
                self.logger.debug(
                    'Error checking TMPDIR space',
                    exc_info=True,
                )
                self.logger.debug(e)
                valid = False
                spaceErrorMessage = _(
                    'Not enough space in the temporary directory [{tmpdir}]'
                ).format(
                    tmpdir=self.environment[
                        ohostedcons.CoreEnv.TEMPDIR
                    ],
                )
            if not interactive:
                if not spaceCheck:
                    raise RuntimeError(spaceErrorMessage)
                if tempDirCheck is not True:
                    raise RuntimeError(vdsmPermissionsErrorMessage)
            else:
                if not spaceCheck:
                    self.logger.error(spaceErrorMessage)
                if tempDirCheck is not True:
                    self.logger.error(vdsmPermissionsErrorMessage)
                if not spaceCheck or tempDirCheck is not True:
                    self.environment[
                        ohostedcons.CoreEnv.TEMPDIR
                    ] = self.dialog.queryString(
                        name='OVEHOSTED_COREENV_TEMPDIR',
                        note=_(
                            'Please specify path to a temporary directory '
                            'with at least {size} GB [@DEFAULT@]: '
                        ).format(
                            size=self.environment[
                                ohostedcons.StorageEnv.QCOW_SIZE_GB
                            ],
                        ),
                        prompt=True,
                        caseSensitive=True,
                        default=str(self.environment[
                            ohostedcons.CoreEnv.TEMPDIR
                        ]),
                    )

            valid = True if tempDirCheck is True and spaceCheck else False

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_VM,
            ohostedcons.Stages.UPGRADE_CHECK_SPM_HOST,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_VM,
            ohostedcons.Stages.CONFIG_OVF_IMPORT,
        ),
        condition=lambda self: self.environment[
            ohostedcons.CoreEnv.ANSIBLE_DEPLOYMENT
        ],
        name=ohostedcons.Stages.CONFIG_OVF_IMPORT_ANSIBLE,
    )
    def _customization_ansible(self):
        interactive = self.environment[
            ohostedcons.VMEnv.OVF
        ] is None
        valid = False
        self.environment[
            ohostedcons.VMEnv.APPLIANCEVCPUS
        ] = str(ohostedcons.Defaults.ANSIBLE_RECOMMENDED_APPLIANCE_VCPUS)
        self.environment[
            ohostedcons.VMEnv.APPLIANCEMEM
        ] = int(ohostedcons.Defaults.ANSIBLE_RECOMMENDED_APPLIANCE_MEM_SIZE_MB)

        while not valid:
            appliance_ver = None
            if not interactive:
                ova_path = self.environment[ohostedcons.VMEnv.OVF]
            else:
                ova_path = ''
                if not ova_path:
                    ova_path = self.dialog.queryString(
                        name='OVEHOSTED_VMENV_OVF_ANSIBLE',
                        note=_(
                            'If you want to deploy with a custom engine '
                            'appliance image,\n'
                            'please specify the path to '
                            'the OVA archive you would like to use\n'
                            '(leave it empty to skip, the setup will use '
                            '{rpmname} rpm installing it if missing): '
                        ).format(rpmname=self._appliance_rpm_name),
                        prompt=True,
                        caseSensitive=True,
                        default="",
                    )
            if ova_path == "":
                valid = True
            else:
                valid = self._check_ovf(ova_path)
            if valid:
                self.environment[ohostedcons.VMEnv.OVF] = ova_path
                self.environment[
                    ohostedcons.VMEnv.APPLIANCE_VERSION
                ] = appliance_ver
            else:
                if interactive:
                    self.logger.error(
                        _(
                            'The specified OVF archive is not a valid OVF '
                            'archive.'
                        )
                    )
                else:
                    raise RuntimeError(
                        _(
                            'The specified OVF archive is not '
                            'readable. Please ensure that {filepath} '
                            'could be read'
                        ).format(
                            filepath=self.environment[
                                ohostedcons.VMEnv.OVF
                            ]
                        )
                    )

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        name=ohostedcons.Stages.OVF_IMPORTED,
        after=(
            ohostedcons.Stages.VM_IMAGE_AVAILABLE,
            ohostedcons.Stages.UPGRADE_DISK_EXTENDED,
        ),
        condition=lambda self: (
            not self.environment[ohostedcons.CoreEnv.ROLLBACK_UPGRADE] and
            not self.environment[ohostedcons.CoreEnv.ANSIBLE_DEPLOYMENT]
        ),
    )
    def _misc(self):
        fd, self._image_path = tempfile.mkstemp(
            dir=self.environment[ohostedcons.CoreEnv.TEMPDIR],
        )
        os.close(fd)
        with transaction.Transaction() as localtransaction:
            localtransaction.append(
                ImageTransaction(
                    parent=self,
                    tar=self.environment[ohostedcons.VMEnv.OVF],
                    src=self._source_image,
                    dst=self._image_path,
                    backup_src=self.environment[
                        ohostedcons.Upgrade.BACKUP_FILE
                    ],
                )
            )

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        after=(
            ohostedcons.Stages.UPGRADE_VM_SHUTDOWN,
        ),
        name=ohostedcons.Stages.UPGRADE_DISK_BACKUP_SAVED,
        condition=lambda self: (
            self.environment[ohostedcons.CoreEnv.UPGRADING_APPLIANCE] or
            self.environment[ohostedcons.CoreEnv.ROLLBACK_UPGRADE]
        )
    )
    def _misc_backup_disk(self):
        if self.environment[ohostedcons.CoreEnv.UPGRADING_APPLIANCE]:
            verb = _('Creating')
            action = _('created')
        elif self.environment[ohostedcons.CoreEnv.ROLLBACK_UPGRADE]:
            verb = _('Restoring')
            action = _('restored')
        self.logger.info(_(
            '{v} a backup of the engine VM disk '
            '(could take a few minutes depending on archive size)'
        ).format(v=verb))
        enginevm_disk_path = self._get_image_path(
            self.environment[ohostedcons.StorageEnv.IMG_UUID],
            self.environment[ohostedcons.StorageEnv.VOL_UUID],
        )
        backup_disk_path = self._get_image_path(
            self.environment[ohostedcons.Upgrade.BACKUP_IMG_UUID],
            self.environment[ohostedcons.Upgrade.BACKUP_VOL_UUID],
        )
        if self.environment[ohostedcons.CoreEnv.UPGRADING_APPLIANCE]:
            source = enginevm_disk_path
            destination = backup_disk_path
        elif self.environment[ohostedcons.CoreEnv.ROLLBACK_UPGRADE]:
            source = backup_disk_path
            destination = enginevm_disk_path
        created = ohostedutil.transferImage(
            self,
            source,
            destination,
        )
        if created[0] == 0:
            self.logger.info(_('Successfully {a}').format(a=action))

    @plugin.event(
        stage=plugin.Stages.STAGE_CLEANUP,
        condition=lambda self: not self.environment[
            ohostedcons.CoreEnv.ANSIBLE_DEPLOYMENT
        ]
    )
    def _cleanup(self):
        if self._image_path and os.path.exists(self._image_path):
            os.unlink(self._image_path)


# vim: expandtab tabstop=4 shiftwidth=4
