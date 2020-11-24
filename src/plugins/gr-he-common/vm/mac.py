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
VM MAC address configuration plugin.
"""


import gettext

from otopi import plugin
from otopi import util

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import util as ohostedutil


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    VM MAC address configuration plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.VMEnv.MAC_ADDR,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.CONFIG_OVF_IMPORT,
            ohostedcons.Stages.DIALOG_TITLES_S_VM,
            ohostedcons.Stages.CUSTOMIZATION_CPU_NUMBER,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_VM,
        ),
        name=ohostedcons.Stages.CUSTOMIZATION_MAC_ADDRESS,
    )
    def _customization(self):
        interactive = self.environment[
            ohostedcons.VMEnv.MAC_ADDR
        ] is None
        default_mac = ohostedutil.randomMAC()
        valid = False
        while not valid:
            if interactive:
                self.environment[
                    ohostedcons.VMEnv.MAC_ADDR
                ] = self.dialog.queryString(
                    name='ovehosted_vmenv_mac',
                    note=_(
                        'Please specify a unicast MAC address for the VM, or '
                        'accept a randomly generated default [@DEFAULT@]: '
                    ),
                    prompt=True,
                    default=default_mac,
                ).strip()
            valid = ohostedutil.validMAC(
                self.environment[ohostedcons.VMEnv.MAC_ADDR]
            )
            if not valid and not interactive:
                raise RuntimeError(
                    _(
                        'Invalid unicast MAC address specified: \'{mac}\''
                    ).format(
                        mac=self.environment[
                            ohostedcons.VMEnv.MAC_ADDR
                        ],
                    )
                )
            if not valid and interactive:
                self.logger.error(
                    _(
                        'Invalid unicast MAC address specified: \'{mac}\''
                    ).format(
                        mac=self.environment[
                            ohostedcons.VMEnv.MAC_ADDR
                        ],
                    )
                )


# vim: expandtab tabstop=4 shiftwidth=4
