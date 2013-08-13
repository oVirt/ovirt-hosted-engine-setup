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


"""
super user password plugin.
"""


import gettext


import paramiko


from otopi import util
from otopi import plugin
from otopi import constants as otopicons


from ovirt_hosted_engine_setup import constants as ohostedcons


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    super user password plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    def _validateUserPasswd(self, host, user, password):
        valid = False
        try:
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(
                hostname=host,
                username=user,
                password=password
            )
            valid = True
        except paramiko.AuthenticationException:
            pass
        finally:
            cli.close()
        return valid

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.HostEnv.ROOT_PASSWORD,
            None
        )

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
        interactive = (
            self.environment[ohostedcons.HostEnv.ROOT_PASSWORD] is None
        )
        while self.environment[ohostedcons.HostEnv.ROOT_PASSWORD] is None:
            password = self.dialog.queryString(
                name='HOST_ROOT_PASSWORD',
                note=_("Enter 'root' user password: "),
                prompt=True,
                hidden=True,
            )
            if self._validateUserPasswd(
                host='localhost',
                user='root',
                password=password
            ):
                self.environment[ohostedcons.HostEnv.ROOT_PASSWORD] = password
            else:
                if interactive:
                    self.logger.error(_('Wrong root password, try again'))
                else:
                    raise RuntimeError(_('Wrong root password'))

        self.environment[otopicons.CoreEnv.LOG_FILTER].append(
            self.environment[ohostedcons.HostEnv.ROOT_PASSWORD]
        )


# vim: expandtab tabstop=4 shiftwidth=4
