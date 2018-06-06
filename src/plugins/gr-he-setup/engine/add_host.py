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
Host adder plugin.
"""

import gettext
import os
import selinux
import socket
import tempfile
import time

from otopi import constants as otopicons
from otopi import filetransaction
from otopi import plugin
from otopi import transaction
from otopi import util

from ovirt_host_deploy import constants as ohdcons

from ovirt_hosted_engine_setup import check_liveliness
from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import engineapi
from ovirt_hosted_engine_setup import pkissh
from ovirt_hosted_engine_setup import vds_info

import ovirtsdk4 as sdk4


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    Host adder plugin.
    """

    VDSM_RETRIES = 600
    VDSM_DELAY = 1

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._interactive_admin_pwd = True
        self._host_deploy_conf = None

    def _wait_host_ready(self, engine_api, hostname):
        self.logger.info(_(
            'Waiting for the host to become operational in the engine. '
            'This may take several minutes...'
        ))

        tries = self.VDSM_RETRIES
        isUp = False
        while not isUp and tries > 0:
            tries -= 1
            try:
                state = ''
                system_service = engine_api.system_service()
                hlist = system_service.hosts_service().list()
                h_id_list = [h.id for h in hlist if h.name == hostname]
                if h_id_list:
                    h = system_service.hosts_service().host_service(
                        h_id_list[0]
                    ).get()
                    state = h.status.value
            except sdk4.Error as exc:
                self.logger.debug(
                    'Error fetching host state: {error}'.format(
                        error=str(exc),
                    )
                )
                state = ''
            self.logger.debug(
                'VDSM host in {state} state'.format(
                    state=state,
                )
            )
            if 'failed' in state:
                self.logger.error(_(
                    'The VDSM host was found in a failed state. '
                    'Please check engine and bootstrap installation logs.'
                ))
                tries = -1  # Error state
            elif state == 'up':
                isUp = True
                self.logger.info(_('The VDSM Host is now operational'))
            else:
                if state == 'non_operational':
                    if not self._retry_non_operational(
                        engine_api,
                        self.environment[ohostedcons.EngineEnv.APP_HOST_NAME],
                    ):
                        # It's up, but non-operational and missing some
                        # required networks. _retry_non_operational
                        # already gave enough info, rest of code can assume
                        # it's up.
                        isUp = True
                if tries % 30 == 0:
                    self.logger.info(_(
                        'Still waiting for VDSM host to become operational...'
                    ))
                time.sleep(self.VDSM_DELAY)
        if not isUp and tries == 0:
            self.logger.error(_(
                'Timed out while waiting for host to start. '
                'Please check the logs.'
            ))
        return isUp

    def _retry_non_operational(self, engine_api, host):
        """Return True if we should continue trying to add the host"""
        ret = True
        try:
            system_service = engine_api.system_service()
            cluster_broker = system_service.clusters_service().cluster_service(
                self.environment[
                    ohostedcons.EngineEnv.HOST_CLUSTER_NAME
                ]
            )
            h = system_service.hosts_service().host_service(host)
            required_networks = set(
                [
                    rn.id
                    for rn in cluster_broker.networks_service().list()
                    if rn.required
                ]
            )
            configured_networks = set(
                [
                    nic.network.id
                    for nic in h.nics_service().list()
                    if nic.network
                ]
            )
            if (
                len(required_networks) > 1 and
                required_networks > configured_networks
            ):
                tbc = required_networks - configured_networks
                networks_service = system_service.networks_service()
                rnet = [
                    networks_service.network_service(rn).get().name
                    for rn in tbc
                ]
                self.dialog.note(
                    _(
                        '\nThe following required networks\n'
                        '  {rnet}\n'
                        'still need to be configured on {host} '
                        'in order to make it\n'
                        'operational. Please setup them via the engine '
                        'webadmin UI or flag them as not required.\n'
                        'When finished, activate the host in the webadmin. '
                    ).format(
                        rnet=rnet,
                        host=host,
                    )
                )
                ret = (
                    False if not self.environment[
                        ohostedcons.NetworkEnv.PROMPT_REQUIRED_NETWORKS
                    ] else
                    self.dialog.queryString(
                        name='OVEHOSTED_REQUIRED_NETWORKS',
                        note=_(
                            'Retry checking host status or ignore this '
                            'and continue '
                            "(@VALUES@)[@DEFAULT@]? "
                        ),
                        prompt=True,
                        validValues=(_('Retry'), _('Ignore')),
                        caseSensitive=False,
                        default=_('Retry'),
                    ) == _('Retry').lower()
                )
                if not ret:
                    self.logger.warning(
                        _('Not waiting for required networks to be set up')
                    )
                    self.dialog.note(
                        _(
                            'To finish deploying, please:\n'
                            '- set up required networks for this host\n'
                            '- activate it\n'
                            '- restart the hosted-engine high availability '
                            'services by running on this machine:\n'
                            '  # service ovirt-ha-agent restart\n'
                            '  # service ovirt-ha-broker restart\n'
                        )
                    )
            else:
                # No missing required networks, perhaps some other issue?
                self.dialog.note(
                    _(
                        'The host {host} is in non-operational state.\n'
                        'Please try to activate it via the engine '
                        'webadmin UI.\n'
                    ).format(
                        host=host,
                    )
                )
                ret = (
                    False if not self.environment[
                        ohostedcons.EngineEnv.PROMPT_NON_OPERATIONAL
                    ] else
                    self.dialog.queryString(
                        name='OVEHOSTED_NON_OPERATIONAL',
                        note=_(
                            'Retry checking host status or ignore this '
                            'and continue '
                            "(@VALUES@)[@DEFAULT@]? "
                        ),
                        prompt=True,
                        validValues=(_('Retry'), _('Ignore')),
                        caseSensitive=False,
                        default=_('Retry'),
                    ) == _('Retry').lower()
                )
                if not ret:
                    self.logger.warning(
                        _('Host left in non-operational state')
                    )
                    self.dialog.note(
                        _(
                            'To finish deploying, please:\n'
                            '- activate it\n'
                            '- restart the hosted-engine high availability '
                            'services by running on this machine:\n'
                            '  # service ovirt-ha-agent restart\n'
                            '  # service ovirt-ha-broker restart\n'
                        )
                    )

        except sdk4.Error as exc:
            self.logger.debug(
                'Error fetching the network configuration: {error}'.format(
                    error=str(exc),
                )
            )
        return ret

    def _wait_cluster_cpu_ready(self, engine_api, cluster_name):
        tries = self.VDSM_RETRIES
        cpu = None
        cluster = None
        while not cpu and tries > 0:
            tries -= 1
            system_service = engine_api.system_service()

            cluster_list = [
                c for c in system_service.clusters_service().list()
                if c.name == cluster_name
            ]
            if cluster_list:
                cluster = cluster_list[0]
                cpu = cluster.cpu

            if cpu is None:
                if tries % 30 == 0:
                    self.logger.info(
                        _(
                            "Waiting for cluster '{name}' "
                            "to become operational..."
                        ).format(
                            name=cluster_name,
                        )
                    )
                time.sleep(self.VDSM_DELAY)
        if cpu is None and tries == 0:
            self.logger.error(_(
                'Timed out while waiting for cluster to become ready. '
                'Please check the logs.'
            ))
        return cluster, cpu

    def _wait_gluster_service_ready(self, engine_api, cluster_name):
        self.logger.info(
            _(
                "Waiting for cluster '{name}' "
                "to be configured for gluster..."
            ).format(
                name=cluster_name,
            )
        )
        tries = self.VDSM_RETRIES
        gluster_service = False
        cluster = None
        while not gluster_service and tries > 0:
            tries -= 1
            system_service = engine_api.system_service()
            cluster_list = system_service.clusters_service().list()
            cluster_flist = [c for c in cluster_list if c.name == cluster_name]
            if cluster_flist:
                cluster = cluster_flist[0]
            if not cluster:
                raise RuntimeError(_('Failed getting cluster info'))
            gluster_service = cluster.gluster_service
            if not gluster_service:
                self.logger.debug(
                    'cluster {cluster} cluster.__dict__ {cdict}'.format(
                        cluster=cluster,
                        cdict=cluster.__dict__,
                    )
                )
                if tries % 30 == 0:
                    self.logger.info(
                        _(
                            "Waiting for cluster '{name}' "
                            "to be configured for gluster service..."
                        ).format(
                            name=cluster.name,
                        )
                    )
                time.sleep(self.VDSM_DELAY)
        if not gluster_service and tries == 0:
            self.logger.error(_(
                'Timed out while waiting for cluster to be configured '
                'for gluster service. '
                'Please check the logs.'
            ))
        return cluster, gluster_service

    def _wait_network_vlan_ready(self, engine_api, network_id, vlan_id):
        tries = self.VDSM_RETRIES
        updated = False
        while not updated and tries > 0:
            tries -= 1
            system_service = engine_api.system_service()
            mgmt_network = system_service.networks_service().network_service(
                network_id
            ).get()

            svlanid = None
            vlan = mgmt_network.vlan
            if vlan is None:
                self.logger.debug(
                    'network {network} network.__dict__ {ndict}'.format(
                        network=mgmt_network,
                        ndict=mgmt_network.__dict__,
                    )
                )
            else:
                svlanid = vlan.id
                self.logger.debug('vlan_id: {id}'.format(id=svlanid))

            if svlanid == vlan_id:
                updated = True
            else:
                time.sleep(self.VDSM_DELAY)

        if not updated:
            self.logger.error(_(
                'Timed out while waiting for configuring management network '
                'vlan ID. Please check the engine logs.'
            ))
            return False
        return True

    def _getSSH(self):
        pkihelper = pkissh.PKIHelper()
        authorized_keys_line = pkihelper.getSSHkey(
            fqdn=self.environment[
                ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
            ],
            ca_certs=self.environment[
                ohostedcons.EngineEnv.TEMPORARY_CERT_FILE
            ],
        )

        authorized_keys_file = os.path.join(
            os.path.expanduser('~root'),
            '.ssh',
            'authorized_keys'
        )

        content = pkihelper.mergeAuthKeysFile(
            authorized_keys_file, authorized_keys_line
        )
        with transaction.Transaction() as localtransaction:
            localtransaction.append(
                filetransaction.FileTransaction(
                    name=authorized_keys_file,
                    content=content,
                    mode=0o600,
                    owner='root',
                    enforcePermissions=True,
                    modifiedList=self.environment[
                        otopicons.CoreEnv.MODIFIED_FILES
                    ],
                )
            )

        if self._selinux_enabled:
            path = os.path.join(
                os.path.expanduser('~root'),
                '.ssh'
            )
            try:
                selinux.restorecon(path, recursive=True)
            except OSError as ex:
                self.logger.error(
                    _(
                        'Failed to refresh SELINUX context for {path}: {ex}'
                    ).format(
                        path=path,
                        ex=ex.message,
                    )
                )

    def _configureHostDeploy(self):
        try:
            fd, self._host_deploy_conf = tempfile.mkstemp(
                prefix='70-hosted-engine-setup-',
                suffix='.conf',
                dir=ohostedcons.FileLocations.OVIRT_HOST_DEPLOY_CONF,
                text=True,
            )
            self.logger.debug(
                'Writing host-deploy configuration to {fname}'.format(
                    fname=self._host_deploy_conf,
                )
            )
            hdfile = os.fdopen(fd, 'w')
            try:
                hdfile.write(
                    '[{section}]\n'.format(
                        section=otopicons.Const.CONFIG_SECTION_INIT,
                    )
                )
                hdfile.write(
                    '{key}={type}:{value}\n'.format(
                        key=ohdcons.CoreEnv.OFFLINE_PACKAGER,
                        type=otopicons.Types.BOOLEAN,
                        value=str(True),
                    )
                )
                if not self.environment[
                    ohostedcons.NetworkEnv.REFUSE_DEPLOYING_WITH_NM
                ]:
                    hdfile.write(
                        '{key}={type}:{value}\n'.format(
                            key=ohdcons.VdsmEnv.DISABLE_NETWORKMANAGER,
                            type=otopicons.Types.BOOLEAN,
                            value=str(False),
                        )
                    )
            finally:
                hdfile.close()
        except EnvironmentError as ex:
            raise RuntimeError(
                _(
                    'Unable to write host-deploy configuration file: {msg}'
                ).format(
                    msg=ex.message,
                )
            )

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.NetworkEnv.PROMPT_REQUIRED_NETWORKS,
            True
        )
        self.environment.setdefault(
            ohostedcons.EngineEnv.PROMPT_NON_OPERATIONAL,
            True
        )
        self._selinux_enabled = False

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        self.command.detect('ip')

    @plugin.event(
        stage=plugin.Stages.STAGE_VALIDATION,
    )
    def _validation(self):
        self._selinux_enabled = selinux.is_selinux_enabled()

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        after=(
            ohostedcons.Stages.CLOSEUP_CA_ACQUIRED,
        ),
        name=ohostedcons.Stages.HOST_ADDED,
    )
    def _closeup(self):
        # TODO: refactor into shorter and simpler functions
        self._getSSH()
        self._configureHostDeploy()
        cluster_name = None
        default_cluster_name = 'Default'
        engine_api = engineapi.get_engine_api(self)
        system_service = engine_api.system_service()
        added_to_cluster = False
        while not added_to_cluster:
            try:
                cluster_name = self.environment[
                    ohostedcons.EngineEnv.HOST_CLUSTER_NAME
                ]
                if not self.environment[ohostedcons.EngineEnv.APP_HOST_NAME]:
                    self.environment[
                        ohostedcons.EngineEnv.APP_HOST_NAME
                    ] = socket.gethostname()
                self.logger.debug(
                    "Getting the list of available clusters via engine's APIs"
                )
                if cluster_name is not None:
                    if cluster_name not in [
                        c.name
                        for c in system_service.clusters_service().list()
                    ]:
                        raise RuntimeError(
                            _(
                                'Specified cluster does not exist: {cluster}'
                            ).format(
                                cluster=cluster_name,
                            )
                        )
                else:
                    cluster_l = [
                        c.name
                        for c in system_service.clusters_service().list()
                    ]
                    cluster_name = (
                        default_cluster_name if default_cluster_name in
                        cluster_l else cluster_l[0]
                    )
                    if len(cluster_l) > 1:
                        cluster_name = self.dialog.queryString(
                            name='cluster_name',
                            note=_(
                                'Enter the name of the cluster to which '
                                'you want to add the host (@VALUES@) '
                                '[@DEFAULT@]: '
                            ),
                            prompt=True,
                            default=cluster_name,
                            validValues=cluster_l,
                        )
                    self.environment[
                        ohostedcons.EngineEnv.HOST_CLUSTER_NAME
                    ] = cluster_name
                cluster_list = system_service.clusters_service().list(
                    follow='networks'
                )
                cluster_flist = [
                    c for c in cluster_list if c.name == cluster_name
                ]
                cluster = None
                if cluster_flist:
                    cluster = cluster_flist[0]
                if not cluster:
                    raise RuntimeError(_('Failed getting cluster info'))

                conn = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
                caps = vds_info.capabilities(conn)
                bridge_port = self.environment[
                    ohostedcons.NetworkEnv.BRIDGE_IF
                ]
                if bridge_port in caps['vlans']:
                    self.logger.debug(
                        "Updating engine's management network to be vlanned"
                    )
                    vlan_id = caps['vlans'][bridge_port]['vlanid']
                    self.logger.debug(
                        "Getting engine's management network via engine's APIs"
                    )
                    cluster_mgmt_network_list = [
                        n for n in cluster.networks
                        if n.name == self.environment[
                            ohostedcons.NetworkEnv.BRIDGE_NAME
                        ]
                    ]
                    cluster_mgmt_network = None
                    if cluster_mgmt_network_list:
                        cluster_mgmt_network = cluster_mgmt_network_list[0]
                    if not cluster_mgmt_network:
                        raise RuntimeError(_(
                            'Failed getting cluster management network {n}'
                        ))

                    mgmt_network_id = cluster_mgmt_network.id
                    mgmt_network_service = system_service.networks_service(
                    ).network_service(
                        cluster_mgmt_network.id
                    )
                    cluster_mgmt_network.vlan.id = vlan_id
                    mgmt_network_service.update(cluster_mgmt_network)

                    self._wait_network_vlan_ready(
                        engine_api,
                        mgmt_network_id,
                        vlan_id
                    )

                if self.environment[
                    ohostedcons.StorageEnv.ENABLE_HC_GLUSTER_SERVICE
                ]:
                    self.logger.debug(
                        "Configuring the cluster for gluster service"
                    )
                    cluster.gluster_service = True
                    cluster_service = system_service.clusters_service(
                    ).cluster_service(cluster.id)
                    cluster_service.update(cluster)

                    c, gluster_ready = self._wait_gluster_service_ready(
                        engine_api,
                        cluster_name
                    )
                    if not gluster_ready:
                        raise RuntimeError(_(
                            'Unable to configure the cluster for gluster'
                        ))

                self.logger.debug('Adding the host to the cluster')

                hosts_service = engine_api.system_service().hosts_service()
                hosts_service.add(
                    sdk4.types.Host(
                        name=self.environment[
                            ohostedcons.EngineEnv.APP_HOST_NAME
                        ],
                        # Note that the below is required for compatibility
                        # with vdsm-generated pki. See bz 1178535.
                        address=self.environment[
                            ohostedcons.NetworkEnv.HOST_NAME
                        ],
                        cluster=cluster,
                        ssh=sdk4.types.Ssh(
                            authentication_method=sdk4.types.
                            SshAuthenticationMethod('publickey'),
                            port=self.environment[
                                ohostedcons.NetworkEnv.SSHD_PORT
                            ],
                        ),
                        override_iptables=self.environment[
                            otopicons.NetEnv.IPTABLES_ENABLE
                        ],
                    )
                )
                added_to_cluster = True
            except sdk4.Error as e:
                self.logger.debug(
                    'Cannot add the host to cluster {cluster}'.format(
                        cluster=cluster_name,
                    ),
                    exc_info=True,
                )
                self.logger.error(
                    _(
                        'Cannot automatically add the host '
                        'to cluster {cluster}:\n{details}\n'
                    ).format(
                        cluster=cluster_name,
                        details=e.detail
                    )
                )
                while not check_liveliness.manualSetupDispatcher(
                    self,
                    check_liveliness.MSD_FURTHER_ACTIONS,
                    self.environment[
                        ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
                    ]
                ):
                    pass

        up = self._wait_host_ready(
            engine_api,
            self.environment[ohostedcons.EngineEnv.APP_HOST_NAME]
        )
        # TODO: host-deploy restarted vdscli so we need to
        # connect again
        if not up:
            self.logger.error(
                _(
                    'Unable to add {host} to the manager'
                ).format(
                    host=self.environment[
                        ohostedcons.EngineEnv.APP_HOST_NAME
                    ],
                )
            )
        else:
            # This works only if the host is up.
            self.logger.debug('Setting CPU for the cluster')
            try:
                cluster, cpu = self._wait_cluster_cpu_ready(
                    engine_api,
                    cluster_name
                )
                self.logger.debug(cpu.__dict__)
                cpu.type = self.environment[ohostedcons.VDSMEnv.ENGINE_CPU]
                cluster.cpu = cpu
                engine_api.system_service().clusters_service().cluster_service(
                    cluster.id
                ).update(cluster)
            except sdk4.Error as e:
                self.logger.debug(
                    'Cannot set CPU level of cluster {cluster}'.format(
                        cluster=cluster_name,
                    ),
                    exc_info=True,
                )
                self.logger.error(
                    _(
                        'Cannot automatically set CPU level '
                        'of cluster {cluster}:\n{details}\n'
                    ).format(
                        cluster=cluster_name,
                        details=e.detail
                    )
                )
        engine_api.close()

    @plugin.event(
        stage=plugin.Stages.STAGE_CLEANUP,
    )
    def _cleanup(self):
        try:
            if self._host_deploy_conf is not None and os.path.exists(
                    self._host_deploy_conf
            ):
                os.unlink(self._host_deploy_conf)
        except EnvironmentError as ex:
            self.logger.error(
                _(
                    'Unable to cleanup temporary file: {msg} - '
                    'Please check and eventually manually cleanup {fnames} '
                    'otherwise future upgrade could be affected.'
                ).format(
                    msg=ex.message,
                    fname=self._host_deploy_conf,
                )
            )

# vim: expandtab tabstop=4 shiftwidth=4
