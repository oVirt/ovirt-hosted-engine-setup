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


"""VDSM misc plugin."""

import pwd
import grp
import gettext


from otopi import util
from otopi import plugin


from vdsm import vdscli


from ovirt_hosted_engine_setup import constants as ohostedcons


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


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
        stage=plugin.Stages.STAGE_MISC,
        name=ohostedcons.Stages.VDSMD_START,
        after=[
            ohostedcons.Stages.LIBVIRT_CONFIGURED,
            ohostedcons.Stages.VDSMD_PKI,
            ohostedcons.Stages.VDSMD_CONFIGURED,
        ],
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
        self.services.state(
            name=self.environment[
                ohostedcons.VDSMEnv.VDSMD_SERVICE
            ],
            state=True,
        )
        vdsClient = util.loadModule(
            path=ohostedcons.FileLocations.VDS_CLIENT_DIR,
            name='vdsClient'
        )
        serv = None
        if vdsClient._glusterEnabled:
            serv = vdsClient.ge.GlusterService()
        else:
            serv = vdsClient.service()
        serv.useSSL = True
        server, serverPort = vdscli.cannonizeAddrPort(
            'localhost'
        ).split(':', 1)
        serv.do_connect(server, serverPort)
        self.environment[ohostedcons.VDSMEnv.VDS_CLI] = serv


# vim: expandtab tabstop=4 shiftwidth=4
