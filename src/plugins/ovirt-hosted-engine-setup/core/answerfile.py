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


"""Answer file plugin."""


import gettext


from otopi import util
from otopi import common
from otopi import plugin


from ovirt_hosted_engine_setup import constants as ohostedcons


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """Answer file plugin."""

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    def _save_answers(self):
        self.logger.info(
            _("Generating answer file '{name}'").format(
                name=self.environment[ohostedcons.CoreEnv.ANSWER_FILE],
            )
        )
        with open(
            self.resolveFile(
                self.environment[ohostedcons.CoreEnv.ANSWER_FILE]
            ),
            'w'
        ) as f:
            f.write('[environment:default]\n')
            for c in ohostedcons.__dict__['__hosted_attrs__']:
                for k in c.__dict__.values():
                    if hasattr(k, '__hosted_attrs__'):
                        if k.__hosted_attrs__['answerfile']:
                            k = k.fget(None)
                            if k in self.environment:
                                v = self.environment[k]
                                f.write(
                                    '%s=%s:%s\n' % (
                                        k,
                                        common.typeName(v),
                                        '\n'.join(v) if isinstance(v, list)
                                        else v,
                                    )
                                )

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.CoreEnv.ANSWER_FILE,
            ohostedcons.FileLocations.OVIRT_HOSTED_ENGINE_ANSWERS
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_VALIDATION,
        priority=plugin.Stages.PRIORITY_LAST,
        condition=lambda self: self.environment[
            ohostedcons.CoreEnv.ANSWER_FILE
        ] is not None
    )
    def _save_answers_at_validation(self):
        self._save_answers()

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        priority=plugin.Stages.PRIORITY_LAST,
        condition=lambda self: self.environment[
            ohostedcons.CoreEnv.ANSWER_FILE
        ] is not None
    )
    def _save_answers_at_closeup(self):
        self._save_answers()
        self.logger.info(
            _("Answer file '{name}' has been updated").format(
                name=self.environment[ohostedcons.CoreEnv.ANSWER_FILE],
            )
        )


# vim: expandtab tabstop=4 shiftwidth=4
