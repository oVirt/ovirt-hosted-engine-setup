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


"""FQDN plugin."""


import gettext

from otopi import plugin
from otopi import util

from ovirt_setup_lib import hostname as osetuphostname

from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """Misc plugin."""

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN,
            None
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.FQDN_REVERSE_VALIDATION,
            False
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        self._hostname_helper = osetuphostname.Hostname(plugin=self)

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_ENGINE,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_ENGINE,
        ),
    )
    def _customization(self):
        if (
            self.environment[
                ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
            ] is None and
            self.environment[
                ohostedcons.CloudInit.INSTANCE_HOSTNAME
            ]
        ):
            self.environment[
                ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
            ] = self.environment[
                ohostedcons.CloudInit.INSTANCE_HOSTNAME
            ]

        self._hostname_helper.getHostname(
            envkey=ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN,
            whichhost='ENGINEVM_HOSTNAME',
            supply_default=False,
            prompttext=_(
                'Please provide the FQDN for the engine '
                'you would like to use.\nThis needs to match '
                'the FQDN that you will use for the engine '
                'installation within the VM.\n'
                'Note: This will be the FQDN of the VM '
                'you are now going to create,\nit should not '
                'point to the base host or to any other '
                'existing machine.\nEngine FQDN: '
            ),
            dialog_name='OVEHOSTED_NETWORK_FQDN',
            validate_syntax=True,
            system=True,
            dns=False,
            local_non_loopback=False,
            reverse_dns=self.environment[
                ohostedcons.NetworkEnv.FQDN_REVERSE_VALIDATION
            ],
            not_local=True,
            not_local_text=_(
                'Please input the hostname for the engine VM, '
                'not for this host.'
            ),
            allow_empty=False,
        )

# vim: expandtab tabstop=4 shiftwidth=4
