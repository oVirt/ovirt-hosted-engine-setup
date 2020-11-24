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
import hashlib
import math
import os
import shutil
import tarfile
import tempfile

from otopi import plugin
from otopi import util

from vdsm.client import ServerError

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup.ovf import ovfenvelope

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


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
                    '[{s}]\n'.format(s=fakesection) + stream.read()
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
            ] = int(float(
                disk.attrib['{http://schemas.dmtf.org/ovf/envelope/1/}size']
            ))+1
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
            ohostedcons.VMEnv.APPLIANCE_VERSION,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.OVF_SIZE_GB,
            None,
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
            ohostedcons.Stages.CONFIG_OVF_IMPORT,
        ),
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
                            '\nIf you want to deploy with a custom engine '
                            'appliance image, '
                            'please specify the path to '
                            'the OVA archive you would like to use.\n'
                            'Entering no value will use '
                            'the image from the {rpmname} rpm, installing it '
                            'if needed.\n'
                            'Appliance image path []: '
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


# vim: expandtab tabstop=4 shiftwidth=4
