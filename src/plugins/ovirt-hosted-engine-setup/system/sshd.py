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
sshd service handler plugin.
"""


import gettext


from otopi import plugin
from otopi import util


from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    sshd service handler plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.NetworkEnv.SSHD_PORT,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        self.command.detect('sshd')

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_SYSTEM,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_SYSTEM,
        ),
    )
    def _customization(self):
        if not self.services.exists(name='sshd'):
            raise RuntimeError(_('sshd service is required'))
        if self.environment[ohostedcons.NetworkEnv.SSHD_PORT] is None:
            self.environment.setdefault(
                ohostedcons.NetworkEnv.SSHD_PORT,
                ohostedcons.Defaults.DEFAULT_SSHD_PORT
            )
            rc, stdout, _stderr = self.execute(
                args=(
                    self.command.get('sshd'),
                    '-T',
                ),
            )
            if rc == 0:
                for line in stdout:
                    words = line.split()
                    if words[0] == 'port':
                        self.environment[
                            ohostedcons.NetworkEnv.SSHD_PORT
                        ] = int(words[1])
                        break

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        name=ohostedcons.Stages.SSHD_START,
    )
    def _misc(self):
        if not self.services.status(name='sshd'):
            self.services.state(
                name='sshd',
                state=True,
            )

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
    )
    def _closeup(self):
        self.services.startup(
            name='sshd',
            state=True
        )


# vim: expandtab tabstop=4 shiftwidth=4
