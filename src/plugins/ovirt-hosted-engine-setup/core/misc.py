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
from otopi import context as otopicontext
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
        self.environment.setdefault(
            ohostedcons.CoreEnv.DEPLOY_PROCEED,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
        priority=plugin.Stages.PRIORITY_FIRST,
    )
    def _init(self):
        interactive = self.environment[
            ohostedcons.CoreEnv.DEPLOY_PROCEED
        ] is None
        if interactive:
            self.environment[
                ohostedcons.CoreEnv.DEPLOY_PROCEED
            ] = self.dialog.queryString(
                name=ohostedcons.Confirms.DEPLOY_PROCEED,
                note=_(
                    'Continuing will configure this host for serving '
                    'as hypervisor and create a VM where oVirt Engine '
                    'will be installed afterwards.\n'
                    'Are you sure you want to continue? '
                    '(@VALUES@)[@DEFAULT@]: '
                ),
                prompt=True,
                validValues=(_('Yes'), _('No')),
                caseSensitive=False,
                default=_('Yes')
            ) == _('Yes').lower()
        if not self.environment[ohostedcons.CoreEnv.DEPLOY_PROCEED]:
            raise otopicontext.Abort('Aborted by user')

        self.environment.setdefault(
            ohostedcons.CoreEnv.REQUIREMENTS_CHECK_ENABLED,
            True
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        priority=plugin.Stages.PRIORITY_LAST,
    )
    def _closeup(self):
        self.dialog.note(
            text=_(
                'Hosted Engine successfully set up'
            ),
        )


# vim: expandtab tabstop=4 shiftwidth=4
