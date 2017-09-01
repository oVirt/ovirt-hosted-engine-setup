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
iSCSI storage domain plugin.
"""


import gettext
import re
import time

from otopi import constants as otopicons
from otopi import plugin
from otopi import util

from ovirt_setup_lib import dialog

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import domains as ohosteddomains


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    Block devices (iSCSI, FC) storage domain plugin.
    """

    _MAXRETRY = 2
    _RETRY_DELAY = 1
    _IPADDR_RE = re.compile(r'(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})')

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._interactive = False
        self.cli = None
        self.domainType = None

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
        return dialog.queryEnvKey(
            dialog=self.dialog,
            logger=self.logger,
            env=self.environment,
            key=ohostedcons.StorageEnv.ISCSI_USER,
            note=_(
                'Please specify the iSCSI portal user: '
            ),
            prompt=True,
            hidden=False,
            tests=(
                {
                    'test': lambda username: (
                        '' if len(
                            username
                        ) <= ohostedcons.Const.MAX_STORAGE_USERNAME_LENGTH
                        else _(
                            'Username should not be longer than %i characters.'
                        ) % ohostedcons.Const.MAX_STORAGE_USERNAME_LENGTH
                    ),
                },
            ),
            name='OVEHOSTED_STORAGE_ISCSI_USER',
            default='',
            store=False,
        )

    def _customize_password(self, user):
        return '' if not user else dialog.queryEnvKey(
            dialog=self.dialog,
            logger=self.logger,
            env=self.environment,
            key=ohostedcons.StorageEnv.ISCSI_PASSWORD,
            note=_(
                'Please specify the iSCSI portal password: '
            ),
            prompt=True,
            hidden=True,
            tests=(
                {
                    'test': lambda password: (
                        '' if len(
                            password
                        ) <= ohostedcons.Const.MAX_STORAGE_PASSWORD_LENGTH
                        else _(
                            'Password should not be longer than %i characters.'
                        ) % ohostedcons.Const.MAX_STORAGE_PASSWORD_LENGTH
                    ),
                },
            ),
            name='OVEHOSTED_STORAGE_ISCSI_PASSWORD',
            default='',
            store=False,
        )

    def _customize_target(self, values, default):
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
        return target

    def _customize_lun(self, domainType, target):
        if domainType == ohostedcons.DomainTypes.ISCSI:
            available_luns = self._iscsi_get_lun_list(
                ip=self.environment[ohostedcons.StorageEnv.ISCSI_IP_ADDR],
                port=self.environment[ohostedcons.StorageEnv.ISCSI_PORT],
                user=self.environment[ohostedcons.StorageEnv.ISCSI_USER],
                password=self.environment[
                    ohostedcons.StorageEnv.ISCSI_PASSWORD
                ],
                iqn=target,
            )
        elif domainType == ohostedcons.DomainTypes.FC:
            available_luns = self._fc_get_lun_list()
        if len(available_luns) == 0:
            self.logger.error(_('Cannot find any LUN on the selected target'))
            return None

        f_luns = []
        lun_list = ''
        available_luns = sorted(available_luns, key=lambda lun: lun['GUID'])
        for entry in available_luns:
            activep = 0
            failedp = 0
            for pathstatus in entry['pathstatus']:
                if pathstatus['state'] == 'active':
                    activep += 1
                else:
                    failedp += 1
            f_luns.append(
                {
                    'index': str(len(f_luns)+1),
                    'GUID': entry['GUID'],
                    'capacityGiB': int(entry['capacity']) / pow(2, 30),
                    'vendorID': entry['vendorID'],
                    'productID': entry['productID'],
                    'status': entry['status'],
                    'activep': activep,
                    'failedp': failedp,
                }
            )
        for entry in f_luns:
            lun_list += _(
                '\t[{i}]\t{guid}\t{capacityGiB}GiB\t{vendorID}\t{productID}\n'
                '\t\tstatus: {status}, paths: {ap} active'
            ).format(
                i=entry['index'],
                guid=entry['GUID'],
                capacityGiB=entry['capacityGiB'],
                vendorID=entry['vendorID'],
                productID=entry['productID'],
                status=entry['status'],
                ap=entry['activep'],
            )
            if entry['failedp'] > 0:
                lun_list += _(', {fp} failed').format(
                    fp=entry['failedp'],
                )
            lun_list += '\n\n'

        self.dialog.note(
            _(
                'The following luns have been found on the requested target:\n'
                '{lun_list}'
            ).format(
                lun_list=lun_list,
            )
        )
        lunGUID = self.environment[ohostedcons.StorageEnv.LUN_ID]
        if lunGUID is None:
            self._interactive = True
            slun = self.dialog.queryString(
                name='OVEHOSTED_STORAGE_BLOCKD_LUN',
                note=_(
                    'Please select the destination LUN '
                    '(@VALUES@) [@DEFAULT@]: '
                ),
                prompt=True,
                caseSensitive=True,
                default='1',
                validValues=[i['index'] for i in f_luns],
            )
            lunGUID = f_luns[int(slun)-1]['GUID']
        return lunGUID

    def _customize_forcecreatevg(self):
        if self.environment[
            ohostedcons.StorageEnv.FORCE_CREATEVG
        ] is None:
            self.environment[
                ohostedcons.StorageEnv.FORCE_CREATEVG
            ] = self.dialog.queryString(
                name='OVEHOSTED_FORCE_CREATEVG',
                note=_(
                    'The selected device is already used.\n'
                    'To create a vg on this device, you must use Force.\n'
                    'WARNING: This will destroy existing data on the device.\n'
                    "(@VALUES@)[@DEFAULT@]? "
                ),
                prompt=True,
                validValues=(_('Force'), _('Abort')),
                caseSensitive=False,
                default=_('Abort'),
            ).lower() == _('Force').lower()

    def _create_vg(self, forceVG=False):
        return self.cli.createVG(
            name=self.environment[ohostedcons.StorageEnv.SD_UUID],
            devlist=[
                self.environment[
                    ohostedcons.StorageEnv.LUN_ID
                ],
            ],
            force=forceVG,
        )

    def _iscsi_discovery(self, address, port, user, password):
        targets = self.cli.discoverSendTargets(
            host=address,
            port=port,
            user=user,
            password=password,
        )
        self.logger.debug(targets)
        if targets['status']['code'] != 0:
            raise RuntimeError(targets['status']['message'])
        full_target_template = (
            '^(?P<portal_hostname>[\w\d\-\.]+):(?P<portal_port>\d+),'
            '(?P<tgpt>-?\d+) (?P<iqn>[\w\d\-\.:]+)$'
        )
        full_target_template_re = re.compile(full_target_template)
        found = []
        for t in targets['items']:
            m = full_target_template_re.match(t)
            mg = m.groupdict()
            if (
                mg['portal_hostname'] == address and
                mg['portal_port'] == port
            ):
                found.append(mg)
        self.logger.debug('found: {f}'.format(f=found))
        return found

    def _iscsi_get_lun_list(self, ip, port, user, password, iqn):
        retry = self._MAXRETRY
        iscsi_lun_list = []
        for _try in range(0, retry):
            devices = self.cli.getDeviceList(
                ohostedcons.VDSMConstants.ISCSI_DOMAIN
            )
            self.logger.debug(devices)
            if devices['status']['code'] != 0:
                raise RuntimeError(devices['status']['message'])
            if 'items' in devices:
                for device in devices['items']:
                    for path in device['pathlist']:
                        if path['iqn'] == iqn:
                            if device not in iscsi_lun_list:
                                iscsi_lun_list.append(device)
            if iscsi_lun_list:
                break

            self.logger.info('Discovering iSCSI node')
            self._iscsi_discovery(
                ip,
                port,
                user,
                password,
            )
            self.logger.info('Connecting to the storage server')
            connectionParams = [
                {
                    'connection': ip,
                    'iqn': iqn,
                    # FIXME!
                    'portal': '0',
                    'user': user,
                    'password': password,
                    'port': port,
                    'id': ohostedcons.Const.BLANK_UUID,
                }
            ]
            res = self.cli.connectStorageServer(
                storagepoolID=ohostedcons.Const.BLANK_UUID,
                domainType=ohostedcons.VDSMConstants.ISCSI_DOMAIN,
                connectionParams=connectionParams,
            )
            if res['status']['code'] != 0:
                raise RuntimeError(res['status']['message'])
            retry -= 1
            time.sleep(self._RETRY_DELAY)
        else:
            raise RuntimeError("Unable to retrieve the list of LUN(s) please "
                               "check the SELinux log and settings on your "
                               "iscsi target")
        return iscsi_lun_list

    def _fc_get_lun_list(self):
        fc_lun_list = []
        devices = self.cli.getDeviceList(
            ohostedcons.VDSMConstants.FC_DOMAIN
        )
        self.logger.debug(devices)
        if devices['status']['code'] != 0:
            raise RuntimeError(devices['status']['message'])
        for device in devices['items']:
            fc_lun_list.append(device)
        return fc_lun_list

    def _iscsi_get_device(self, ip, port, user, password, iqn, lunGUID):
        available_luns = self._iscsi_get_lun_list(
            ip, port, user, password, iqn
        )
        for iscsi_device in available_luns:
            if iscsi_device['GUID'] == lunGUID:
                    return iscsi_device
        return None

    def _fc_get_device(self, lunGUID):
        available_luns = self._fc_get_lun_list()
        for fc_device in available_luns:
            if fc_device['GUID'] == lunGUID:
                    return fc_device
        return None

    def _validate_domain(self, domainType, target, lunGUID):
        if domainType == ohostedcons.DomainTypes.ISCSI:
            device = self._iscsi_get_device(
                ip=self.environment[ohostedcons.StorageEnv.ISCSI_IP_ADDR],
                port=self.environment[ohostedcons.StorageEnv.ISCSI_PORT],
                user=self.environment[ohostedcons.StorageEnv.ISCSI_USER],
                password=self.environment[
                    ohostedcons.StorageEnv.ISCSI_PASSWORD
                ],
                iqn=target,
                lunGUID=lunGUID
            )
        elif domainType == ohostedcons.DomainTypes.FC:
            device = self._fc_get_device(lunGUID)
        if device is None:
            raise RuntimeError(
                _('The requested device is not listed by VDSM')
            )
        self.logger.debug(device)
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
                    'Error: device {lunGUID} has capacity of only '
                    '{capacity}Mb while a minimum of '
                    '{minimum}Mb is  required'
                ).format(
                    lunGUID=lunGUID,
                    capacity=size_mb,
                    minimum=ohostedcons.Const.MINIMUM_SPACE_STORAGEDOMAIN_MB,
                )
            )
        self.environment[
            ohostedcons.StorageEnv.BDEVICE_SIZE_GB
        ] = size_mb / pow(2, 10)
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

        if device['status'] == 'used' and device['vgUUID'] == '':
            self._customize_forcecreatevg()
            if not self.environment[
                ohostedcons.StorageEnv.FORCE_CREATEVG
            ]:
                raise RuntimeError(
                    _('The selected LUN is dirty; please clean it and retry')
                )

        self.environment[ohostedcons.StorageEnv.GUID] = device['GUID']

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
            ohostedcons.StorageEnv.LUN_ID,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.VG_UUID,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.GUID,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.FORCE_CREATEVG,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.CONFIG_STORAGE_BLOCKD,
        after=(
            ohostedcons.Stages.CONFIG_STORAGE_EARLY,
        ),
        before=(
            ohostedcons.Stages.CONFIG_STORAGE_LATE,
        ),
        condition=lambda self: (
            self.environment[
                ohostedcons.StorageEnv.DOMAIN_TYPE
            ] == ohostedcons.DomainTypes.ISCSI or
            self.environment[
                ohostedcons.StorageEnv.DOMAIN_TYPE
            ] == ohostedcons.DomainTypes.FC
        ),
    )
    def _customization(self):
        self.cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        self.domainType = self.environment[ohostedcons.StorageEnv.DOMAIN_TYPE]
        lunGUID = None
        valid_lun = False
        target = None
        if self.environment[ohostedcons.StorageEnv.MNT_OPTIONS]:
            msg = _(
                'Custom mount options are not supported on {type} devices.'
            ).format(
                type=self.domainType,
            )
            self.logger.error(msg)
            raise RuntimeError(msg)
        if self.domainType == ohostedcons.DomainTypes.ISCSI:
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
                    valid_targets_dict = self._iscsi_discovery(
                        address,
                        port,
                        user,
                        password,
                    )
                    valid_targets = [x['iqn'] for x in valid_targets_dict]
                    if valid_targets:
                        valid_access = True
                    else:
                        self.logger.error(_('No valid target'))
                except RuntimeError as e:
                    self.logger.debug('exception', exc_info=True)
                    self.logger.error(e)
                    if not self._interactive:
                        raise RuntimeError(_('Cannot access iSCSI portal'))
            self.environment[ohostedcons.StorageEnv.ISCSI_IP_ADDR] = address
            self.environment[ohostedcons.StorageEnv.ISCSI_PORT] = port
            self.environment[ohostedcons.StorageEnv.ISCSI_USER] = user
            self.environment[ohostedcons.StorageEnv.ISCSI_PASSWORD] = password

        while not valid_lun:
            if self.domainType == ohostedcons.DomainTypes.ISCSI:
                target = self._customize_target(
                    values=valid_targets,
                    default=valid_targets[0]
                )
            else:
                target = None
            lunGUID = self._customize_lun(self.domainType, target)
            if lunGUID is not None:
                try:
                    self._validate_domain(self.domainType, target, lunGUID)
                    valid_lun = True
                except Exception as e:
                    self.logger.debug('exception', exc_info=True)
                    self.logger.error(e)
                    if not self._interactive:
                        raise RuntimeError(_('Cannot access LUN'))
            elif self.domainType == ohostedcons.DomainTypes.FC:
                raise RuntimeError(
                    _('No LUN is accessible on FC')
                )
        if self.domainType == ohostedcons.DomainTypes.ISCSI:
            self.environment[ohostedcons.StorageEnv.ISCSI_TARGET] = target
        self.environment[ohostedcons.StorageEnv.LUN_ID] = lunGUID

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        after=(
            ohostedcons.Stages.VDSMD_START,
        ),
        before=(
            ohostedcons.Stages.STORAGE_AVAILABLE,
        ),
        condition=lambda self: (
            self.environment[
                ohostedcons.StorageEnv.DOMAIN_TYPE
            ] == ohostedcons.DomainTypes.ISCSI or
            self.environment[
                ohostedcons.StorageEnv.DOMAIN_TYPE
            ] == ohostedcons.DomainTypes.FC
        ),
    )
    def _misc(self):
        self.cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        if self.environment[ohostedcons.StorageEnv.VG_UUID] is None:
            # If we don't have a volume group we must create it
            forceVG = False
            if self.environment[
                ohostedcons.StorageEnv.FORCE_CREATEVG
            ]:
                forceVG = True
            self.logger.info(_('Creating Volume Group'))
            dom = self._create_vg(forceVG)
            self.logger.debug(dom)
            if dom['status']['code'] != 0:
                self.logger.error(
                    _(
                        'Error creating Volume Group: {message}'
                    ).format(
                        message=dom['status']['message']
                    )
                )
                if not forceVG:
                    # eventually retry forcing VG creation on dirty storage
                    self._customize_forcecreatevg()
                    if not self.environment[
                        ohostedcons.StorageEnv.FORCE_CREATEVG
                    ]:
                        raise RuntimeError(dom['status']['message'])
                    else:
                        forceVG = True
                        dom = self._create_vg(forceVG)
                        self.logger.debug(dom)
                        if dom['status']['code'] != 0:
                            self.logger.error(
                                _(
                                    'Error creating Volume Group: {message}'
                                ).format(
                                    message=dom['status']['message']
                                )
                            )
                            raise RuntimeError(dom['status']['message'])
                else:
                    raise RuntimeError(dom['status']['message'])
            self.environment[
                ohostedcons.StorageEnv.VG_UUID
            ] = dom['status']['message']

        vginfo = self.cli.getVGInfo(
            self.environment[ohostedcons.StorageEnv.VG_UUID]
        )
        self.logger.debug(vginfo)
        if vginfo['status']['code'] != 0:
            raise RuntimeError(vginfo['status']['message'])
        if (
            self.domainType == ohostedcons.DomainTypes.ISCSI and
            self.environment[ohostedcons.StorageEnv.ISCSI_PORTAL] is None
        ):
            try:
                for pv in vginfo['pvlist']:
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
