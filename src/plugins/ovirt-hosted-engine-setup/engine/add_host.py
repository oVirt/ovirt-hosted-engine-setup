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
import urllib2


import ovirtsdk.api
import ovirtsdk.xml
import ovirtsdk.infrastructure.errors


from otopi import util
from otopi import plugin
from otopi import constants as otopicons


from ovirt_hosted_engine_setup import constants as ohostedcons


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    Host adder plugin.
    """

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

    def _getIPAddress(self):
        self.logger.debug('Acquiring bridge address')
        address = None
        rc, stdout, stderr = self.execute(
            args=(
                self.command.get('ip'),
                'addr',
                'show',
                self.environment[ohostedcons.NetworkEnv.BRIDGE_NAME],
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

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.EngineEnv.ADMIN_PASSWORD,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        self.command.detect('ip')

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
    )
    def _customization(self):
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
                self.environment[
                    ohostedcons.EngineEnv.ADMIN_PASSWORD
                ] = password
            else:
                if interactive:
                    self.logger.error(_('Please specify a password'))
                else:
                    raise RuntimeError(
                        _('Empty password not allowed for user admin')
                    )
        self.environment[otopicons.CoreEnv.LOG_FILTER].append(
            self.environment[ohostedcons.EngineEnv.ADMIN_PASSWORD]
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        after=[
            ohostedcons.Stages.ENGINE_ALIVE,
        ],
    )
    def _closeup(self):
        self._getPKICert()
        try:
            self.logger.debug('Connecting to the Engine')
            engine_api = self._ovirtsdk_api.API(
                url='https://{fqdn}/api'.format(
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
            self.logger.debug('Adding the local host to the local cluster')
            # TODO ask host name to be used in engine?
            engine_api.hosts.add(
                self._ovirtsdk_xml.params.Host(
                    name='local_host',
                    address=self._getIPAddress(),
                    reboot_after_installation=False,
                    cluster=engine_api.clusters.get('Default'),
                    root_password=self.environment[
                        ohostedcons.HostEnv.ROOT_PASSWORD
                    ]
                )
            )
        except ovirtsdk.infrastructure.errors.RequestError as e:
            self.logger.debug(
                'Cannot add the local host to the Default cluster',
                exc_info=True,
            )
            self.logger.error(
                _(
                    'Cannot automatically add the local host '
                    'to the Default cluster:\n{details}\n'
                ).format(
                    details=e.details
                )
            )

    @plugin.event(
        stage=plugin.Stages.STAGE_CLEANUP,
    )
    def _cleanup(self):
        if self.cert is not None and os.path.exists(self.cert):
            os.unlink(self.cert)


# vim: expandtab tabstop=4 shiftwidth=4
