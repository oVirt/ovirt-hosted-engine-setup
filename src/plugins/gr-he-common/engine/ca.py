#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2016-2017 Red Hat, Inc.
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
Engine CA plugin.
"""

import gettext

from otopi import constants as otopicons
from otopi import plugin
from otopi import util

from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    Engine CA plugin.
    """

    VDSM_RETRIES = 600
    VDSM_DELAY = 1

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._interactive_admin_pwd = True

    @plugin.event(
        stage=plugin.Stages.STAGE_BOOT,
        before=(
            otopicons.Stages.CORE_LOG_INIT,
        )
    )
    def _boot(self):
        self.environment[otopicons.CoreEnv.LOG_FILTER_KEYS].append(
            ohostedcons.EngineEnv.ADMIN_PASSWORD
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.EngineEnv.ADMIN_PASSWORD,
            None
        )
        self.environment.setdefault(
            ohostedcons.EngineEnv.ADMIN_USERNAME,
            ohostedcons.Defaults.DEFAULT_ADMIN_USERNAME,
        )
        self.environment.setdefault(
            ohostedcons.EngineEnv.TEMPORARY_CERT_FILE,
            None
        )
        self.environment.setdefault(
            ohostedcons.EngineEnv.INSECURE_SSL,
            None
        )
        self.environment[ohostedcons.EngineEnv.INTERACTIVE_ADMIN_PASSWORD] = (
            self.environment[ohostedcons.EngineEnv.ADMIN_PASSWORD] is None
        )

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
        while self.environment[ohostedcons.EngineEnv.ADMIN_PASSWORD] is None:
            password = self.dialog.queryString(
                name='ENGINE_ADMIN_PASSWORD',
                note=_(
                    "Enter engine admin password: "
                ),
                prompt=True,
                hidden=True,
            )
            if password:
                password_check = self.dialog.queryString(
                    name='ENGINE_ADMIN_PASSWORD',
                    note=_(
                        "Confirm engine admin password: "
                    ),
                    prompt=True,
                    hidden=True,
                )
                if password == password_check:
                    self.environment[
                        ohostedcons.EngineEnv.ADMIN_PASSWORD
                    ] = password
                else:
                    self.logger.error(_('Passwords do not match'))
            else:
                if self.environment[
                    ohostedcons.EngineEnv.INTERACTIVE_ADMIN_PASSWORD
                ]:
                    self.logger.error(_('Please specify a password'))
                else:
                    raise RuntimeError(
                        _('Empty password not allowed for user admin')
                    )

# vim: expandtab tabstop=4 shiftwidth=4
