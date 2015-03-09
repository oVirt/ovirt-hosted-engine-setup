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
VDSM configuration plugin.
"""


import configparser
import gettext
import os
import StringIO  # FIXME: May need some otopi magic for python3 compatibility


from otopi import constants as otopicons
from otopi import filetransaction
from otopi import plugin
from otopi import transaction
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
        self.environment.setdefault(
            ohostedcons.VDSMEnv.USE_SSL,
            True
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_LATE_SETUP,
        name=ohostedcons.Stages.VDSMD_CONF_LOADED,
    )
    def _late_setup(self):
        if self.config.read(ohostedcons.FileLocations.VDSM_CONF):
            if (
                self.config.has_section('vars') and
                self.config.has_option('vars', 'ssl')
            ):
                self.environment[
                    ohostedcons.VDSMEnv.USE_SSL
                ] = self.config.getboolean('vars', 'ssl')

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        name=ohostedcons.Stages.VDSMD_CONFIGURED,
    )
    def _misc(self):
        self.logger.info(_('Configuring VDSM'))
        if not os.path.exists(ohostedcons.FileLocations.VDSM_CONF):
            self.logger.warning(
                _(
                    'VDSM configuration file not found: '
                    'creating a new configuration file'
                )
            )
        for section in ('irs', 'vars'):
            if not self.config.has_section(section):
                self.config.add_section(section)
        self.config.set(
            'vars',
            'default_bridge',
            self.environment[ohostedcons.NetworkEnv.BRIDGE_NAME]
        )
        f = StringIO.StringIO()
        try:
            self.config.write(f)
            with transaction.Transaction() as localtransaction:
                localtransaction.append(
                    filetransaction.FileTransaction(
                        name=ohostedcons.FileLocations.VDSM_CONF,
                        content=f.getvalue(),
                        modifiedList=self.environment[
                            otopicons.CoreEnv.MODIFIED_FILES
                        ],
                    ),
                )
        finally:
            f.close()


# vim: expandtab tabstop=4 shiftwidth=4
