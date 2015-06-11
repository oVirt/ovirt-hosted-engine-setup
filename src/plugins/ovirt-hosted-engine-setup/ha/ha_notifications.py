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
HA notifications configuration
"""


import configparser
import gettext
import re
import StringIO


from otopi import plugin
from otopi import util


from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    HA notifications plugin.
    """

    _RE_HOSTNAME = re.compile(
        flags=re.VERBOSE,
        pattern=r"""
            ^
            [a-z0-9.-]+
            $
        """
    )

    _RE_PORT = re.compile(
        flags=re.VERBOSE,
        pattern=r"""
            ^
            [0-9]+
            $
        """
    )

    _RE_EMAIL_ADDRESS = re.compile(
        flags=re.VERBOSE,
        pattern=r"""
            [a-zA-Z0-9_.+\-=]+
            @
            [a-z0-9.-]+
        """
    )

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.NotificationsEnv.SMTP_SERVER,
            None
        )
        self.environment.setdefault(
            ohostedcons.NotificationsEnv.SMTP_PORT,
            None
        )
        self.environment.setdefault(
            ohostedcons.NotificationsEnv.SOURCE_EMAIL,
            None
        )
        self.environment.setdefault(
            ohostedcons.NotificationsEnv.DEST_EMAIL,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        condition=lambda self: not self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
    )
    def _customization(self):
        default_smtp_config = {
            # TODO - remove the ugly parens below when pep8 stops failing
            # https://github.com/jcrocholl/pep8/issues/144
            ohostedcons.Const.HA_NOTIF_SMTP_SERVER: (
                ohostedcons.NotificationsEnv.DEFAULT_SMTP_SERVER),
            ohostedcons.Const.HA_NOTIF_SMTP_PORT: (
                ohostedcons.NotificationsEnv.DEFAULT_SMTP_PORT),
            ohostedcons.Const.HA_NOTIF_SMTP_SOURCE_EMAIL: (
                ohostedcons.NotificationsEnv.DEFAULT_SOURCE_EMAIL),
            ohostedcons.Const.HA_NOTIF_SMTP_DEST_EMAILS: (
                ohostedcons.NotificationsEnv.DEFAULT_DEST_EMAIL),
        }
        self._cfg = configparser.SafeConfigParser()
        self._cfg.add_section('email')

        interactions = (
            {
                'name': ohostedcons.Const.HA_NOTIF_SMTP_SERVER,
                'envkey': ohostedcons.NotificationsEnv.SMTP_SERVER,
                'note': _(
                    'Please provide the name of the SMTP server through which '
                    'we will send notifications [@DEFAULT@]: '
                ),
                'validation': lambda value: self._RE_HOSTNAME.match(value),
            },
            {
                'name': ohostedcons.Const.HA_NOTIF_SMTP_PORT,
                'envkey': ohostedcons.NotificationsEnv.SMTP_PORT,
                'note': _(
                    'Please provide the TCP port number of the SMTP server '
                    '[@DEFAULT@]: '
                ),
                'validation': lambda value: self._RE_PORT.match(value),
            },
            {
                'name': ohostedcons.Const.HA_NOTIF_SMTP_SOURCE_EMAIL,
                'envkey': ohostedcons.NotificationsEnv.SOURCE_EMAIL,
                'note': _(
                    'Please provide the email address from which '
                    'notifications will be sent [@DEFAULT@]: '
                ),
                'validation': lambda value: self._RE_EMAIL_ADDRESS.match(
                    value
                ),
            },
            {
                'name': ohostedcons.Const.HA_NOTIF_SMTP_DEST_EMAILS,
                'envkey': ohostedcons.NotificationsEnv.DEST_EMAIL,
                'note': _(
                    'Please provide a comma-separated list of email addresses '
                    'which will get notifications [@DEFAULT@]: '
                ),
                'validation': lambda value: (
                    None not in [
                        self._RE_EMAIL_ADDRESS.match(addr)
                        for addr in value.split(',')
                    ]
                ),
            },
        )

        for item in interactions:
            interactive = self.environment[item['envkey']] is None
            valid = False
            while not valid:
                if interactive:
                    self.environment[item['envkey']] = self.dialog.queryString(
                        name='DIALOG' + item['envkey'],
                        note=item['note'],
                        prompt=True,
                        caseSensitive=True,
                        default=default_smtp_config[item['name']]
                    )
                if item['validation'](self.environment[item['envkey']]):
                    valid = True
                else:
                    self.logger.debug(
                        'input %s for %s failed validation' % (
                            self.environment[item['envkey']],
                            item['envkey'],
                        )
                    )
                    if interactive:
                        self.logger.error(
                            _('Invalid input, please try again')
                        )
                    else:
                        raise RuntimeError(
                            _(
                                'Invalid input for environment value {key}'
                            ).format(
                                key=item['envkey'],
                            ),
                        )
            self._cfg.set(
                'email',
                item['name'],
                self.environment[item['envkey']]
            )

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        condition=lambda self: not self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
        name=ohostedcons.Stages.BROKER_CONF_AVAILABLE,
    )
    def _misc(self):
        f = StringIO.StringIO()
        try:
            self._cfg.write(f)
            self.environment[
                ohostedcons.StorageEnv.BROKER_CONF_CONTENT
            ] = f.getvalue()
        finally:
            f.close()


# vim: expandtab tabstop=4 shiftwidth=4
