#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2014 Red Hat, Inc.
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
Hosted Engine Disk adder plugin.
"""


import gettext


import ovirtsdk.api
import ovirtsdk.xml
import ovirtsdk.infrastructure.errors


from otopi import util
from otopi import plugin


from ovirt_hosted_engine_setup import constants as ohostedcons


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    Hosted Engine Disk adder plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.StorageEnv.IMG_ALIAS,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        condition=lambda self: not self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_VM,
            ohostedcons.Stages.CONFIG_OVF_IMPORT,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_VM,
        ),
    )
    def _customization(self):
        if self.environment[ohostedcons.StorageEnv.IMG_ALIAS] is None:
            self.environment[
                ohostedcons.StorageEnv.IMG_ALIAS
            ] = self.dialog.queryString(
                name='OVEHOSTED_STORAGE_IMG_ALIAS',
                note=_(
                    'Please specify an alias for the Hosted Engine image '
                    '[@DEFAULT@]: '
                ),
                prompt=True,
                default=ohostedcons.Defaults.DEFAULT_IMAGE_ALIAS,
            )

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        after=(
            ohostedcons.Stages.HOST_ADDED,
        ),
        condition=(
            lambda self: self.environment[
                ohostedcons.StorageEnv.DOMAIN_TYPE
            ] == ohostedcons.DomainTypes.ISCSI and
            not self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]
        ),
    )
    def _closeup(self):
        lun = ovirtsdk.xml.params.LogicalUnit(
            id=self.environment[ohostedcons.StorageEnv.GUID],
            address=self.environment[ohostedcons.StorageEnv.ISCSI_IP_ADDR],
            port=int(self.environment[ohostedcons.StorageEnv.ISCSI_PORT]),
            target=self.environment[ohostedcons.StorageEnv.ISCSI_TARGET],
            username=self.environment[ohostedcons.StorageEnv.ISCSI_USER],
            password=self.environment[ohostedcons.StorageEnv.ISCSI_PASSWORD],
        )
        disk = ovirtsdk.xml.params.Disk(
            alias=self.environment[ohostedcons.StorageEnv.IMG_ALIAS],
            description=self.environment[ohostedcons.StorageEnv.IMAGE_DESC],
            interface='virtio_scsi',
            sgio='unfiltered',
            format='raw',
            lun_storage=ovirtsdk.xml.params.Storage(
                type_='iscsi',
                logical_unit=[
                    lun,
                ],
            ),
        )
        try:
            self.logger.debug('Connecting to the Engine')
            engine_api = ovirtsdk.api.API(
                url='https://{fqdn}/ovirt-engine/api'.format(
                    fqdn=self.environment[
                        ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
                    ],
                ),
                username='admin@internal',
                password=self.environment[
                    ohostedcons.EngineEnv.ADMIN_PASSWORD
                ],
                ca_file=self.environment[
                    ohostedcons.EngineEnv.TEMPORARY_CERT_FILE
                ],
            )
            # check if the disk is already there
            known_disks = engine_api.disks.list()
            for check_disk in known_disks:
                if check_disk.get_alias() == self.environment[
                    ohostedcons.StorageEnv.IMG_ALIAS
                ]:
                    self.logger.info(
                        _(
                            'The Hosted Engine disk alias has been found '
                            'in the Engine, not adding it'
                        )
                    )
                    break
                check_lun_storage = check_disk.get_lun_storage()
                lun_list = check_lun_storage.get_logical_unit()
                for check_logical_unit in lun_list:
                    if check_logical_unit.get_id() == self.environment[
                        ohostedcons.StorageEnv.GUID
                    ]:
                        self.logger.info(
                            _(
                                'The Hosted Engine disk GUID has been found '
                                'in the Engine, not adding it'
                            )
                        )
                        break
            else:
                engine_api.disks.add(disk)
        except ovirtsdk.infrastructure.errors.RequestError:
            self.logger.debug(
                'Cannot add the Hosted Engine VM Disk to the engine',
                exc_info=True,
            )
            self.logger.error(
                _('Cannot add the Hosted Engine VM Disk to the engine')
            )
            raise RuntimeError(
                _('Cannot add the Hosted Engine VM Disk to the engine')
            )
        engine_api.disconnect()


# vim: expandtab tabstop=4 shiftwidth=4
