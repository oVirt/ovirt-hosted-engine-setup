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
VM configuration plugin.
"""


import gettext
import uuid

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

    """
    VM configuration plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.VMEnv.VM_UUID,
            str(uuid.uuid4())
        )
        self.environment[ohostedcons.VMEnv.SUBST] = {}
        self.environment.setdefault(
            ohostedcons.VMEnv.CDROM_UUID,
            str(uuid.uuid4())
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.NIC_UUID,
            str(uuid.uuid4())
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.CONSOLE_UUID,
            str(uuid.uuid4())
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        name=ohostedcons.Stages.VM_CONFIGURED,
        after=(
            ohostedcons.Stages.VM_IMAGE_AVAILABLE,
            ohostedcons.Stages.BRIDGE_AVAILABLE,
            ohostedcons.Stages.STORAGE_POOL_DESTROYED,
        ),
    )
    def _misc(self):
        self.logger.info(_('Configuring VM'))
        subst = {
            '@SP_UUID@': ohostedcons.Const.BLANK_UUID,
            '@SD_UUID@': self.environment[
                ohostedcons.StorageEnv.SD_UUID
            ],
            '@VOL_UUID@': self.environment[
                ohostedcons.StorageEnv.VOL_UUID
            ],
            '@IMG_UUID@': self.environment[
                ohostedcons.StorageEnv.IMG_UUID
            ],
            '@VM_UUID@': self.environment[
                ohostedcons.VMEnv.VM_UUID
            ],
            '@MEM_SIZE@': self.environment[
                ohostedcons.VMEnv.MEM_SIZE_MB
            ],
            '@MAC_ADDR@': self.environment[
                ohostedcons.VMEnv.MAC_ADDR
            ],
            '@NAME@': ohostedcons.Const.HOSTED_ENGINE_VM_NAME,
            '@CONSOLE_TYPE@': self.environment[
                ohostedcons.VMEnv.CONSOLE_TYPE
            ],
            '@VCPUS@': self.environment[
                ohostedcons.VMEnv.VCPUS
            ],
            '@MAXVCPUS@': self.environment[
                ohostedcons.VMEnv.MAXVCPUS
            ],
            '@CPU_TYPE@': self.environment[
                ohostedcons.VDSMEnv.VDSM_CPU
            ].replace('model_', ''),
            '@EMULATED_MACHINE@': self.environment[
                ohostedcons.VMEnv.EMULATED_MACHINE
            ],
            '@CDROM_UUID@': self.environment[
                ohostedcons.VMEnv.CDROM_UUID
            ],
            '@NIC_UUID@': self.environment[
                ohostedcons.VMEnv.NIC_UUID
            ],
            '@CONSOLE_UUID@': self.environment[
                ohostedcons.VMEnv.CONSOLE_UUID
            ],
            '@BRIDGE@': self.environment[
                ohostedcons.NetworkEnv.BRIDGE_NAME
            ],
        }

        if self.environment[ohostedcons.VMEnv.CONSOLE_TYPE] == 'vnc':
            subst['@VIDEO_DEVICE@'] = 'vga'
        else:
            subst['@VIDEO_DEVICE@'] = 'qxl'

        if self.environment[
            ohostedcons.VMEnv.CDROM
        ]:
            subst['@CDROM@'] = self.environment[
                ohostedcons.VMEnv.CDROM
            ]
        else:
            subst['@CDROM@'] = ''

        content = ohostedutil.processTemplate(
            template=ohostedcons.FileLocations.ENGINE_VM_TEMPLATE,
            subst=subst,
        )
        self.environment[ohostedcons.VMEnv.SUBST] = subst
        with transaction.Transaction() as localtransaction:
            localtransaction.append(
                filetransaction.FileTransaction(
                    name=ohostedcons.FileLocations.ENGINE_VM_CONF,
                    content=content,
                    modifiedList=self.environment[
                        otopicons.CoreEnv.MODIFIED_FILES
                    ],
                    mode=0o600,
                    owner=ohostedcons.Defaults.DEFAULT_SYSTEM_USER_VDSM,
                    group=ohostedcons.Defaults.DEFAULT_SYSTEM_GROUP_KVM,
                    enforcePermissions=True,
                ),
            )


# vim: expandtab tabstop=4 shiftwidth=4
