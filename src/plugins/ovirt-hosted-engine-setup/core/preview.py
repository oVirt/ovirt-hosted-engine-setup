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


"""Preview plugin."""


import gettext


from otopi import util
from otopi import plugin


from ovirt_hosted_engine_setup import constants as ohostedcons


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """Preview plugin."""

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.CoreEnv.CONFIRM_SETTINGS,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_VALIDATION,
        priority=plugin.Stages.PRIORITY_LOW,
    )
    def _validation(self):
        self.dialog.note(
            text=_('\n--== CONFIGURATION PREVIEW ==--\n\n'),
        )
        for c in ohostedcons.__dict__['__hosted_attrs__']:
            for k in c.__dict__.values():
                if hasattr(k, '__hosted_attrs__'):
                    attrs = k.__hosted_attrs__
                    if attrs['summary']:
                        env = k.fget(None)
                        value = self.environment.get(env)
                        if value is not None:
                            self.dialog.note(
                                text=_('{key:35}: {value}').format(
                                    key=(
                                        attrs['description']
                                        if attrs['description'] is not None
                                        else env
                                    ),
                                    value=value,
                                ),
                            )

        interactive = self.environment[ohostedcons.CoreEnv.CONFIRM_SETTINGS]
        if interactive is None:
            self.environment[
                ohostedcons.CoreEnv.CONFIRM_SETTINGS
            ] = self.dialog.queryString(
                name=ohostedcons.Confirms.SETTINGS,
                note=_(
                    '\n'
                    'Please confirm installation settings '
                    '(@VALUES@)[@DEFAULT@]: '
                ),
                prompt=True,
                validValues=(_('Yes'), _('No')),
                caseSensitive=False,
                default=_('Yes'),
            ) == _('Yes').lower()

        if not self.environment[ohostedcons.CoreEnv.CONFIRM_SETTINGS]:
            raise RuntimeError(_('Configuration was rejected by user'))


# vim: expandtab tabstop=4 shiftwidth=4
