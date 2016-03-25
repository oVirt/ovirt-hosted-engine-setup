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


"""VDSM misc plugin."""

import gettext
import grp
import pwd

from otopi import plugin
from otopi import util

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_ha.lib import util as ohautil


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """VDSM misc plugin."""

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT
    )
    def _init(self):
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

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        self.command.detect('vdsm-tool')

    @plugin.event(
        stage=plugin.Stages.STAGE_LATE_SETUP,
        name=ohostedcons.Stages.VDSM_LIBVIRT_CONFIGURED,
        after=(
            ohostedcons.Stages.VDSMD_CONF_LOADED,
        ),
    )
    def _late_setup(self):
        # We need vdsmd up for customization checks
        if not self.services.status(
            name=self.environment[
                ohostedcons.VDSMEnv.VDSMD_SERVICE
            ]
        ):
            rc, _stdout, _stderr = self.execute(
                (
                    self.command.get('vdsm-tool'),
                    'configure',
                    '--force',
                ),
                raiseOnError=False,
            )
            if rc != 0:
                raise RuntimeError(
                    _(
                        'Failed to reconfigure libvirt for VDSM'
                    )
                )
            if not self.services.supportsDependency:
                if self.services.exists('cgconfig'):
                    self.services.state('cgconfig', True)
                if self.services.exists('messagebus'):
                    self.services.state('messagebus', True)
                if self.services.exists('libvirtd'):
                    self.services.state('libvirtd', True)
            self.services.state(
                name=self.environment[
                    ohostedcons.VDSMEnv.VDSMD_SERVICE
                ],
                state=True
            )
        self.environment[
            ohostedcons.VDSMEnv.VDS_CLI
        ] = ohautil.connect_vdsm_json_rpc(
            logger=self.logger,
            timeout=ohostedcons.Const.VDSCLI_SSL_TIMEOUT,
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        name=ohostedcons.Stages.VDSMD_START,
        after=(
            ohostedcons.Stages.LIBVIRT_CONFIGURED,
            ohostedcons.Stages.VDSMD_CONFIGURED,
        ),
    )
    def _misc(self):
        self.logger.info(
            _('Starting {service}').format(
                service=self.environment[
                    ohostedcons.VDSMEnv.VDSMD_SERVICE
                ],
            )
        )
        self.services.startup(
            name=self.environment[
                ohostedcons.VDSMEnv.VDSMD_SERVICE
            ],
            state=True,
        )
        # We need to reconfigure and restart for reloading the configuration
        self.services.state(
            name=self.environment[
                ohostedcons.VDSMEnv.VDSMD_SERVICE
            ],
            state=False,
        )
        rc, _stdout, _stderr = self.execute(
            (
                self.command.get('vdsm-tool'),
                'configure',
                '--force',
            ),
            raiseOnError=False,
        )
        if rc != 0:
            raise RuntimeError(
                _(
                    'Failed to reconfigure libvirt for VDSM'
                )
            )
        if not self.services.supportsDependency:
            if self.services.exists('cgconfig'):
                self.services.state('cgconfig', True)
            if self.services.exists('messagebus'):
                self.services.state('messagebus', True)
            if self.services.exists('libvirtd'):
                self.services.state('libvirtd', True)
        self.services.state(
            name=self.environment[
                ohostedcons.VDSMEnv.VDSMD_SERVICE
            ],
            state=True,
        )
        self.environment[
            ohostedcons.VDSMEnv.VDS_CLI
        ] = ohautil.connect_vdsm_json_rpc(
            logger=self.logger,
            timeout=ohostedcons.Const.VDSCLI_SSL_TIMEOUT,
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        after=(
            ohostedcons.Stages.HOST_ADDED,
        ),
        name=ohostedcons.Stages.VDSCLI_RECONNECTED,
    )
    def _closeup(self):
        # We need to reconnect cause host-deploy
        # restarted vdsm adding the host
        self.environment[
            ohostedcons.VDSMEnv.VDS_CLI
        ] = ohautil.connect_vdsm_json_rpc(
            logger=self.logger,
            timeout=ohostedcons.Const.VDSCLI_SSL_TIMEOUT,
        )

# vim: expandtab tabstop=4 shiftwidth=4
