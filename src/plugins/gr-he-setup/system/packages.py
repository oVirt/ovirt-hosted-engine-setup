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

"""Install required packages."""


import gettext


from distutils.version import LooseVersion

from otopi import plugin
from otopi import util

from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """Packages installer plugin."""

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    def _gluster_unavailable(self):
        self.logger.info(
            _(
                'Please abort the setup and install vdsm-gluster, '
                'glusterfs-server >= {minversion} and restart vdsmd service '
                'in order to gain Hyper Converged setup support.'
            ).format(
                minversion=self.environment[
                    ohostedcons.VDSMEnv.GLUSTER_MINIMUM_VERSION
                ]
            )
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.VDSMEnv.GLUSTER_MINIMUM_VERSION,
            ohostedcons.Const.GLUSTER_MINIMUM_VERSION
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_LATE_SETUP,
        after=(
            ohostedcons.Stages.VDSM_LIBVIRT_CONFIGURED,
        ),
    )
    def _late_setup(self):
        cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        caps = cli.getVdsCapabilities()
        self.logger.debug(caps)
        if caps['status']['code'] != 0:
            raise RuntimeError(caps['status']['message'])
        if (
            'GLUSTER_BRICK_MANAGEMENT'
            not in caps['additionalFeatures'] or
            'glusterfs-server' not in caps['packages2']
        ):
            self.logger.warning(
                _(
                    'Cannot locate gluster packages, '
                    'Hyper Converged setup support will be disabled.'
                )
            )
            self._gluster_unavailable()
            return
        self.logger.debug('vdsm-gluster support detected')
        minversion = self.environment[
            ohostedcons.VDSMEnv.GLUSTER_MINIMUM_VERSION
        ]
        currentversion = '%s-%s' % (
            caps['packages2']['glusterfs-server']['version'],
            caps['packages2']['glusterfs-server']['release'],
        )
        if minversion is not None:
            # this version object does not handle the '-' as rpm...
            if (
                [LooseVersion(v) for v in minversion.split('-')] >
                [LooseVersion(v) for v in currentversion.split('-')]
            ):
                self.logger.warning(
                    _(
                        'glusterfs-server package is too old, '
                        'need {minimum} found {version}'
                    ).format(
                        minimum=minversion,
                        version=currentversion,
                    )
                )
                self._gluster_unavailable()


# vim: expandtab tabstop=4 shiftwidth=4
