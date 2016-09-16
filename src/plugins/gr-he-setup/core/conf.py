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


"""Core plugin."""


import gettext

from otopi import constants as otopicons
from otopi import filetransaction
from otopi import plugin
from otopi import transaction
from otopi import util

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import util as ohostedutil


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """Misc plugin."""

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        after=(
            ohostedcons.Stages.VM_IMAGE_AVAILABLE,
            ohostedcons.Stages.BRIDGE_AVAILABLE,
            ohostedcons.Stages.CONF_VOLUME_AVAILABLE,
            ohostedcons.Stages.VM_CONFIGURED,
        ),
        name=ohostedcons.Stages.SAVE_CONFIG,
    )
    def _misc(self):
        self.logger.info(_('Updating hosted-engine configuration'))
        subst = {
            '@FQDN@': self.environment[
                ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
            ],
            '@VM_DISK_ID@': self.environment[
                ohostedcons.StorageEnv.IMG_UUID
            ],
            '@VM_DISK_VOL_ID@': self.environment[
                ohostedcons.StorageEnv.VOL_UUID
            ],
            '@SHARED_STORAGE@': self.environment[
                ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
            ],
            '@CONSOLE_TYPE@': self.environment[
                ohostedcons.VMEnv.CONSOLE_TYPE
            ],
            '@VM_UUID@': self.environment[
                ohostedcons.VMEnv.VM_UUID
            ],
            '@CONF_FILE@': ohostedcons.FileLocations.ENGINE_VM_CONF,
            '@HOST_ID@': self.environment[ohostedcons.StorageEnv.HOST_ID],
            '@DOMAIN_TYPE@': self.environment[
                ohostedcons.StorageEnv.DOMAIN_TYPE
            ],
            '@MNT_OPTIONS@': self.environment[
                ohostedcons.StorageEnv.MNT_OPTIONS
            ] or '',
            '@SP_UUID@': self.environment[ohostedcons.StorageEnv.SP_UUID],
            '@SD_UUID@': self.environment[ohostedcons.StorageEnv.SD_UUID],
            '@CONNECTION_UUID@': self.environment[
                ohostedcons.StorageEnv.CONNECTION_UUID
            ],
            '@CA_CERT@': ohostedcons.FileLocations.LIBVIRT_SPICE_CA_CERT,
            '@CA_SUBJECT@': self.environment[
                ohostedcons.VDSMEnv.SPICE_SUBJECT
            ],
            '@VDSM_USE_SSL@': str(
                self.environment[ohostedcons.VDSMEnv.USE_SSL]
            ).lower(),
            '@GATEWAY@': self.environment[ohostedcons.NetworkEnv.GATEWAY],
            '@BRIDGE@': self.environment[
                ohostedcons.NetworkEnv.BRIDGE_NAME
            ],
            '@METADATA_VOLUME_UUID@': self.environment[
                ohostedcons.StorageEnv.METADATA_VOLUME_UUID
            ],
            '@METADATA_IMAGE_UUID@': self.environment[
                ohostedcons.StorageEnv.METADATA_IMAGE_UUID
            ],
            '@LOCKSPACE_VOLUME_UUID@': self.environment[
                ohostedcons.StorageEnv.LOCKSPACE_VOLUME_UUID
            ],
            '@LOCKSPACE_IMAGE_UUID@': self.environment[
                ohostedcons.StorageEnv.LOCKSPACE_IMAGE_UUID
            ],
            '@CONF_VOLUME_UUID@': self.environment[
                ohostedcons.StorageEnv.CONF_VOL_UUID
            ],
            '@CONF_IMAGE_UUID@': self.environment[
                ohostedcons.StorageEnv.CONF_IMG_UUID
            ],
            '@IQN@': '',
            '@PORTAL@': '',
            '@USER@': '',
            '@PASSWORD@': '',
            '@PORT@': '',
        }
        if self.environment[ohostedcons.StorageEnv.DOMAIN_TYPE] in (
            ohostedcons.DomainTypes.ISCSI,
        ):
            # Defaults are ok for NFS and GlusterFS, need to change only
            # for iSCSI
            subst['@SHARED_STORAGE@'] = self.environment[
                ohostedcons.StorageEnv.ISCSI_IP_ADDR
            ]
            subst['@IQN@'] = self.environment[
                ohostedcons.StorageEnv.ISCSI_TARGET
            ]
            subst['@PORTAL@'] = self.environment[
                ohostedcons.StorageEnv.ISCSI_PORTAL
            ]
            subst['@USER@'] = self.environment[
                ohostedcons.StorageEnv.ISCSI_USER
            ]
            subst['@PASSWORD@'] = self.environment[
                ohostedcons.StorageEnv.ISCSI_PASSWORD
            ]
            subst['@PORT@'] = self.environment[
                ohostedcons.StorageEnv.ISCSI_PORT
            ]

        content = ohostedutil.processTemplate(
            template=ohostedcons.FileLocations.OVIRT_HOSTED_ENGINE_TEMPLATE,
            subst=subst
        )
        self.environment[
            ohostedcons.StorageEnv.HECONF_CONTENT
        ] = content
        with transaction.Transaction() as localtransaction:
            localtransaction.append(
                filetransaction.FileTransaction(
                    name=(
                        ohostedcons.FileLocations.
                        OVIRT_HOSTED_ENGINE_SETUP_CONF
                    ),
                    content=content,
                    modifiedList=self.environment[
                        otopicons.CoreEnv.MODIFIED_FILES
                    ],
                ),
            )


# vim: expandtab tabstop=4 shiftwidth=4
