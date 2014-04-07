#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2014 Red Hat, Inc.
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
iSCSI storage domain plugin.
"""


import gettext
import re
import time


from otopi import constants as otopicons
from otopi import plugin
from otopi import util


from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import domains as ohosteddomains

_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    iSCSI storage domain plugin.
    """

    _MAXRETRY = 2
    _RETRY_DELAY = 1
    _IPADDR_RE = re.compile(r'(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})')

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._interactive = False
        self.serv = None
        self.vdsClient = util.loadModule(
            path=ohostedcons.FileLocations.VDS_CLIENT_DIR,
            name='vdsClient'
        )

    def _customize_ip_address(self):
        valid = False
        address = None
        while not valid:
            address = self.environment[ohostedcons.StorageEnv.ISCSI_IP_ADDR]
            if address is None:
                self._interactive = True
                address = self.dialog.queryString(
                    name='OVEHOSTED_STORAGE_ISCSI_IP_ADDR',
                    note=_(
                        'Please specify the iSCSI portal IP address: '
                    ),
                    prompt=True,
                    caseSensitive=True,
                )
            try:
                if address:
                    match = self._IPADDR_RE.match(address)
                    if match:
                        # TODO: figure out a better regexp avoiding this check
                        valid = True
                        for i in match.groups():
                            valid &= int(i) >= 0
                            valid &= int(i) < 255
                if not valid:
                    raise ValueError(_('Address must be a valid IP address'))
            except ValueError as e:
                if self.environment[
                    ohostedcons.StorageEnv.ISCSI_IP_ADDR
                ] is None:
                    self.logger.debug('exception', exc_info=True)
                    self.logger.error(_('Address must be a valid IP address'))
                else:
                    raise e
        return address

    def _customize_port(self):
        valid = False
        port = None
        while not valid:
            port = self.environment[ohostedcons.StorageEnv.ISCSI_PORT]
            if port is None:
                self._interactive = True
                port = self.dialog.queryString(
                    name='OVEHOSTED_STORAGE_ISCSI_IP_PORT',
                    note=_(
                        'Please specify the iSCSI portal port [@DEFAULT@]: '
                    ),
                    prompt=True,
                    caseSensitive=True,
                    default=ohostedcons.Defaults.DEFAULT_ISCSI_PORT,
                )
            try:
                int_port = int(port)
                if int_port > 0 and int_port < 65536:
                    valid = True
                else:
                    raise ValueError(_('Port must be a valid port number'))
            except ValueError as e:
                if self.environment[ohostedcons.StorageEnv.ISCSI_PORT] is None:
                    self.logger.debug('exception', exc_info=True)
                    self.logger.error(_('Port must be a valid port number'))
                else:
                    raise e
        return port

    def _customize_user(self):
        user = self.environment[ohostedcons.StorageEnv.ISCSI_USER]
        if user is None:
            self._interactive = True
            user = self.dialog.queryString(
                name='OVEHOSTED_STORAGE_ISCSI_USER',
                note=_(
                    'Please specify the iSCSI portal user: '
                ),
                prompt=True,
                caseSensitive=True,
                default='',
            )
        return user

    def _customize_password(self, user):
        password = ''
        if (
            user and
            self.environment[ohostedcons.StorageEnv.ISCSI_PASSWORD] is None
        ):
            self._interactive = True
            password = self.dialog.queryString(
                name='OVEHOSTED_STORAGE_ISCSI_PASSWORD',
                note=_(
                    'Please specify the iSCSI portal password: '
                ),
                prompt=True,
                hidden=True,
                default=''
            )
        return password

    def _customize_target(self, values, default):
        valid = False
        while not valid:
            target = self.environment[ohostedcons.StorageEnv.ISCSI_TARGET]
            if target is None:
                self._interactive = True
                target = self.dialog.queryString(
                    name='OVEHOSTED_STORAGE_ISCSI_TARGET',
                    note=_(
                        'Please specify the target name '
                        '(@VALUES@) [@DEFAULT@]: '
                    ),
                    prompt=True,
                    caseSensitive=True,
                    default=default,
                    validValues=values,
                )
            self._validate_domain(target)
            valid = True
        self.environment[ohostedcons.StorageEnv.ISCSI_TARGET] = target

    def _iscsi_discovery(self, address, port, user, password):
        targets = self.serv.s.discoverSendTargets(
            {
                'connection': address,
                'port': port,
                'user': user,
                'password': password,
            }
        )
        self.logger.debug(targets)
        if targets['status']['code'] != 0:
            raise RuntimeError(targets['status']['message'])
        return targets['targets']

    def _iscsi_get_device(self, ip, port, user, password, iqn):
        retry = self._MAXRETRY
        iscsi_device = None
        while iscsi_device is None and retry > 0:
            # check if the device is already known to VDSM
            devices = self.serv.s.getDeviceList(
                ohostedcons.VDSMConstants.ISCSI_DOMAIN
            )
            self.logger.debug(devices)
            if devices['status']['code'] != 0:
                raise RuntimeError(devices['status']['message'])
            for device in devices['devList']:
                for path in device['pathlist']:
                    if path['iqn'] == iqn:
                        iscsi_device = device
                        retry = -1
            if iscsi_device is None:
                self.logger.info('Discovering iSCSI node')
                self._iscsi_discovery(
                    ip,
                    port,
                    user,
                    password,
                )
                self.logger.info('Connecting to the storage server')
                res = self.serv.s.connectStorageServer(
                    ohostedcons.VDSMConstants.ISCSI_DOMAIN,
                    self.vdsClient.BLANK_UUID,
                    [
                        {
                            'connection': ip,
                            'iqn': iqn,
                            'portal': '0',
                            'user': user,
                            'password': password,
                            'port': port,
                            'id': self.vdsClient.BLANK_UUID,
                        }
                    ]
                )
                if res['status']['code'] != 0:
                    raise RuntimeError(devices['status']['message'])
            retry -= 1
            time.sleep(self._RETRY_DELAY)
        return iscsi_device

    def _validate_domain(self, target):
        device = self._iscsi_get_device(
            ip=self.environment[ohostedcons.StorageEnv.ISCSI_IP_ADDR],
            port=self.environment[ohostedcons.StorageEnv.ISCSI_PORT],
            user=self.environment[ohostedcons.StorageEnv.ISCSI_USER],
            password=self.environment[ohostedcons.StorageEnv.ISCSI_PASSWORD],
            iqn=target,
        )
        if device is None:
            raise RuntimeError(
                _('The requested device is not listed by VDSM')
            )
        size_mb = int(device['capacity']) / pow(2, 20)
        self.logger.debug(
            'Available space on {iqn} is {space}Mb'.format(
                iqn=target,
                space=size_mb
            )
        )
        if size_mb < ohostedcons.Const.MINIMUM_SPACE_STORAGEDOMAIN_MB:
            raise ohosteddomains.InsufficientSpaceError(
                _(
                    'Error: device {iqn} has capacity of only '
                    '{capacity}Mb while a minimum of '
                    '{minimum}Mb is  required'
                ).format(
                    iqn=target,
                    capacity=size_mb,
                    minimum=ohostedcons.Const.MINIMUM_SPACE_STORAGEDOMAIN_MB,
                )
            )
        if self.environment[
            ohostedcons.StorageEnv.VG_UUID
        ] is not None:
            if device['vgUUID'] != self.environment[
                ohostedcons.StorageEnv.VG_UUID
            ]:
                raise RuntimeError(
                    _(
                        'Specified VG UUID does not match '
                        'found UUID'
                    )
                )
        elif device['vgUUID'] != '':
            self.environment[
                ohostedcons.StorageEnv.VG_UUID
            ] = device['vgUUID']

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        self.command.detect('iscsiadm')

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.StorageEnv.ISCSI_IP_ADDR,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.ISCSI_PORT,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.ISCSI_PORTAL,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.ISCSI_USER,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.ISCSI_PASSWORD,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.ISCSI_TARGET,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.VG_UUID,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.CONFIG_STORAGE_ISCSI,
        after=(
            ohostedcons.Stages.CONFIG_STORAGE_EARLY,
        ),
        before=(
            ohostedcons.Stages.CONFIG_STORAGE_LATE,
        ),
        condition=(
            lambda self: self.environment[
                ohostedcons.StorageEnv.DOMAIN_TYPE
            ] == ohostedcons.DomainTypes.ISCSI
        ),
    )
    def _customization(self):
        self.serv = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        valid_access = False
        address = None
        port = None
        user = None
        password = None
        valid_targets = []
        while not valid_access:
            address = self._customize_ip_address()
            port = self._customize_port()
            user = self._customize_user()
            password = self._customize_password(user)
            self.environment[otopicons.CoreEnv.LOG_FILTER].append(password)
            # Validating access
            try:
                valid_targets = self._iscsi_discovery(
                    address,
                    port,
                    user,
                    password,
                )
                valid_access = True
            except RuntimeError as e:
                self.logger.debug('exception', exc_info=True)
                self.logger.error(e)
                if not self._interactive:
                    raise RuntimeError(_('Cannot access iSCSI portal'))
        self.environment[ohostedcons.StorageEnv.ISCSI_IP_ADDR] = address
        self.environment[ohostedcons.StorageEnv.ISCSI_PORT] = port
        self.environment[ohostedcons.StorageEnv.ISCSI_USER] = user
        self.environment[ohostedcons.StorageEnv.ISCSI_PASSWORD] = password

        self._customize_target(
            values=valid_targets,
            default=valid_targets[0]
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        after=(
            ohostedcons.Stages.VDSMD_START,
        ),
        before=(
            ohostedcons.Stages.STORAGE_AVAILABLE,
        ),
        condition=(
            lambda self: self.environment[
                ohostedcons.StorageEnv.DOMAIN_TYPE
            ] == ohostedcons.DomainTypes.ISCSI
        ),
    )
    def _misc(self):
        iscsi_device = self._iscsi_get_device(
            ip=self.environment[ohostedcons.StorageEnv.ISCSI_IP_ADDR],
            port=self.environment[ohostedcons.StorageEnv.ISCSI_PORT],
            user=self.environment[ohostedcons.StorageEnv.ISCSI_USER],
            password=self.environment[ohostedcons.StorageEnv.ISCSI_PASSWORD],
            iqn=self.environment[ohostedcons.StorageEnv.ISCSI_TARGET],
        )

        if self.environment[ohostedcons.StorageEnv.VG_UUID] is None:
            # If we don't have a volume group we must create it
            self.logger.info(_('Creating Volume Group'))
            dom = self.serv.s.createVG(
                self.environment[ohostedcons.StorageEnv.SD_UUID],
                [
                    iscsi_device['GUID'],
                ],
                False,
            )
            self.logger.debug(dom)
            if dom['status']['code'] != 0:
                raise RuntimeError(dom['status']['message'])
            self.environment[
                ohostedcons.StorageEnv.VG_UUID
            ] = dom['uuid']

        vginfo = self.serv.s.getVGInfo(
            self.environment[ohostedcons.StorageEnv.VG_UUID]
        )
        self.logger.debug(vginfo)
        if vginfo['status']['code'] != 0:
            raise RuntimeError(vginfo['status']['message'])
        if self.environment[ohostedcons.StorageEnv.ISCSI_PORTAL] is None:
            try:
                for pv in vginfo['info']['pvlist']:
                    for path in pv['pathlist']:
                        if path['iqn'] == self.environment[
                            ohostedcons.StorageEnv.ISCSI_TARGET
                        ]:
                            self.environment[
                                ohostedcons.StorageEnv.ISCSI_PORTAL
                            ] = path['portal']
                            break
            except (ValueError, KeyError) as e:
                self.logger.debug('exception', exc_info=True)
                self.logger.error(_('Cannot detect iSCSI portal'))
                raise e


# vim: expandtab tabstop=4 shiftwidth=4
