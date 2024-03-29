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


"""Shell detection plugin."""


import gettext
import os

from otopi import constants as otopicons
from otopi import context
from otopi import plugin
from otopi import util

from ovirt_setup_lib import dialog

from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """Shell detection plugin."""

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
        priority=plugin.Stages.PRIORITY_HIGH,
        condition=lambda self: (
            not self.environment[otopicons.BaseEnv.ABORTED]
        ),
    )
    def _setup(self):
        self.environment.setdefault(
            ohostedcons.CoreEnv.SKIP_TTY_CHECK,
            False
        )
        self.environment.setdefault(
            ohostedcons.CoreEnv.TMUX_PROCEED,
            None
        )
        self.environment.setdefault(
            ohostedcons.CoreEnv.FORCE_IP_PROCEED,
            None
        )
        ssh_connected = not os.getenv('SSH_CLIENT') is None
        skip_tty_check = self.environment[
            ohostedcons.CoreEnv.SKIP_TTY_CHECK
        ]
        if not skip_tty_check:
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
        tmux_used = os.getenv('TERM') == 'screen'
        if ssh_connected and not tmux_used:
            interactive = self.environment[
                ohostedcons.CoreEnv.TMUX_PROCEED
            ] is None
            if interactive:
                self.environment[
                    ohostedcons.CoreEnv.TMUX_PROCEED
                ] = self.dialog.queryString(
                    name=ohostedcons.Confirms.TMUX_PROCEED,
                    note=_(
                        'It has been detected that this program is executed '
                        'through an SSH connection without using tmux.\n'
                        'Continuing with the installation may lead to broken '
                        'installation if the network connection fails.\n'
                        'It is highly recommended to abort the installation '
                        'and run it inside a tmux session using command '
                        '"tmux".\n'
                        'Do you want to continue anyway? '
                        '(@VALUES@)[@DEFAULT@]: '
                    ),
                    prompt=True,
                    validValues=(_('Yes'), _('No')),
                    caseSensitive=False,
                    default=_('No')
                ) == _('Yes').lower()
                if not self.environment[ohostedcons.CoreEnv.TMUX_PROCEED]:
                    raise context.Abort('Aborted by user')

        if (
            not self.environment[ohostedcons.NetworkEnv.FORCE_IPV4]
            and not self.environment[ohostedcons.NetworkEnv.FORCE_IPV6]
        ):
            dialog.queryEnvKey(
                dialog=self.dialog,
                logger=self.logger,
                env=self.environment,
                key=ohostedcons.CoreEnv.FORCE_IP_PROCEED,
                name='FORCE_IP_PROCEED',
                note=_(
                    '\nIf you run "hosted-engine --deploy" without the '
                    '"--4" or "--6" option in a dual-stack environment, '
                    'the default is IPv6.\n'
                    'You must ensure that your DNS returns only '
                    'IPv6 addresses.\n'
                    'See: https://ovirt.org/documentation/installing_ovirt'
                    '_as_a_self-hosted_engine_using_the_command_line/'
                    'index.html#Deploying_the_Self-Hosted_Engine_Using_'
                    'the_CLI_install_RHVM\n'
                    'Do you want to continue anyway? (@VALUES@)[@DEFAULT@]: '
                ),
                prompt=True,
                validValues=(_('Yes'), _('No')),
                caseSensitive=False,
                default=_('No'),
            )
            if self.environment[ohostedcons.CoreEnv.FORCE_IP_PROCEED] == 'no':
                raise context.Abort('Aborted by user')

# vim: expandtab tabstop=4 shiftwidth=4
