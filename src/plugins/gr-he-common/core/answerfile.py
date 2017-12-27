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


"""Answer file plugin."""


import datetime
import gettext
import os


from io import StringIO

from otopi import constants as otopicons
from otopi import common
from otopi import plugin
from otopi import util

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import util as ohostedutil


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """Answer file plugin."""

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    def _generate_answers(self, f):
        f.write(u'[environment:default]\n')
        for c in ohostedcons.__dict__['__hosted_attrs__']:
            for k in c.__dict__.values():
                if hasattr(k, '__hosted_attrs__'):
                    if k.__hosted_attrs__['answerfile']:
                        k = k.fget(None)
                        if k in self.environment:
                            v = self.environment[k]
                            f.write(
                                u'%s=%s:%s\n' % (
                                    k,
                                    common.typeName(v),
                                    '\n'.join(v) if isinstance(v, list)
                                    else v,
                                )
                            )

    def _save_answers(self, name):
        self.logger.info(
            _("Generating answer file '{name}'").format(
                name=name,
            )
        )
        path = self.resolveFile(name)
        with open(path, 'w') as f:
            self._generate_answers(f)
        if self.environment[ohostedcons.CoreEnv.NODE_SETUP]:
            try:
                ohostedutil.persist(path)
            except Exception as e:
                self.logger.debug(
                    'Error persisting {path}'.format(
                        path=path,
                    ),
                    exc_info=True,
                )
                self.logger.error(e)

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.CoreEnv.ETC_ANSWER_FILE,
            ohostedcons.FileLocations.OVIRT_HOSTED_ENGINE_ANSWERS
        )
        self.environment.setdefault(
            ohostedcons.CoreEnv.USER_ANSWER_FILE,
            None
        )
        self._answers = []

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        name=ohostedcons.Stages.ANSWER_FILE_AVAILABLE,
    )
    def _closeup(self):
        # TODO: ensure to generate after latest env value modification
        # otherwise that value will not be in the file copied to the engine VM
        f = StringIO()
        try:
            self._generate_answers(f)
            self.environment[
                ohostedcons.StorageEnv.ANSWERFILE_CONTENT
            ] = f.getvalue()
        finally:
            f.close()

    @plugin.event(
        stage=plugin.Stages.STAGE_CLEANUP,
        priority=plugin.Stages.PRIORITY_LAST,
    )
    def _save_answers_at_cleanup(self):
        self._answers.extend(
            (
                os.path.join(
                    (
                        ohostedcons.FileLocations.
                        OVIRT_HOSTED_ENGINE_ANSWERS_ARCHIVE_DIR
                    ),
                    'answers-%s.conf' % (
                        datetime.datetime.now().strftime('%Y%m%d%H%M%S'),
                    )
                ),
                self.environment[
                    ohostedcons.CoreEnv.USER_ANSWER_FILE
                ],
            )
        )
        if not self.environment[otopicons.BaseEnv.ERROR]:
            self._answers.append(
                self.environment[
                    ohostedcons.CoreEnv.ETC_ANSWER_FILE
                ]
            )
        for name in self._answers:
            if name:
                self._save_answers(name)


# vim: expandtab tabstop=4 shiftwidth=4
