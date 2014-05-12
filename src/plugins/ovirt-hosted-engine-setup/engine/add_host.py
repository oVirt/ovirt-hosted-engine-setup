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


"""
Host adder plugin.
"""

import contextlib
import gettext
import os
import re
import tempfile
import time
import urllib2


import ethtool


import ovirtsdk.api
import ovirtsdk.xml
import ovirtsdk.infrastructure.errors


from otopi import util
from otopi import plugin
from otopi import constants as otopicons
from otopi import transaction
from otopi import filetransaction


from ovirt_hosted_engine_setup import constants as ohostedcons


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    Host adder plugin.
    """

    VDSM_RETRIES = 600
    VDSM_DELAY = 1
    _ADDRESS_RE = re.compile(
        flags=re.VERBOSE,
        pattern=r"""
            \s+
            inet
            \s
            (?P<address>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})
            .+
            \s+
            (?P<interface>\w+)
            $
    """
    )

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._ovirtsdk_api = ovirtsdk.api
        self._ovirtsdk_xml = ovirtsdk.xml
        self.cert = None

    def _getPKICert(self):
        self.logger.debug('Acquiring ca.crt from the engine')
        with contextlib.closing(
            urllib2.urlopen(
                'http://{fqdn}/ca.crt'.format(
                    fqdn=self.environment[
                        ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
                    ]
                )
            )
        ) as urlObj:
            content = urlObj.read()
            if content:
                self.logger.debug(content)
                fd, self.cert = tempfile.mkstemp(
                    prefix='engine-ca',
                    suffix='.crt',
                )
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, 'w') as fileobj:
                    fileobj.write(content)

    def _getSSHkey(self):
        self.logger.debug('Acquiring SSH key from the engine')
        with contextlib.closing(
            urllib2.urlopen(
                'http://{fqdn}/engine.ssh.key.txt'.format(
                    fqdn=self.environment[
                        ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
                    ]
                )
            )
        ) as urlObj:
            authorized_keys_line = urlObj.read()
            if authorized_keys_line:
                self.logger.debug(authorized_keys_line)
                authorized_keys_file = os.path.join(
                    os.path.expanduser('~root'),
                    '.ssh',
                    'authorized_keys'
                )
                content = []
                if os.path.exists(authorized_keys_file):
                    with open(authorized_keys_file, 'r') as f:
                        content = f.read().splitlines()
                if not authorized_keys_line in content:
                    content.append(authorized_keys_line)
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
            rc, stdout, stderr = self.execute(
                (
                    self.command.get('restorecon'),
                    '-r',
                    path
                )
            )
            if rc != 0:
                self.logger.error(
                    _('Failed to refresh SELINUX context for {path}').format(
                        path=path
                    )
                )

    def _getIPAddress(self):
        address = None
        stdout = ''
        if (
            self.environment[ohostedcons.NetworkEnv.BRIDGE_NAME] in
            ethtool.get_devices()
        ):
            self.logger.debug('Acquiring bridge address')
            rc, stdout, stderr = self.execute(
                args=(
                    self.command.get('ip'),
                    'addr',
                    'show',
                    self.environment[ohostedcons.NetworkEnv.BRIDGE_NAME],
                ),
            )
        else:
            self.logger.debug('Acquiring nic address')
            rc, stdout, stderr = self.execute(
                args=(
                    self.command.get('ip'),
                    'addr',
                    'show',
                    self.environment[ohostedcons.NetworkEnv.BRIDGE_IF],
                ),
            )
        for line in stdout:
            addressmatch = self._ADDRESS_RE.match(line)
            if addressmatch is not None:
                address = addressmatch.group('address')
                break
        if address is None:
            raise RuntimeError(_('Cannot acquire bridge address'))
        self.logger.debug(address)
        return address

    def _wait_host_ready(self, engine_api, host):
        self.logger.info(_(
            'Waiting for the host to become operational in the engine. '
            'This may take several minutes...'
        ))
        tries = self.VDSM_RETRIES
        isUp = False
        while not isUp and tries > 0:
            tries -= 1
            try:
                state = engine_api.hosts.get(host).status.state
            except Exception as exc:
                #sadly all ovirtsdk errors inherit only from Exception
                self.logger.debug(
                    'Error fetching host state: {error}'.format(
                        error=str(exc),
                    )
                )
                state = ''
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
                self.logger.debug(
                    'VDSM host in {state} state'.format(
                        state=state,
                    )
                )
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

    def _wait_cluster_cpu_ready(self, engine_api, cluster_name):
        tries = self.VDSM_RETRIES
        cpu = None
        while cpu is None and tries > 0:
            tries -= 1
            cluster = engine_api.clusters.get(cluster_name)
            cpu = cluster.get_cpu()
            if cpu is None:
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
                            "to become operational..."
                        ).format(
                            name=cluster.name,
                        )
                    )
                time.sleep(self.VDSM_DELAY)
        if cpu is None and tries == 0:
            self.logger.error(_(
                'Timed out while waiting for cluster to become ready. '
                'Please check the logs.'
            ))
        return cluster, cpu

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.EngineEnv.ADMIN_PASSWORD,
            None
        )
        self.environment[otopicons.CoreEnv.LOG_FILTER_KEYS].append(
            ohostedcons.EngineEnv.ADMIN_PASSWORD
        )
        self.environment.setdefault(
            ohostedcons.EngineEnv.APP_HOST_NAME,
            None
        )
        self._selinux_enabled = False

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        self.command.detect('ip')
        self.command.detect('selinuxenabled')
        self.command.detect('restorecon')

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_ENGINE,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_ENGINE,
        ),
    )
    def _customization(self):
        interactive = (
            self.environment[ohostedcons.EngineEnv.APP_HOST_NAME] is None
        )
        while self.environment[ohostedcons.EngineEnv.APP_HOST_NAME] is None:
            hostname = self.dialog.queryString(
                name='APP_HOST_NAME',
                note=_(
                    'Enter the name which will be used to identify this host'
                    ' inside the Administrator Portal [@DEFAULT@]: '
                ),
                prompt=True,
                default='hosted_engine_%s' % self.environment[
                    ohostedcons.StorageEnv.HOST_ID
                ],
            )
            if hostname:
                self.environment[
                    ohostedcons.EngineEnv.APP_HOST_NAME
                ] = hostname
            else:
                if interactive:
                    self.logger.error(_('Please specify a host name'))
                else:
                    raise RuntimeError(
                        _('Empty host name not allowed')
                    )

        interactive = (
            self.environment[ohostedcons.EngineEnv.ADMIN_PASSWORD] is None
        )
        while self.environment[ohostedcons.EngineEnv.ADMIN_PASSWORD] is None:
            password = self.dialog.queryString(
                name='ENGINE_ADMIN_PASSWORD',
                note=_(
                    "Enter 'admin@internal' user password that "
                    'will be used for accessing the Administrator Portal: '
                ),
                prompt=True,
                hidden=True,
            )
            if password:
                if not interactive:
                    self.environment[
                        ohostedcons.EngineEnv.ADMIN_PASSWORD
                    ] = password
                else:
                    password_check = self.dialog.queryString(
                        name='ENGINE_ADMIN_PASSWORD',
                        note=_(
                            "Confirm 'admin@internal' user password: "
                        ),
                        prompt=True,
                        hidden=True,
                    )
                    if password == password_check:
                        self.environment[
                            ohostedcons.EngineEnv.ADMIN_PASSWORD
                        ] = password
                    else:
                        self.logger.error(_('Passwords do not match'))
            else:
                if interactive:
                    self.logger.error(_('Please specify a password'))
                else:
                    raise RuntimeError(
                        _('Empty password not allowed for user admin')
                    )

    @plugin.event(
        stage=plugin.Stages.STAGE_VALIDATION,
    )
    def _validation(self):
        if self.command.get('selinuxenabled', optional=True) is None:
            self._selinux_enabled = False
        else:
            rc, stdout, stderr = self.execute(
                (
                    self.command.get('selinuxenabled'),
                ),
                raiseOnError=False,
            )
            self._selinux_enabled = rc == 0

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        after=(
            ohostedcons.Stages.ENGINE_ALIVE,
        ),
        name=ohostedcons.Stages.HOST_ADDED,
    )
    def _closeup(self):
        self._getPKICert()
        self._getSSHkey()
        try:
            self.logger.debug('Connecting to the Engine')
            engine_api = self._ovirtsdk_api.API(
                url='https://{fqdn}/ovirt-engine/api'.format(
                    fqdn=self.environment[
                        ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
                    ],
                ),
                username='admin@internal',
                password=self.environment[
                    ohostedcons.EngineEnv.ADMIN_PASSWORD
                ],
                ca_file=self.cert,
            )
            self.logger.debug('Adding the host to the cluster')
            engine_api.hosts.add(
                self._ovirtsdk_xml.params.Host(
                    name=self.environment[
                        ohostedcons.EngineEnv.APP_HOST_NAME
                    ],
                    address=self._getIPAddress(),
                    reboot_after_installation=False,
                    cluster=engine_api.clusters.get('Default'),
                    ssh=self._ovirtsdk_xml.params.SSH(
                        authentication_method='publickey',
                        port=self.environment[
                            ohostedcons.NetworkEnv.SSHD_PORT
                        ],
                    ),
                    override_iptables=True,
                )
            )
        except ovirtsdk.infrastructure.errors.RequestError as e:
            self.logger.debug(
                'Cannot add the host to the Default cluster',
                exc_info=True,
            )
            self.logger.error(
                _(
                    'Cannot automatically add the host '
                    'to the Default cluster:\n{details}\n'
                ).format(
                    details=e.detail
                )
            )
        up = self._wait_host_ready(
            engine_api,
            self.environment[ohostedcons.EngineEnv.APP_HOST_NAME]
        )
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
            #This works only if the host is up.
            self.logger.debug('Setting CPU for the cluster')
            try:
                cluster, cpu = self._wait_cluster_cpu_ready(
                    engine_api,
                    'Default'
                )
                self.logger.debug(cpu.__dict__)
                cpu.set_id(self.environment[ohostedcons.VDSMEnv.ENGINE_CPU])
                cluster.set_cpu(cpu)
                cluster.update()
            except ovirtsdk.infrastructure.errors.RequestError as e:
                self.logger.debug(
                    'Cannot set the CPU level to the Default cluster',
                    exc_info=True,
                )
                self.logger.error(
                    _(
                        'Cannot automatically set the CPU '
                        'to the Default cluster:\n{details}\n'
                    ).format(
                        details=e.detail
                    )
                )
        engine_api.disconnect()

    @plugin.event(
        stage=plugin.Stages.STAGE_CLEANUP,
    )
    def _cleanup(self):
        if self.cert is not None and os.path.exists(self.cert):
            os.unlink(self.cert)


# vim: expandtab tabstop=4 shiftwidth=4
