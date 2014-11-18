#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2013-2014 Red Hat, Inc.
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


"""Shell detection plugin."""

import gettext
import os


from otopi import util
from otopi import context
from otopi import plugin
from otopi import constants as otopicons


from ovirt_hosted_engine_setup import constants as ohostedcons


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """Shell detection plugin."""

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
        priority=plugin.Stages.PRIORITY_HIGH,
        condition=lambda self: not self.environment[otopicons.BaseEnv.ABORTED],
    )
    def _setup(self):
        self.environment.setdefault(
            ohostedcons.CoreEnv.SCREEN_PROCEED,
            None
        )
        ssh_connected = not os.getenv('SSH_CLIENT') is None
        if ssh_connected and os.getenv('TERM') is None:
            self.logger.error(
                _(
                    'It has been detected that this program is executed '
                    'through an SSH connection without pseudo-tty '
                    'allocation.\n'
                    'Please run again ssh adding -t option\n'
                )
            )
            raise context.Abort('Aborted due to missing requirement')
        screen_used = os.getenv('TERM') == 'screen'
        if ssh_connected and not screen_used:
            interactive = self.environment[
                ohostedcons.CoreEnv.SCREEN_PROCEED
            ] is None
            if interactive:
                self.environment[
                    ohostedcons.CoreEnv.SCREEN_PROCEED
                ] = self.dialog.queryString(
                    name=ohostedcons.Confirms.SCREEN_PROCEED,
                    note=_(
                        'It has been detected that this program is executed '
                        'through an SSH connection without using screen.\n'
                        'Continuing with the installation may lead to broken '
                        'installation if the network connection fails.\n'
                        'It is highly recommended to abort the installation '
                        'and run it inside a screen session using command '
                        '"screen".\n'
                        'Do you want to continue anyway? '
                        '(@VALUES@)[@DEFAULT@]: '
                    ),
                    prompt=True,
                    validValues=(_('Yes'), _('No')),
                    caseSensitive=False,
                    default=_('No')
                ) == _('Yes').lower()
                if not self.environment[ohostedcons.CoreEnv.SCREEN_PROCEED]:
                    raise context.Abort('Aborted by user')


# vim: expandtab tabstop=4 shiftwidth=4
