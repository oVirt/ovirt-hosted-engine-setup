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


"""Misc plugin."""


import gettext


from otopi import constants as otopicons
from otopi import util
from otopi import context
from otopi import plugin


from ovirt_hosted_engine_setup import constants as ohostedcons


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """Misc plugin."""

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_BOOT,
        before=[
            otopicons.Stages.CORE_LOG_INIT,
            otopicons.Stages.CORE_CONFIG_INIT,
        ],
    )
    def _preinit(self):
        self.environment.setdefault(
            otopicons.CoreEnv.LOG_FILE_NAME_PREFIX,
            ohostedcons.FileLocations.OVIRT_HOSTED_ENGINE_SETUP
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
        priority=plugin.Stages.PRIORITY_FIRST,
    )
    def _confirm(self):
        if not self.dialog.confirm(
            name=ohostedcons.Confirms.DEPLOY_PROCEED,
            description='Proceed with ovirt-hosted-engine-setup',
            note=_(
                'Continuing will configure this host for serving '
                'as hypervisor and create a VM where oVirt Engine '
                'will be installed afterwards.\n'
                'Are you sure you want to continue? (yes/no) '
            ),
            prompt=True,
        ):
            raise context.Abort('Aborted by user')

        self.environment.setdefault(
            ohostedcons.CoreEnv.REQUIREMENTS_CHECK_ENABLED,
            True
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
    )
    def _customization(self):
        self.environment[
            ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
        ] = self.dialog.queryString(
            name='ovehosted_network_fqdn',
            note=_(
                'Please provide the FQDN for the engine '
                'you would like to use. This needs to match '
                'the FQDN that you will use for the engine '
                'installation within the VM: '
            ),
            prompt=True,
            caseSensitive=True,
        )

        # Validate the FQDN ?

# vim: expandtab tabstop=4 shiftwidth=4
