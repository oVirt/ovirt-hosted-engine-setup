#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2013-2016 Red Hat, Inc.
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
from otopi import context as otopicontext
from otopi import plugin
from otopi import util


from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """Misc plugin."""

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
        priority=plugin.Stages.PRIORITY_FIRST,
    )
    def _setup(self):
        self.dialog.note(
            _(
                'During customization use CTRL-D to abort.'
            )
        )
        interactive = self.environment[
            ohostedcons.CoreEnv.DEPLOY_PROCEED
        ] is None
        if interactive:
            self.environment[
                ohostedcons.CoreEnv.DEPLOY_PROCEED
            ] = self.dialog.queryString(
                name=ohostedcons.Confirms.DEPLOY_PROCEED,
                note=_(
                    'Continuing will configure this host for serving as '
                    'hypervisor and create a VM where you have to install '
                    'the engine afterwards.\n'
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
        try:
            # avoid: pyflakes 'Config' imported but unused error
            import ovirt.node.utils.fs
            if hasattr(ovirt.node.utils.fs, 'Config'):
                self.environment[ohostedcons.CoreEnv.NODE_SETUP] = True
        except ImportError:
            self.logger.debug('Disabling persisting file configuration')

    @plugin.event(
        stage=plugin.Stages.STAGE_TERMINATE,
        priority=plugin.Stages.PRIORITY_LAST,
    )
    def _terminate(self):
        if self.environment[otopicons.BaseEnv.ERROR]:
            self.logger.error(_(
                'Hosted Engine deployment failed: this system is not reliable,'
                ' please check the issue, fix and redeploy'
            ))
            self.dialog.note(
                text=_('Log file is located at {path}').format(
                    path=self.environment[
                        otopicons.CoreEnv.LOG_FILE_NAME
                    ],
                ),
            )
        else:
            self.logger.info(_('Hosted Engine successfully set up'))


# vim: expandtab tabstop=4 shiftwidth=4
