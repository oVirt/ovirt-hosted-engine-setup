#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2013-2015 Red Hat, Inc.
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
import hashlib
from io import StringIO
import json
import os
import shutil
import tarfile
import tempfile


from otopi import plugin
from otopi import transaction
from otopi import util


from ovirt_hosted_engine_ha.lib import heconflib
from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import domains as ohosteddomains
from ovirt_hosted_engine_setup.ovf import ovfenvelope


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


# TODO: avoid the transaction or complete it
# now there is just one element without any rollback action
class ImageTransaction(transaction.TransactionElement):
    """Image transaction element."""

    def __init__(self, parent, tar, src, dst):
        super(ImageTransaction, self).__init__()
        self._parent = parent
        self._tar = tar
        self._src = src
        self._dst = dst
        self._prepared = False

    def __str__(self):
        return _("Image Transaction")

    def _get_volume_path(self):
        """
        Return path of the volume file inside the domain
        """
        return heconflib.get_volume_path(
            self._parent.environment[
                ohostedcons.StorageEnv.DOMAIN_TYPE
            ],
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
        size = cli.getVolumeSize(
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

        if size['status']['code']:
            raise RuntimeError(size['status']['message'])
        destination_size = int(size['apparentsize'])
        if destination_size != source_size:
            raise RuntimeError(
                _(
                    'Incoherence detected in OVF file: image size {source} '
                    'does not match declared size {destination}'
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
        try:
            self._parent.execute(
                (
                    self._parent.command.get('sudo'),
                    '-u',
                    'vdsm',
                    '-g',
                    'kvm',
                    self._parent.command.get('qemu-img'),
                    'convert',
                    '-O',
                    'raw',
                    source,
                    destination
                ),
                raiseOnError=True
            )
        except RuntimeError as e:
            self._parent.logger.debug('error uploading the image: ' + str(e))
            return (1, str(e))
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

    def _detect_appliances(self):
        self.logger.info(_('Detecting available oVirt engine appliances'))
        appliances = []
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
                app = {k: config.get(fakesection, k)
                       for k in keys
                       }
                app.update(
                    {'index': str(len(appliances) + 1)}
                )
                appliances.append(app)
            else:
                self.logger.error('error parsing: ' + cf)
        self.logger.debug('available appliances: ' + str(appliances))
        if not appliances:
            self.logger.info(_(
                'No engine appliance image is available on your system.'
            ))
            self.dialog.note(_(
                'Using an oVirt engine appliance could greatly speed-up '
                'ovirt hosted-engine deploy.\n'
                'You could get oVirt engine appliance installing '
                'ovirt-engine-appliance rpm.'
            ))
        return appliances

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
                ohostedcons.StorageEnv.IMAGE_SIZE_GB
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
                self.logger.warning(
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

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.VMEnv.OVF,
            None
        )
        self.environment.setdefault(
            ohostedcons.CoreEnv.TEMPDIR,
            os.getenv('TMPDIR', ohostedcons.Defaults.DEFAULT_TEMPDIR)
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        self.command.detect('sudo')
        self.command.detect('qemu-img')

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_VM,
            ohostedcons.Stages.CONFIG_BOOT_DEVICE,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_VM,
        ),
        condition=lambda self: (
            self.environment[ohostedcons.VMEnv.BOOT] == 'disk' and
            not self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]
        ),
        name=ohostedcons.Stages.CONFIG_OVF_IMPORT,
    )
    def _customization(self):
        interactive = self.environment[
            ohostedcons.VMEnv.OVF
        ] is None
        appliances = []
        if interactive:
            appliances = self._detect_appliances()
            if appliances:
                directlyOVA = str(len(appliances) + 1)
                app_list = ''
                for entry in appliances:
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
            if not interactive:
                ova_path = self.environment[ohostedcons.VMEnv.OVF]
            else:
                ova_path = ''
                if appliances:
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
                            str(i + 1) for i in range(len(appliances) + 1)
                        ],
                    )
                    if sapp != directlyOVA:
                        ova_path = appliances[int(sapp) - 1]['path']
                        self.logger.info(_('Verifying its sha1sum'))
                        if (
                            self._file_hash(ova_path) !=
                            appliances[int(sapp) - 1]['sha1sum']
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
            try:
                checker.check_available_space(
                    self.environment[ohostedcons.CoreEnv.TEMPDIR],
                    int(
                        self.environment[ohostedcons.StorageEnv.IMAGE_SIZE_GB]
                    ) * 1024
                )
                valid = True
            except ohosteddomains.InsufficientSpaceError as e:
                self.logger.debug(
                    'Error checking TMPDIR space',
                    exc_info=True,
                )
                self.logger.debug(e)
                valid = False
                errorMessage = _(
                    'Not enough space in the temporary directory [{tmpdir}]'
                ).format(
                    tmpdir=self.environment[
                        ohostedcons.CoreEnv.TEMPDIR
                    ],
                )
                if not interactive:
                    raise RuntimeError(errorMessage)
                else:
                    self.logger.error(errorMessage)
                    self.environment[
                        ohostedcons.CoreEnv.TEMPDIR
                    ] = self.dialog.queryString(
                        name='OVEHOSTED_COREENV_TEMPDIR',
                        note=_(
                            'Please specify path to a temporary directory '
                            'with at least {size} GB [@DEFAULT@]: '
                        ).format(
                            size=self.environment[
                                ohostedcons.StorageEnv.IMAGE_SIZE_GB
                            ],
                        ),
                        prompt=True,
                        caseSensitive=True,
                        default=str(self.environment[
                            ohostedcons.CoreEnv.TEMPDIR
                        ]),
                    )

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        name=ohostedcons.Stages.OVF_IMPORTED,
        after=(
            ohostedcons.Stages.VM_IMAGE_AVAILABLE,
        ),
        condition=lambda self: (
            self.environment[ohostedcons.VMEnv.BOOT] == 'disk' and
            not self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]
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
                )
            )

    @plugin.event(
        stage=plugin.Stages.STAGE_CLEANUP,
    )
    def _cleanup(self):
        if self._image_path and os.path.exists(self._image_path):
            os.unlink(self._image_path)


# vim: expandtab tabstop=4 shiftwidth=4
