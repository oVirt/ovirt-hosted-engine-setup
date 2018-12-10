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
VDSM configuration plugin.
"""


import configparser
import gettext
import grp
import pwd

from otopi import plugin
from otopi import util

from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    VDSM configuration plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self.config = configparser.ConfigParser()
        self.config.optionxform = str

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT
    )
    def _init(self):
        # TODO: check what's still in use and remove everything else from here
        self.environment.setdefault(
            ohostedcons.VDSMEnv.USE_SSL,
            True
        )
        self.environment.setdefault(
            ohostedcons.VDSMEnv.VDSMD_SERVICE,
            ohostedcons.Defaults.DEFAULT_VDSMD_SERVICE
        )
        self.environment.setdefault(
            ohostedcons.VDSMEnv.VDSM_UID,
            pwd.getpwnam('vdsm').pw_uid
        )
        self.environment.setdefault(
            ohostedcons.VDSMEnv.KVM_GID,
            grp.getgrnam('kvm').gr_gid
        )
        self.environment.setdefault(
            ohostedcons.VDSMEnv.VDS_CLI,
            None
        )


# vim: expandtab tabstop=4 shiftwidth=4
