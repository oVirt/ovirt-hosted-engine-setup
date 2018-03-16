#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2017 Red Hat, Inc.
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


"""Storage domain plugin."""


import gettext
import re

from otopi import plugin
from otopi import util

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import ansible_utils


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """Storage domain plugin."""

    _IPADDR_RE = re.compile(r'(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})')

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    def _query_nfs_version(self):
        return self.dialog.queryString(
            name='OVEHOSTED_STORAGE_NFS_VERSION',
            note=_(
                'Please specify the nfs version '
                'you would like to use (@VALUES@)[@DEFAULT@]: '
            ),
            prompt=True,
            caseSensitive=True,
            validValues=(
                ohostedcons.NfsVersions.AUTO,
                ohostedcons.NfsVersions.V3,
                ohostedcons.NfsVersions.V4,
                ohostedcons.NfsVersions.V4_1,
            ),
            default=ohostedcons.NfsVersions.AUTO,
        )

    def _query_connection_path(self):
        return self.dialog.queryString(
            name='OVEHOSTED_STORAGE_DOMAIN_CONNECTION',
            note=_(
                'Please specify the full shared storage '
                'connection path to use (example: host:/path): '
            ),
            prompt=True,
            caseSensitive=True,
        )

    def _query_mnt_options(self, mnt_options):
        return self.dialog.queryString(
            name='OVEHOSTED_STORAGE_DOMAIN_MNT_OPTIONS',
            note=_(
                'If needed, specify additional mount options for '
                'the connection to the hosted-engine storage'
                'domain [@DEFAULT@]: '
            ),
            prompt=True,
            caseSensitive=True,
            default=mnt_options if mnt_options else '',
        )

    def _query_iscsi_portal(self):
        valid = False
        address = None
        while not valid:
            address = self.dialog.queryString(
                name='OVEHOSTED_STORAGE_ISCSI_IP_ADDR',
                note=_(
                    'Please specify the iSCSI portal IP address: '
                ),
                prompt=True,
                caseSensitive=True,
            )
            if address:
                valid = True
                for a in address.split(','):
                    match = self._IPADDR_RE.match(a)
                    if match:
                        # TODO: figure out a better regexp
                        # avoiding this check
                        valid &= True
                        for i in match.groups():
                            valid &= int(i) >= 0
                            valid &= int(i) < 255
                    else:
                        valid = False
            if not valid:
                self.logger.error(_('Address must be a valid IP address'))
        return address

    def _query_iscsi_port(self):
        valid = False
        while not valid:
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
                for p in port.split(','):
                    int_port = int(p)
                    if int_port > 0 and int_port < 65536:
                        valid = True
                    else:
                        raise ValueError(_('Port must be a valid port number'))
            except ValueError:
                self.logger.debug('exception', exc_info=True)
                self.logger.error(_('Port must be a valid port number'))
        return port

    def _query_iscsi_username(self, discover):
        valid = False
        username = None
        if discover:
            qtype = _('discover')
        else:
            qtype = _('portal login')
        while not valid:
            valid = True
            username = self.dialog.queryString(
                name='OVEHOSTED_STORAGE_ISCSI_USER',
                note=_(
                    'Please specify the iSCSI {qtype} user: '
                ).format(qtype=qtype),
                prompt=True,
                caseSensitive=True,
                default='',
            )
            if len(username) > ohostedcons.Const.MAX_STORAGE_USERNAME_LENGTH:
                valid = False
                self.logger.error(_(
                    'Username should not be longer than {i} characters.'
                ).format(i=ohostedcons.Const.MAX_STORAGE_USERNAME_LENGTH))
        return username

    def _query_iscsi_password(self, discover):
        valid = False
        password = None
        if discover:
            qtype = _('discover')
        else:
            qtype = _('portal login')
        while not valid:
            valid = True
            password = self.dialog.queryString(
                name='OVEHOSTED_STORAGE_ISCSI_PASSWORD',
                note=_(
                    'Please specify the iSCSI {qtype} password: '
                ).format(qtype=qtype),
                prompt=True,
                caseSensitive=True,
                hidden=True,
                default='',
            )
            if len(password) > ohostedcons.Const.MAX_STORAGE_PASSWORD_LENGTH:
                valid = False
                self.logger.error(_(
                    'Username should not be longer than {i} characters.'
                ).format(i=ohostedcons.Const.MAX_STORAGE_PASSWORD_LENGTH))
        return password

    def _query_iscsi_target(
            self,
            discover_username,
            discover_password,
            portal,
            port
    ):
        iscsi_discover_vars = {
            'FQDN': self.environment[
                ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
            ],
            'HOST_NAME': self.environment[
                ohostedcons.EngineEnv.APP_HOST_NAME
            ],
            'ADMIN_PASSWORD': self.environment[
                ohostedcons.EngineEnv.ADMIN_PASSWORD
            ],
            'ISCSI_DISCOVER_USERNAME': discover_username,
            'ISCSI_DISCOVER_PASSWORD': discover_password,
            'ISCSI_PORTAL_ADDR': portal,
            'ISCSI_PORTAL_PORT': port,
        }
        ah = ansible_utils.AnsibleHelper(
            playbook_name=ohostedcons.FileLocations.HE_AP_ISCSI_DISCOVER,
            extra_vars=iscsi_discover_vars,
        )
        self.logger.info(_('Discovering iSCSI targets'))
        r = ah.run()
        self.logger.debug(r)
        try:
            values = r[
                'otopi_iscsi_targets'
            ]['json']['discovered_targets']['iscsi_details']
        except KeyError:
            raise RuntimeError(_('Unable to find any target'))
        self.logger.debug(values)
        f_targets = []
        found = {}
        for v in values:
            self.logger.debug(v)
            target = v['target']
            tpgt = v['portal'].split(',')[1]
            if target not in found:
                found[target] = {}
            if tpgt not in found[target]:
                found[target][tpgt] = []
            found[target][tpgt].append(
                {
                    'address': v['address'],
                    'port': v['port']
                }
            )
        self.logger.debug(found)
        for target in found:
            for tpgt in found[target]:
                f_targets.append(
                    {
                        'index': str(len(f_targets)+1),
                        'target': target,
                        'tpgt': tpgt,
                        'address_port_l': found[target][tpgt]
                    }
                )
        target_list = ''
        for entry in f_targets:
            target_list += _(
                '\t[{index}]\t{target}\n\t\tTPGT: {tpgt}, portals:\n'
            ).format(
                index=entry['index'],
                target=entry['target'],
                tpgt=entry['tpgt'],
            )
            for pp in entry['address_port_l']:
                target_list += _(
                    '\t\t\t{portal}:{port}\n'
                ).format(
                    portal=pp['address'],
                    port=pp['port'],
                )
            target_list += '\n'

        self.dialog.note(
            _(
                'The following targets have been found:\n'
                '{target_list}'
            ).format(
                target_list=target_list,
            )
        )
        s_target = self.dialog.queryString(
            name='OVEHOSTED_STORAGE_ISCSI_TARGET',
            note=_(
                'Please select a target '
                '(@VALUES@) [@DEFAULT@]: '
            ),
            prompt=True,
            caseSensitive=True,
            default='1',
            validValues=[i['index'] for i in f_targets],
        )
        apl = f_targets[int(s_target)-1]['address_port_l']
        return (
            f_targets[int(s_target)-1]['target'],
            f_targets[int(s_target)-1]['tpgt'],
            ','.join([x['address'] for x in apl]),
            ','.join([x['port'] for x in apl]),
        )

    def _query_iscsi_lunid(self, username, password, portal, port, target):
        iscsi_getdevices_vars = {
            'FQDN': self.environment[
                ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
            ],
            'HOST_NAME': self.environment[
                ohostedcons.EngineEnv.APP_HOST_NAME
            ],
            'ADMIN_PASSWORD': self.environment[
                ohostedcons.EngineEnv.ADMIN_PASSWORD
            ],
            'ISCSI_USERNAME': username,
            'ISCSI_PASSWORD': password,
            'ISCSI_PORTAL_ADDR': portal,
            'ISCSI_PORTAL_PORT': port,
            'ISCSI_TARGET': target,
        }
        ah = ansible_utils.AnsibleHelper(
            playbook_name=ohostedcons.FileLocations.HE_AP_ISCSI_GETDEVICES,
            extra_vars=iscsi_getdevices_vars,
        )
        self.logger.info(_('Getting iSCSI LUNs list'))
        r = ah.run()
        self.logger.debug(r)
        available_luns = []
        if (
            'otopi_iscsi_devices' in r and
            'ansible_facts' in r['otopi_iscsi_devices'] and
            'ovirt_host_storages' in r['otopi_iscsi_devices']['ansible_facts']
        ):
            available_luns = r[
                'otopi_iscsi_devices'
            ][
                'ansible_facts'
            ]['ovirt_host_storages']
        return self._select_lun(available_luns)

    def _query_fc_lunid(self):
        fc_getdevices_vars = {
            'FQDN': self.environment[
                ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
            ],
            'HOST_NAME': self.environment[
                ohostedcons.EngineEnv.APP_HOST_NAME
            ],
            'ADMIN_PASSWORD': self.environment[
                ohostedcons.EngineEnv.ADMIN_PASSWORD
            ]
        }
        ansible_helper = ansible_utils.AnsibleHelper(
            playbook_name=ohostedcons.FileLocations.HE_AP_FC_GETDEVICES,
            extra_vars=fc_getdevices_vars,
        )
        self.logger.info(_('Getting Fibre Channel LUNs list'))
        r = ansible_helper.run()
        self.logger.debug(r)
        available_luns = []
        if (
            'otopi_fc_devices' in r and
            'ansible_facts' in r['otopi_fc_devices'] and
            'ovirt_host_storages' in r['otopi_fc_devices']['ansible_facts']
        ):
            available_luns = r[
                'otopi_fc_devices'
            ][
                'ansible_facts'
            ]['ovirt_host_storages']
        return self._select_lun(available_luns)

    def _select_lun(self, available_luns):
        if len(available_luns) == 0:
            msg = _('Cannot find any LUN on the selected target')
            self.logger.error(msg)
            raise RuntimeError(msg)

        f_luns = []
        lun_list = ''
        available_luns = sorted(available_luns, key=lambda lun: lun['id'])
        self.logger.debug(available_luns)
        # TODO: enforce free and minimum free space
        for entry in available_luns:
            paths = entry['logical_units'][0]['paths']
            f_luns.append(
                {
                    'index': str(len(f_luns)+1),
                    'id': entry['id'],
                    'capacityGiB': int(
                        entry['logical_units'][0]['size']
                    ) / pow(2, 30),
                    'vendorID': entry['logical_units'][0]['vendor_id'],
                    'productID': entry['logical_units'][0]['product_id'],
                    'status': entry['logical_units'][0]['status'],
                    'paths': paths,
                    'discard_max_size': int(entry['logical_units'][0]
                                            ['discard_max_size'])
                }
            )
        for entry in f_luns:
            lun_list += _(
                '\t[{i}]\t{id}\t{capacityGiB}GiB\t{vendorID}\t{productID}\n'
                '\t\tstatus: {status}, paths: {ap} active'
            ).format(
                i=entry['index'],
                id=entry['id'],
                capacityGiB=entry['capacityGiB'],
                vendorID=entry['vendorID'],
                productID=entry['productID'],
                status=entry['status'],
                ap=entry['paths'],
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
        return f_luns[int(slun)-1]

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.StorageEnv.NFS_VERSION,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.DOMAIN_TYPE,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.MNT_OPTIONS,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.STORAGE_DOMAIN_NAME,
            ohostedcons.Defaults.DEFAULT_STORAGE_DOMAIN_NAME
        )
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
            ohostedcons.StorageEnv.ISCSI_DISCOVER_USER,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.ISCSI_DISCOVER_PASSWORD,
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

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        name=ohostedcons.Stages.ANSIBLE_CREATE_SD,
        after=[
            ohostedcons.Stages.ANSIBLE_BOOTSTRAP_LOCAL_VM,
        ],
    )
    def _closeup(self):
        created = False
        interactive = True
        if (
            self.environment[ohostedcons.StorageEnv.DOMAIN_TYPE] is not None or
            self.environment[
                ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
            ] is not None or
            self.environment[ohostedcons.StorageEnv.MNT_OPTIONS] is not None or
            self.environment[ohostedcons.StorageEnv.NFS_VERSION] is not None or
            self.environment[
                ohostedcons.StorageEnv.ISCSI_IP_ADDR
            ] is not None or
            self.environment[
                ohostedcons.StorageEnv.ISCSI_PORT
            ] is not None or
            self.environment[
                ohostedcons.StorageEnv.ISCSI_USER
            ] is not None or
            self.environment[
                ohostedcons.StorageEnv.ISCSI_PASSWORD
            ] is not None or
            self.environment[
                ohostedcons.StorageEnv.ISCSI_TARGET
            ] is not None or
            self.environment[
                ohostedcons.StorageEnv.ISCSI_TARGET
            ] is not None
        ):
            interactive = False
        while not created:
            domain_type = self.environment[ohostedcons.StorageEnv.DOMAIN_TYPE]
            storage_domain_connection = self.environment[
                ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
            ]
            storage_domain_address = None
            storage_domain_path = None
            mnt_options = self.environment[
                ohostedcons.StorageEnv.MNT_OPTIONS
            ]
            nfs_version = self.environment[
                ohostedcons.StorageEnv.NFS_VERSION
            ]
            iscsi_portal = self.environment[
                ohostedcons.StorageEnv.ISCSI_IP_ADDR
            ]
            iscsi_port = self.environment[
                ohostedcons.StorageEnv.ISCSI_PORT
            ]
            iscsi_username = self.environment[
                ohostedcons.StorageEnv.ISCSI_USER
            ]
            iscsi_password = self.environment[
                ohostedcons.StorageEnv.ISCSI_PASSWORD
            ]
            iscsi_discover_username = self.environment[
                ohostedcons.StorageEnv.ISCSI_DISCOVER_USER
            ]
            iscsi_discover_password = self.environment[
                ohostedcons.StorageEnv.ISCSI_DISCOVER_PASSWORD
            ]
            iscsi_target = self.environment[
                ohostedcons.StorageEnv.ISCSI_TARGET
            ]
            lunid = self.environment[
                ohostedcons.StorageEnv.LUN_ID
            ]
            discard = True

            if domain_type is None:
                domain_type = self.dialog.queryString(
                    name='OVEHOSTED_STORAGE_DOMAIN_TYPE',
                    note=_(
                        'Please specify the storage '
                        'you would like to use (@VALUES@)[@DEFAULT@]: '
                    ),
                    prompt=True,
                    caseSensitive=True,
                    validValues=(
                        ohostedcons.DomainTypes.GLUSTERFS,
                        ohostedcons.DomainTypes.ISCSI,
                        ohostedcons.DomainTypes.FC,
                        ohostedcons.DomainTypes.NFS,
                    ),
                    default=ohostedcons.DomainTypes.NFS,
                )
            else:
                if domain_type == ohostedcons.DomainTypes.NFS3:
                    domain_type = ohostedcons.DomainTypes.NFS
                    self.environment[
                        ohostedcons.StorageEnv.NFS_VERSION
                    ] = ohostedcons.NfsVersions.V3
                elif domain_type == ohostedcons.DomainTypes.NFS4:
                    domain_type = ohostedcons.DomainTypes.NFS
                    self.environment[
                        ohostedcons.StorageEnv.NFS_VERSION
                    ] = ohostedcons.NfsVersions.V4

            if domain_type == ohostedcons.DomainTypes.NFS:
                if nfs_version is None:
                    nfs_version = self._query_nfs_version()

            if (
                domain_type == ohostedcons.DomainTypes.NFS or
                domain_type == ohostedcons.DomainTypes.GLUSTERFS
            ):
                if storage_domain_connection is None:
                    storage_domain_connection = self._query_connection_path()
                storage_domain_det = storage_domain_connection.split(':')
                if len(storage_domain_det) != 2:
                    msg = _('Invalid connection path')
                    self.logger.error(msg)
                    if not interactive:
                        raise RuntimeError(msg)
                    continue
                storage_domain_address = storage_domain_det[0]
                storage_domain_path = storage_domain_det[1]

                if mnt_options is None:
                    mnt_options = self._query_mnt_options(mnt_options)

            elif domain_type == ohostedcons.DomainTypes.ISCSI:
                if iscsi_portal is None:
                    iscsi_portal = self._query_iscsi_portal()
                    storage_domain_address = iscsi_portal
                if iscsi_port is None:
                    iscsi_port = self._query_iscsi_port()
                if iscsi_discover_username is None:
                    iscsi_discover_username = self._query_iscsi_username(
                        discover=True
                    )
                if iscsi_discover_password is None:
                    iscsi_discover_password = self._query_iscsi_password(
                        discover=True
                    )
                if iscsi_username is None:
                    iscsi_username = self._query_iscsi_username(
                        discover=False
                    )
                if iscsi_password is None:
                    iscsi_password = self._query_iscsi_password(
                        discover=False
                    )
                if iscsi_target is None:
                    try:
                        iscsi_target, iscsi_tpgt, iscsi_portal, iscsi_port = \
                            self._query_iscsi_target(
                                discover_username=iscsi_discover_username,
                                discover_password=iscsi_discover_password,
                                portal=iscsi_portal,
                                port=iscsi_port,
                            )
                    except RuntimeError as e:
                        self.logger.error(_('Unable to get target list'))
                        if not interactive:
                            raise e
                        continue
                if lunid is None:
                    try:
                        lun = self._query_iscsi_lunid(
                            username=iscsi_username,
                            password=iscsi_password,
                            portal=iscsi_portal,
                            port=iscsi_port,
                            target=iscsi_target
                        )
                        lunid = lun['id']
                        discard = lun['discard_max_size'] > 0
                        self.logger.info(
                            _("iSCSI discard after delete is {v}").format(
                                v=_("enabled") if discard else _("disabled")
                            )
                        )
                    except RuntimeError as e:
                        self.logger.error(_('Unable to get target list'))
                        if not interactive:
                            raise e
                        continue

            elif domain_type == ohostedcons.DomainTypes.FC:
                if lunid is None:
                    try:
                        lun = self._query_fc_lunid()
                        lunid = lun['id']
                        discard = lun['discard_max_size'] > 0
                        self.logger.info(
                            _("FC discard after delete is {v}").format(
                                v=_("enabled") if discard else _("disabled")
                            )
                        )
                    except RuntimeError as e:
                        self.logger.error(_('Unable to get target list'))
                        if not interactive:
                            raise e
                        continue

            else:
                self.logger.error(_('Currently not implemented'))
                if not interactive:
                    raise RuntimeError('Currently not implemented')
                continue

            storage_domain_vars = {
                'FQDN': self.environment[
                    ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
                ],
                'HOST_NAME': self.environment[
                    ohostedcons.EngineEnv.APP_HOST_NAME
                ],
                'ADMIN_PASSWORD': self.environment[
                    ohostedcons.EngineEnv.ADMIN_PASSWORD
                ],
                'STORAGE_DOMAIN_NAME': self.environment[
                    ohostedcons.StorageEnv.STORAGE_DOMAIN_NAME
                ],
                'STORAGE_DOMAIN_ADDR': storage_domain_address,
                'STORAGE_DOMAIN_PATH': storage_domain_path,
                'MOUNT_OPTIONS': mnt_options,
                'NFS_VERSION': nfs_version,
                'DOMAIN_TYPE': domain_type,
                'ISCSI_PORTAL_PORT': iscsi_port,
                'ISCSI_TARGET': iscsi_target,
                'LUN_ID': lunid,
                'ISCSI_USERNAME': iscsi_username,
                'ISCSI_PASSWORD': iscsi_password,
                'LOCAL_VM_DIR': self.environment[
                    ohostedcons.CoreEnv.LOCAL_VM_DIR
                ],
                'DISCARD': discard,
            }
            ah = ansible_utils.AnsibleHelper(
                playbook_name=ohostedcons.FileLocations.HE_AP_CREATE_SD,
                extra_vars=storage_domain_vars,
            )
            self.logger.info(_('Creating Storage Domain'))
            try:
                r = ah.run()
            except RuntimeError as e:
                if not interactive:
                    raise e
                continue
            self.logger.debug(
                'Create storage domain results {r}'.format(r=r)
            )
            if (
                'otopi_storage_domain_details' in r and
                'storagedomain' in r['otopi_storage_domain_details']
            ):
                storage_domain = r[
                    'otopi_storage_domain_details'
                ]['storagedomain']
                self.environment[
                    ohostedcons.StorageEnv.BDEVICE_SIZE_GB
                ] = int(storage_domain['available'])/1024/1024/1024
                if storage_domain['status'] == 'active':
                    created = True
                    # and set all the env values from the response
                    storage = storage_domain['storage']
                    storage_type = storage['type']
                    if storage_type == "fcp":
                        storage_type = "fc"  # Normalize type for HE broker.
                    self.environment[
                        ohostedcons.StorageEnv.DOMAIN_TYPE
                    ] = storage_type
                    if self.environment[
                        ohostedcons.StorageEnv.DOMAIN_TYPE
                    ] == ohostedcons.DomainTypes.NFS:
                        self.environment[
                            ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
                        ] = '{address}:{path}'.format(
                            address=storage['address'],
                            path=storage['path'],
                        )
                        # TODO: any way to get it from the engine
                        self.environment[
                            ohostedcons.StorageEnv.MNT_OPTIONS
                        ] = mnt_options
                        self.environment[
                            ohostedcons.StorageEnv.NFS_VERSION
                        ] = storage['nfs_version']
                    if self.environment[
                        ohostedcons.StorageEnv.DOMAIN_TYPE
                    ] == ohostedcons.DomainTypes.GLUSTERFS:
                        self.environment[
                            ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
                        ] = '{address}:{path}'.format(
                            address=storage['address'],
                            path=storage['path'],
                        )
                        self.environment[
                            ohostedcons.StorageEnv.MNT_OPTIONS
                        ] = mnt_options
                    if self.environment[
                        ohostedcons.StorageEnv.DOMAIN_TYPE
                    ] == ohostedcons.DomainTypes.ISCSI:
                        self.logger.info(
                            _('iSCSI connected paths: {n}').format(
                                n=len(storage['volume_group']['logical_units'])
                            )
                        )
                        self.environment[
                            ohostedcons.StorageEnv.ISCSI_PORTAL
                        ] = storage['volume_group']['logical_units'][
                            0
                        ]['portal'].split(',')[1]
                        lun0 = storage['volume_group']['logical_units'][0]
                        self.environment[
                            ohostedcons.StorageEnv.ISCSI_IP_ADDR
                        ] = ','.join([x['address'] for x in storage[
                            'volume_group'
                        ]['logical_units']])
                        self.environment[
                            ohostedcons.StorageEnv.STORAGE_DOMAIN_CONNECTION
                        ] = self.environment[
                            ohostedcons.StorageEnv.ISCSI_IP_ADDR
                        ]
                        self.environment[
                            ohostedcons.StorageEnv.ISCSI_PORT
                        ] = ','.join([str(x['port']) for x in storage[
                            'volume_group'
                        ]['logical_units']])
                        self.environment[
                            ohostedcons.StorageEnv.ISCSI_TARGET
                        ] = lun0['target']
                        self.environment[
                            ohostedcons.StorageEnv.LUN_ID
                        ] = lun0['id']
                        self.environment[
                            ohostedcons.StorageEnv.ISCSI_USER
                        ] = iscsi_username
                        self.environment[
                            ohostedcons.StorageEnv.ISCSI_PASSWORD
                        ] = iscsi_password
                else:
                    if not interactive:
                        raise RuntimeError('Failed creating storage domain')
            else:
                if not interactive:
                    raise RuntimeError('Failed creating storage domain')


# vim: expandtab tabstop=4 shiftwidth=4
