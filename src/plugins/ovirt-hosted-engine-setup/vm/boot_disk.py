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


"""
VM disk import plugin.
"""


import gettext
import os
import shutil
import tarfile
import tempfile


from otopi import util
from otopi import plugin
from otopi import transaction


from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup.ovf import ovfenvelope
from ovirt_hosted_engine_setup import domains as ohosteddomains


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


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
        serv = self._parent.environment[ohostedcons.VDSMEnv.VDS_CLI]
        status, message = serv.uploadVolume([
            self._parent.environment[ohostedcons.StorageEnv.SD_UUID],
            self._parent.environment[ohostedcons.StorageEnv.SP_UUID],
            self._parent.environment[ohostedcons.StorageEnv.IMG_UUID],
            self._parent.environment[ohostedcons.StorageEnv.VOL_UUID],
            self._dst,
            str(
                self._parent.environment[
                    ohostedcons.StorageEnv.IMAGE_SIZE_GB
                ]
            ),
        ])
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
            tempfile.gettempdir()
        )

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
            self.environment[
                ohostedcons.StorageEnv.IMAGE_DESC
            ] = disk.attrib[
                '{http://schemas.dmtf.org/ovf/envelope/1/}disk-alias'
            ]
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
                ohostedcons.VMEnv.VCPUS
            ] = num_of_sockets * cpu_per_socket
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
            self.environment[
                ohostedcons.VMEnv.MEM_SIZE_MB
            ] = int(
                tree.find(
                    'Content/Section/Item/{'
                    'http://schemas.dmtf.org/wbem/wscim/1/cim-schema'
                    '/2/CIM_ResourceAllocationSettingData'
                    '}VirtualQuantity'
                ).text
            )
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
            #decode ovf file content
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
        valid = False
        while not valid:
            if interactive:
                self.environment[
                    ohostedcons.VMEnv.OVF
                ] = self.dialog.queryString(
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

            valid = self._check_ovf(self.environment[ohostedcons.VMEnv.OVF])
            if not valid:
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
            except RuntimeError as e:
                self.logger.debug(
                    'Error checking TMPDIR space',
                    exc_info=True,
                )
                self.logger.error(e)
                valid = False
                if not interactive:
                    raise e
                else:
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
