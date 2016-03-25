#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2014-2015 Red Hat, Inc.
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
GlusterFS storage provisioning plugin.
"""

import gettext
import socket

from otopi import constants as otopicons
from otopi import filetransaction
from otopi import plugin
from otopi import transaction
from otopi import util

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import domains as ohosteddomains
from ovirt_hosted_engine_ha.lib import util as ohautil


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    GlusterFS storage provisioning plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._checker = ohosteddomains.DomainChecker()

    def _configure_glusterfs_service(self):
        """
        @see: http://www.ovirt.org/Features/
        Self_Hosted_Engine_Hyper_Converged_Gluster_Support
        #Config_files_changes
        """
        content = []
        with open(ohostedcons.FileLocations.GLUSTERD_VOL, 'r') as f:
            for line in f.read().splitlines():
                if line.find('rpc-auth-allow-insecure') != -1:
                    continue
                elif line.find('base-port') != -1:
                    continue
                elif line.find('end-volume') == 0:
                    content.append('    option rpc-auth-allow-insecure on')
                    content.append('    option base-port 49217')
                content.append(line)

        with transaction.Transaction() as localtransaction:
            localtransaction.append(
                filetransaction.FileTransaction(
                    name=ohostedcons.FileLocations.GLUSTERD_VOL,
                    content=content,
                    modifiedList=self.environment[
                        otopicons.CoreEnv.MODIFIED_FILES
                    ],
                ),
            )

    def _provision_gluster_volume(self):
        """
        Set parameters as suggested by Gluster Storage Domain Reference
        @see: http://www.ovirt.org/Gluster_Storage_Domain_Reference
        """
        cli = ohautil.connect_vdsm_json_rpc(
            logger=self.logger,
            timeout=ohostedcons.Const.VDSCLI_SSL_TIMEOUT,
        )
        share = self.environment[ohostedcons.StorageEnv.GLUSTER_SHARE_NAME]
        brick = self.environment[ohostedcons.StorageEnv.GLUSTER_BRICK]
        self.logger.debug('glusterVolumesList')
        response = cli.glusterVolumesList()
        self.logger.debug(response)
        if response['status']['code'] != 0:
            self.logger.error(_('Failed to retrieve the Gluster Volume list'))
            raise RuntimeError(response['status']['message'])
        volumes = response['volumes']
        if share in volumes:
            self.logger.info(_('GlusterFS Volume already exists'))
            if set([brick]) != set(volumes[share]['bricks']):
                self.logger.debug(set([brick]))
                self.logger.debug(set(volumes[share]['bricks']))
                raise RuntimeError(
                    _(
                        'GlusterFS Volume has been found with different '
                        'bricks list'
                    )
                )
        else:
            self.logger.info(_('Creating GlusterFS Volume'))
            replica_count = ''
            stripe_count = ''
            transport_list = ['tcp']
            force = True
            self.logger.debug('glusterVolumeCreate')
            response = cli.glusterVolumeCreate(
                share,
                [brick],
                replica_count,
                stripe_count,
                transport_list,
                force
            )
            self.logger.debug(response)
            if response['status']['code'] != 0:
                self.logger.error(_('Failed to create the Gluster Volume'))
                raise RuntimeError(response['status']['message'])

        for option, value in {
            'cluster.quorum-type': 'auto',
            'network.ping-timeout': '10',
            'nfs.disable': 'on',
            'user.cifs': 'disable',
            'auth.allow': '*',
            'group': 'virt',
            'storage.owner-uid': '36',
            'storage.owner-gid': '36',
            'server.allow-insecure': 'on',
        }.items():
            self.logger.debug('glusterVolumeSet %s' % option)
            response = cli.glusterVolumeSet(
                share,
                option,
                value
            )
            if response['status']['code'] != 0:
                self.logger.error(
                    _('Failed to set {option} on the Gluster Volume').format(
                        option=option,
                    )
                )
                raise RuntimeError(response['status']['message'])

        self.logger.debug('glusterVolumesList')
        response = cli.glusterVolumesList()
        self.logger.debug(response)
        if response['status']['code'] != 0:
            self.logger.error(_('Failed to retrieve the Gluster Volume list'))
            raise RuntimeError(response['status']['message'])
        volume = response['volumes'][share]
        self.logger.debug('glusterTasksList')
        response = cli.glusterTasksList()
        self.logger.debug(response)
        if response['status']['code'] != 0:
            self.logger.error(_('Failed to retrieve the Gluster Tasks List'))
            raise RuntimeError(response['status']['message'])
        # TODO: check if we need to do something about these tasks

        if volume['volumeStatus'] == 'ONLINE':
            self.logger.debug('GlusterFS Volume already started')
        elif volume['volumeStatus'] == 'OFFLINE':
            self.logger.debug('glusterVolumeStart')
            response = cli.glusterVolumeStart(share)
            if response['status']['code'] != 0:
                self.logger.error(_('Failed to start the Gluster Volume'))
                raise RuntimeError(response['status']['message'])
        else:
            raise RuntimeError(
                _(
                    'GlusterFS Volume found in an unknown state: {state}'
                ).format(
                    state=volume['volumeStatus'],
                )
            )

        self.logger.debug('glusterVolumesList')
        response = cli.glusterVolumesList()
        self.logger.debug(response)
        if response['status']['code'] != 0:
            self.logger.error(_('Failed to retrieve the Gluster Volume list'))
            raise RuntimeError(response['status']['message'])

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.StorageEnv.GLUSTER_PROVISIONING_ENABLED,
            False
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.GLUSTER_SHARE_NAME,
            ohostedcons.Defaults.DEFAULT_GLUSTER_SHARE_NAME
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.GLUSTER_BRICK,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.GLUSTER_PROVISIONING,
        after=(
            ohostedcons.Stages.CONFIG_STORAGE_EARLY,
        ),
        before=(
            ohostedcons.Stages.CONFIG_STORAGE_NFS,
        ),
    )
    def _customization(self):
        if self.environment[
            ohostedcons.StorageEnv.DOMAIN_TYPE
        ] != ohostedcons.DomainTypes.GLUSTERFS:
            self.environment[
                ohostedcons.StorageEnv.GLUSTER_PROVISIONING_ENABLED
            ] = False
        interactive = self.environment[
            ohostedcons.StorageEnv.GLUSTER_PROVISIONING_ENABLED
        ] is None
        if interactive:
            self.environment[
                ohostedcons.StorageEnv.GLUSTER_PROVISIONING_ENABLED
            ] = self.dialog.queryString(
                name='OVEHOSTED_GLUSTER_PROVISIONING',
                note=_(
                    'Do you want to configure this host for '
                    'providing GlusterFS storage (will start with no replica '
                    'requires to grow to replica 3 later)? '
                    '(@VALUES@)[@DEFAULT@]: '
                ),
                prompt=True,
                validValues=(_('Yes'), _('No')),
                caseSensitive=False,
                default=_('No')
            ) == _('Yes').lower()

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.GLUSTER_PROVISIONING,
        ),
        before=(
            ohostedcons.Stages.CONFIG_STORAGE_NFS,
        ),
        condition=lambda self: self.environment[
            ohostedcons.StorageEnv.GLUSTER_PROVISIONING_ENABLED
        ],
    )
    def _brick_customization(self):
        interactive = self.environment[
            ohostedcons.StorageEnv.GLUSTER_BRICK
        ] is None
        if interactive:
            path = self.dialog.queryString(
                name='OVEHOSTED_GLUSTER_BRICKS',
                note=_(
                    'Please provide a path to be used for the brick '
                    'on this host:'
                ),
                prompt=True,
                caseSensitive=True,
            )
            self.environment[
                ohostedcons.StorageEnv.GLUSTER_BRICK
            ] = '%s:%s' % (socket.gethostname(), path)
        else:
            host = self.environment[
                ohostedcons.StorageEnv.GLUSTER_BRICK
            ].split(':')[0]
            if host != socket.gethostname():
                raise ValueError(
                    _('The specified brick must be on this host')
                )
        self.environment[
            ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
        ] = '{host}:/{share}'.format(
            host=socket.gethostname(),
            share=self.environment[ohostedcons.StorageEnv.GLUSTER_SHARE_NAME],
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_VALIDATION,
    )
    def _validate(self):
        if self.environment[
            ohostedcons.StorageEnv.GLUSTER_PROVISIONING_ENABLED
        ]:
            raise RuntimeError(
                _('HyperConverged deployment is currently unsupported ')
            )

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        condition=lambda self: self.environment[
            ohostedcons.StorageEnv.GLUSTER_PROVISIONING_ENABLED
        ],
        after=(
            ohostedcons.Stages.VDSMD_START,
        ),
        before=(
            ohostedcons.Stages.STORAGE_AVAILABLE,
        )
    )
    def _misc(self):
        """
        If GlusterFS provisioning was requested:
        - configure GlusterFS for allowing HyperConvergence
        - starts GlusterFS services
        - create volume
        """
        self._configure_glusterfs_service()
        self.logger.info(_('Starting GlusterFS services'))
        self.services.state(
            name=ohostedcons.Const.GLUSTERD_SERVICE,
            state=True,
        )
        self._provision_gluster_volume()

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        condition=lambda self: self.environment[
            ohostedcons.StorageEnv.GLUSTER_PROVISIONING_ENABLED
        ],
    )
    def _closeup(self):
        """
        Enable GlusterFS services if GlusterFS provisioning was requested
        """
        self.logger.info(_('Enabling GlusterFS services'))
        self.services.startup(
            name=ohostedcons.Const.GLUSTERD_SERVICE,
            state=True,
        )


# vim: expandtab tabstop=4 shiftwidth=4
