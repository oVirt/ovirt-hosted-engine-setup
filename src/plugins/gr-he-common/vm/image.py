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
VM image creation plugin.
"""


import gettext
import uuid

from otopi import plugin
from otopi import util

from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


def _int_or_0(x):
    return int(x) if x else 0


@util.export
class Plugin(plugin.PluginBase):
    """
    VM image creation plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    def _customize_disk_size(self, available_gb=None):
        interactive = self.environment[
            ohostedcons.StorageEnv.IMAGE_SIZE_GB
        ] is None
        default = max(
            _int_or_0(ohostedcons.Defaults.DEFAULT_IMAGE_SIZE_GB),
            _int_or_0(self.environment[ohostedcons.StorageEnv.OVF_SIZE_GB])
        )

        valid = False
        while not valid:
            if interactive:
                self.environment[
                    ohostedcons.StorageEnv.IMAGE_SIZE_GB
                ] = self.dialog.queryString(
                    name='ovehosted_vmenv_image',
                    note=_(
                        'Please specify the size of the VM disk in GiB: '
                        '[@DEFAULT@]: '
                    ),
                    prompt=True,
                    default=default,
                )
            try:
                valid = True
                if available_gb is not None and (
                    int(
                        self.environment[
                            ohostedcons.StorageEnv.IMAGE_SIZE_GB
                        ]
                    ) + ohostedcons.Const.OVFSTORE_SIZE_GIB +
                    ohostedcons.Const.CRITICAL_SPACE_ACTION_BLOCKER
                ) > available_gb:
                    msg = _(
                        'Not enough free space, '
                        'about {estimate} GiB will be available '
                        'within the storage domain '
                        '(required {required} GiB for the engine VM disk '
                        'plus {req_ovf} GiB for the OVF_STORE disks creation)'
                    ).format(
                        estimate=available_gb,
                        required=self.environment[
                            ohostedcons.StorageEnv.IMAGE_SIZE_GB
                        ],
                        req_ovf=(
                            ohostedcons.Const.OVFSTORE_SIZE_GIB +
                            ohostedcons.Const.CRITICAL_SPACE_ACTION_BLOCKER
                        ),
                    )
                    self.logger.warning(msg)
                    valid = False
                    if not interactive:
                        raise RuntimeError(msg)

                if valid and self.environment[
                    ohostedcons.StorageEnv.OVF_SIZE_GB
                ] and int(
                    self.environment[ohostedcons.StorageEnv.OVF_SIZE_GB]
                ) > int(
                    self.environment[ohostedcons.StorageEnv.IMAGE_SIZE_GB]
                ):
                    msg = _(
                        'Minimum requirements to fit the disk from the '
                        'appliance OVF not met (required {required} GiB)'
                    ).format(
                        required=self.environment[
                            ohostedcons.StorageEnv.OVF_SIZE_GB
                        ],
                    )
                    self.logger.warning(msg)
                    valid = False
                    if not interactive:
                        raise RuntimeError(msg)

                if valid and int(
                    self.environment[ohostedcons.StorageEnv.IMAGE_SIZE_GB]
                ) < ohostedcons.Defaults.DEFAULT_IMAGE_SIZE_GB:
                    self.logger.warning(
                        _('Minimum requirements for disk size not met')
                    )
                    if (
                        interactive and
                        self.environment[
                            ohostedcons.CoreEnv.REQUIREMENTS_CHECK_ENABLED
                        ] and
                        not self.dialog.queryString(
                            name=ohostedcons.Confirms.DISK_PROCEED,
                            note=_(
                                'Continue with specified disk size? '
                                '(@VALUES@)[@DEFAULT@]: '
                            ),
                            prompt=True,
                            validValues=(_('Yes'), _('No')),
                            caseSensitive=False,
                            default=_('No')
                        ) == _('Yes').lower()
                    ):
                        valid = False
            except ValueError:
                valid = False
                if not interactive:
                    raise RuntimeError(
                        _('Invalid disk size specified: {size}').format(
                            size=self.environment[
                                ohostedcons.StorageEnv.IMAGE_SIZE_GB
                            ],
                        )
                    )
                else:
                    self.logger.error(
                        _('Invalid disk size specified: {size}').format(
                            size=self.environment[
                                ohostedcons.StorageEnv.IMAGE_SIZE_GB
                            ],
                        )
                    )

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.StorageEnv.IMAGE_SIZE_GB,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.BDEVICE_SIZE_GB,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.IMG_UUID,
            str(uuid.uuid4())
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.VOL_UUID,
            str(uuid.uuid4())
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.IMAGE_DESC,
            ohostedcons.Defaults.DEFAULT_IMAGE_DESC
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        after=(
            ohostedcons.Stages.ANSIBLE_CREATE_SD,
        ),
        name=ohostedcons.Stages.ANSIBLE_CUSTOMIZE_DISK_SIZE,
    )
    def _closeup_ansible(self):
        self._customize_disk_size(available_gb=self.environment[
            ohostedcons.StorageEnv.BDEVICE_SIZE_GB
        ])

# vim: expandtab tabstop=4 shiftwidth=4
