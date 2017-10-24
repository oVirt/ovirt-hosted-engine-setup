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


"""
Customization sections title plugin.
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
    Customization sections title plugin.
    """

    def _title(self, text):
        self.dialog.note(
            text='\n--== %s ==--\n\n' % text,
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.DIALOG_TITLES_S_STORAGE,
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_STORAGE,
        )
    )
    def _storage_start(self):
        self._title(
            text=_('STORAGE CONFIGURATION'),
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.DIALOG_TITLES_E_STORAGE,
        before=(
            ohostedcons.Stages.DIALOG_TITLES_S_NETWORK,
        ),
    )
    def _storage_end(self):
        pass

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.DIALOG_TITLES_S_NETWORK,
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_NETWORK,
        ),
    )
    def _network_start(self):
        self._title(
            text=_('HOST NETWORK CONFIGURATION'),
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.DIALOG_TITLES_E_NETWORK,
        before=(
            ohostedcons.Stages.DIALOG_TITLES_S_VM,
        ),
    )
    def _network_end(self):
        pass

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.DIALOG_TITLES_S_VM,
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_VM,
        ),
    )
    def _vm_start(self):
        self._title(
            text=_('VM CONFIGURATION'),
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.DIALOG_TITLES_E_VM,
        before=(
            ohostedcons.Stages.DIALOG_TITLES_S_ENGINE,
        ),
    )
    def _vm_end(self):
        pass

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.DIALOG_TITLES_S_ENGINE,
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_ENGINE,
        ),
    )
    def _engine_start(self):
        self._title(
            text=_('HOSTED ENGINE CONFIGURATION'),
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.DIALOG_TITLES_E_ENGINE,
    )
    def _engine_end(self):
        pass
