#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2015-2016 Red Hat, Inc.
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
VM cloud-init configuration plugin.
"""


import gettext
import os
import pwd
import re
import shutil
import tempfile

from otopi import constants as otopicons
from otopi import plugin
from otopi import util

from ovirt_setup_lib import hostname as osetuphostname

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import util as ohostedutil

import ethtool
import netaddr


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    VM cloud-init configuration plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._enable = False
        self._directory_name = None

    # TODO: Fix to support also IPv6
    _INET_ADDRESS_RE = re.compile(
        flags=re.VERBOSE,
        pattern=r"""
            \s+
            inet
            \s
            (?P<address>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2})
            .+
            \s+
            (?P<interface>[a-zA-Z0-9_.]+)
            $
    """
    )

    def _validate_ip_cidr(self, ipcidr):
        try:
            ip = netaddr.IPNetwork(ipcidr)
            if not (
                ip.ip and
                ip.ip.is_unicast() and
                not ip.ip.is_loopback()
            ):
                return None
            if ip.size > 1:
                if not (
                    ip.network and
                    ip.ip != ip.network and
                    ip.broadcast and
                    ip.ip != ip.broadcast
                ):
                    return None
        except netaddr.AddrFormatError:
            return None
        return ip

    def _validate_ip(self, ip):
        try:
            naip = netaddr.IPNetwork(ip)
        except netaddr.AddrFormatError:
            return None
        return self._validate_ip_cidr(
            str(ip) + ('/128' if str(naip.ipv6()) == str(ip) else '/32')
        )

    def _getMyIPAddress(self):
        device = (
            self.environment[ohostedcons.NetworkEnv.BRIDGE_NAME]
            if self.environment[ohostedcons.NetworkEnv.BRIDGE_NAME]
            in ethtool.get_devices()
            else self.environment[ohostedcons.NetworkEnv.BRIDGE_IF]
        )
        self.logger.debug(
            "Acquiring '{device}' address".format(
                device=device,
            )
        )
        rc, stdout, stderr = self.execute(
            args=(
                self.command.get('ip'),
                'addr',
                'show',
                device,
            ),
        )
        address = None
        for line in stdout:
            addressmatch = self._INET_ADDRESS_RE.match(line)
            if addressmatch is not None:
                address = addressmatch.group('address')
                break
        self.logger.debug('address: ' + str(address))

        if address is None:
            raise RuntimeError(
                _('Cannot acquire nic/bridge address')
            )
        try:
            ipna = netaddr.IPNetwork(address)
        except netaddr.AddrFormatError:
            raise RuntimeError(
                _('Cannot acquire a valid nic/bridge address')
            )
        return ipna

    def _getFreeIPAddress(self, myip):
        myipna = netaddr.IPNetwork(myip)
        for ip in myipna.iter_hosts():
            if ip != myip.ip:
                if not ohostedutil.check_is_pingable(self, ip):
                    return ip
        return ''

    def _msg_validate_ip_cidr(self, proposed_cidr):
        if not self._validate_ip_cidr(proposed_cidr):
            return _(
                "'{ipcidr}' is not a valid CIDR "
                "IP address"
            ).format(
                ipcidr=proposed_cidr
            )
        return None

    def _msg_validate_ip_cidr_subnet(self, proposed_cidr, v_ip, type):
        if type == 'h':
            elem = _('this host')
        elif type == 'g':
            elem = _('the default gateway')
        else:
            raise RuntimeError(
                _("'_msg_validate_ip_cidr_subnet - {type}: invalid host type'")
                .format(type=type)
            )
        if not netaddr.IPAddress(v_ip) in netaddr.IPNetwork(proposed_cidr):
            return _(
                'The Engine VM ({engine}) and {elem} '
                '({host}) will not be in the same IP subnet.\n'
                'Static routing configuration are not '
                'supported on automatic VM configuration.\n'
            ).format(
                engine=proposed_cidr,
                host=str(v_ip),
                elem=elem,
            )
        return None

    def _get_host_dns_configuration(self):
        nameservers = []
        try:
            rconf = open('/etc/resolv.conf', 'r')
            lines = rconf.readlines()
            for line in lines:
                ip = re.search(
                    # TODO: Fix to support also IPv6
                    r"^\s*nameserver\s(\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b)",
                    line
                )
                if ip:
                    nameservers.append(ip.group(1))
        except IOError:
            pass
        return ','.join(nameservers)

    def _error_raise_retry(self, msg, interactive):
        if msg:
            self.logger.error(msg)
            if not interactive:
                raise RuntimeError(msg)
            return msg

    def _customize_vm_addressing(self):
        interactive = self.environment[
            ohostedcons.CloudInit.VM_STATIC_CIDR
        ] is None
        my_ip = self._getMyIPAddress()
        valid = False
        while not valid:
            if interactive:
                static = self.dialog.queryString(
                    name='CI_VM_STATIC_NETWORKING',
                    note=_(
                        'How should the engine VM network '
                        'be configured '
                        '(@VALUES@)[@DEFAULT@]? '
                    ),
                    prompt=True,
                    validValues=(_('DHCP'), _('Static')),
                    caseSensitive=False,
                    default=_('DHCP')
                ) == _('Static').lower()
            else:
                static = self.environment[
                    ohostedcons.CloudInit.VM_STATIC_CIDR
                ]
            if static:
                if interactive:
                    default_ip = str(self._getFreeIPAddress(my_ip))
                    proposed_ip = self.dialog.queryString(
                        name='CLOUDINIT_VM_STATIC_IP_ADDRESS',
                        note=_(
                            'Please enter the IP address '
                            'to be used for the engine VM [@DEFAULT@]: '
                        ),
                        prompt=True,
                        caseSensitive=False,
                        default=default_ip,
                    )
                    proposed_cidr = proposed_ip + '/' + str(my_ip.prefixlen)
                else:
                    proposed_cidr = self.environment[
                        ohostedcons.CloudInit.VM_STATIC_CIDR
                    ]
                if self._error_raise_retry(
                    self._msg_validate_ip_cidr(proposed_cidr),
                    interactive
                ):
                    continue
                if self._error_raise_retry(
                    self._msg_validate_ip_cidr_subnet(
                        proposed_cidr,
                        my_ip,
                        'h'
                    ),
                    interactive,
                ):
                    continue
                if self._error_raise_retry(
                    self._msg_validate_ip_cidr_subnet(
                        proposed_cidr,
                        self.environment[
                            ohostedcons.NetworkEnv.GATEWAY
                        ],
                        'g'
                    ),
                    interactive,
                ):
                    continue
                self.logger.info(
                    _(
                        'The engine VM will be configured to use {cidr}'
                    ).format(
                        cidr=proposed_cidr
                    )
                )
                self.environment[
                    ohostedcons.CloudInit.VM_STATIC_CIDR
                ] = proposed_cidr
            else:  # DHCP
                self.environment[
                    ohostedcons.CloudInit.VM_STATIC_CIDR
                ] = False
            valid = True

    def _msg_validate_dns(self, dns_string):
        dnslist = dns_string.split(',')
        if len(dnslist) > 3:
            msg = _(
                'Just three DNS addresses are supported'
            )
            return msg
        for d in dnslist:
            if not self._validate_ip(d.strip()):
                msg = _(
                    "'{ip}' doesn't look like a valid IP address"
                ).format(ip=d)
                return msg
        return None

    def _customize_vm_dns(self):
        interactive = (
            self.environment[
                ohostedcons.CloudInit.VM_STATIC_CIDR
            ] and
            self.environment[ohostedcons.CloudInit.VM_DNS] is None
        )
        valid = False
        if interactive:
            dns_conf = self._get_host_dns_configuration()
        while not valid:
            if interactive:
                dns = self.dialog.queryString(
                    name='CI_DNS',
                    note=_(
                        'Please provide a comma-separated list (max 3) of IP '
                        'addresses of domain name servers for the engine VM\n'
                        'Engine VM DNS (leave it empty to skip) [@DEFAULT@]: '
                    ),
                    prompt=True,
                    default=dns_conf,
                )
            else:
                dns = self.environment[
                    ohostedcons.CloudInit.VM_DNS
                ]
            if not dns:
                self.environment[
                    ohostedcons.CloudInit.VM_DNS
                ] = False
                valid = True
                continue
            dns_clean = dns.replace(' ', '')
            if self._error_raise_retry(
                self._msg_validate_dns(dns_clean),
                interactive
            ):
                continue
            self.environment[
                ohostedcons.CloudInit.VM_DNS
            ] = dns_clean
            valid = True

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.CloudInit.GENERATE_ISO,
            None
        )
        self.environment.setdefault(
            ohostedcons.CloudInit.ROOTPWD,
            None
        )
        if self.environment[
            ohostedcons.CloudInit.ROOTPWD
        ]:
            self.environment[
                ohostedcons.CloudInit.ROOTPWD
            ] = self.environment[
                ohostedcons.CloudInit.ROOTPWD
            ].strip()
        self.environment[otopicons.CoreEnv.LOG_FILTER_KEYS].append(
            ohostedcons.CloudInit.ROOTPWD
        )
        self.environment.setdefault(
            ohostedcons.CloudInit.INSTANCE_HOSTNAME,
            None
        )
        self.environment.setdefault(
            ohostedcons.CloudInit.INSTANCE_DOMAINNAME,
            None
        )
        self.environment.setdefault(
            ohostedcons.CloudInit.EXECUTE_ESETUP,
            None
        )
        self.environment.setdefault(
            ohostedcons.CloudInit.VM_STATIC_CIDR,
            None
        )
        self.environment.setdefault(
            ohostedcons.CloudInit.VM_DNS,
            None
        )
        self.environment.setdefault(
            ohostedcons.CloudInit.VM_ETC_HOSTS,
            None
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.AUTOMATE_VM_SHUTDOWN,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        self.command.detect('genisoimage')
        self._hostname_helper = osetuphostname.Hostname(plugin=self)
        self.command.detect('ping')

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_VM,
            ohostedcons.Stages.CONFIG_OVF_IMPORT,
            ohostedcons.Stages.UPGRADE_CHECK_UPGRADE_REQUIREMENTS,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_VM,
        ),
        condition=lambda self: (
            self.environment[ohostedcons.VMEnv.CDROM] is None and
            not self.environment[ohostedcons.CoreEnv.ROLLBACK_UPGRADE]
        ),
        name=ohostedcons.Stages.CONFIG_CLOUD_INIT_OPTIONS,
    )
    def _customization(self):
        if self.environment[
            ohostedcons.CloudInit.GENERATE_ISO
        ] is None:
            if self.dialog.queryString(
                name='CLOUD_INIT_USE',
                note=_(
                    'Would you like to use cloud-init to customize the '
                    'appliance on the first boot '
                    '(@VALUES@)[@DEFAULT@]? '
                ),
                prompt=True,
                validValues=(_('Yes'), _('No')),
                caseSensitive=False,
                default=_('Yes')
            ) == _('Yes').lower():
                if self.dialog.queryString(
                    name='CLOUD_INIT_GENERATE',
                    note=_(
                        'Would you like to generate on-fly a cloud-init '
                        'ISO image (of no-cloud type)\n'
                        'or do you have an existing one '
                        '(@VALUES@)[@DEFAULT@]? '
                    ),
                    prompt=True,
                    validValues=(_('Generate'), _('Existing')),
                    caseSensitive=False,
                    default=_('Generate')
                ) == _('Generate').lower():
                    self.environment[
                        ohostedcons.CloudInit.GENERATE_ISO
                    ] = ohostedcons.Const.CLOUD_INIT_GENERATE
                else:
                    self.environment[
                        ohostedcons.CloudInit.GENERATE_ISO
                    ] = ohostedcons.Const.CLOUD_INIT_EXISTING
            else:
                self.environment[
                    ohostedcons.CloudInit.GENERATE_ISO
                ] = ohostedcons.Const.CLOUD_INIT_SKIP

        if self.environment[
            ohostedcons.CloudInit.GENERATE_ISO
        ] == ohostedcons.Const.CLOUD_INIT_GENERATE:
            if not self.environment[
                ohostedcons.CloudInit.INSTANCE_HOSTNAME
            ]:
                instancehname = self._hostname_helper.getHostname(
                    envkey=None,
                    whichhost='CI_INSTANCE_HOSTNAME',
                    supply_default=False,
                    prompttext=_(
                        'Please provide the FQDN you would like to use for '
                        'the engine appliance.\n'
                        'Note: This will be the FQDN of the engine VM '
                        'you are now going to launch,\nit should not '
                        'point to the base host or to any other '
                        'existing machine.\n'
                        'Engine VM FQDN: (leave it empty to skip): '
                    ),
                    dialog_name='CI_INSTANCE_HOSTNAME',
                    validate_syntax=True,
                    system=True,
                    dns=False,
                    local_non_loopback=False,
                    reverse_dns=False,
                    not_local=True,
                    not_local_text=_(
                        'Please input the hostname for the engine VM, '
                        'not for this host.'
                    ),
                    allow_empty=True,
                )
                if instancehname:
                    self.environment[
                        ohostedcons.CloudInit.INSTANCE_HOSTNAME
                    ] = instancehname
                else:
                    self.environment[
                        ohostedcons.CloudInit.INSTANCE_HOSTNAME
                    ] = False

            if not self.environment[
                ohostedcons.CloudInit.EXECUTE_ESETUP
            ]:
                self.environment[
                    ohostedcons.CloudInit.EXECUTE_ESETUP
                ] = self.dialog.queryString(
                    name='CI_EXECUTE_ESETUP',
                    note=_(
                        'Automatically execute '
                        'engine-setup on the engine appliance on first boot '
                        '(@VALUES@)[@DEFAULT@]? '
                    ),
                    prompt=True,
                    validValues=(_('Yes'), _('No')),
                    caseSensitive=False,
                    default=_('Yes')
                ) == _('Yes').lower()

        if self.environment[
            ohostedcons.CloudInit.EXECUTE_ESETUP
        ] and self.environment[
            ohostedcons.EngineEnv.HOST_CLUSTER_NAME
        ] is None:
            self.environment[
                ohostedcons.EngineEnv.HOST_CLUSTER_NAME
            ] = 'Default'

        if self.environment[
            ohostedcons.CloudInit.EXECUTE_ESETUP
        ] and self.environment[
            ohostedcons.VMEnv.AUTOMATE_VM_SHUTDOWN
        ] is None:
            self.environment[
                ohostedcons.VMEnv.AUTOMATE_VM_SHUTDOWN
            ] = self.dialog.queryString(
                name='AUTOMATE_VM_SHUTDOWN',
                note=_(
                    'Automatically restart the engine VM '
                    'as a monitored service after engine-setup '
                    '(@VALUES@)[@DEFAULT@]? '
                ),
                prompt=True,
                validValues=(_('Yes'), _('No')),
                caseSensitive=False,
                default=_('Yes')
            ) == _('Yes').lower()

        if (
            self.environment[
                ohostedcons.CloudInit.INSTANCE_HOSTNAME
            ] and
            self.environment[
                ohostedcons.CloudInit.INSTANCE_DOMAINNAME
            ] is None
        ):
            default_domain = ''
            if '.' in self.environment[
                ohostedcons.CloudInit.INSTANCE_HOSTNAME
            ]:
                default_domain = self.environment[
                    ohostedcons.CloudInit.INSTANCE_HOSTNAME
                ].split('.', 1)[1]
            self.environment[
                ohostedcons.CloudInit.INSTANCE_DOMAINNAME
            ] = self.dialog.queryString(
                name='CI_INSTANCE_DOMAINNAME',
                note=_(
                    'Please provide the domain name you would like to use for '
                    'the engine appliance.\n'
                    'Engine VM domain: [@DEFAULT@]'
                ),
                prompt=True,
                default=default_domain,
            )

        if (
            self.environment[
                ohostedcons.CloudInit.INSTANCE_HOSTNAME
            ] or
            self.environment[
                ohostedcons.CloudInit.EXECUTE_ESETUP
            ] or
            self.environment[
                ohostedcons.CloudInit.VM_STATIC_CIDR
            ] or
            self.environment[
                ohostedcons.CloudInit.VM_DNS
            ]
        ):
            self.environment[
                ohostedcons.CloudInit.GENERATE_ISO
            ] = ohostedcons.Const.CLOUD_INIT_GENERATE
            self._enable = True

        if self.environment[
            ohostedcons.CloudInit.GENERATE_ISO
        ] == ohostedcons.Const.CLOUD_INIT_GENERATE:
            while self.environment[
                ohostedcons.CloudInit.ROOTPWD
            ] is None:
                password = self.dialog.queryString(
                    name='CI_ROOT_PASSWORD',
                    note=_(
                        "Enter root password that "
                        'will be used for the engine appliance '
                        '(leave it empty to skip): '
                    ),
                    prompt=True,
                    hidden=True,
                    default='',
                ).strip()
                if password:
                    password_check = self.dialog.queryString(
                        name='CI_ROOT_PASSWORD',
                        note=_(
                            "Confirm appliance root password: "
                        ),
                        prompt=True,
                        hidden=True,
                    )
                    if password == password_check:
                        self.environment[
                            ohostedcons.CloudInit.ROOTPWD
                        ] = password
                    else:
                        self.logger.error(_('Passwords do not match'))
                else:
                    self.environment[ohostedcons.CloudInit.ROOTPWD] = ''
                    self.logger.info(_('Skipping appliance root password'))

        if (
            self.environment[
                ohostedcons.CloudInit.GENERATE_ISO
            ] != ohostedcons.Const.CLOUD_INIT_GENERATE or
            not self.environment[
                ohostedcons.CloudInit.ROOTPWD
            ] or self.environment[
                ohostedcons.CloudInit.ROOTPWD
            ].strip() == ''
        ):
            self.logger.warning(_(
                'The oVirt engine appliance is not configured with a '
                'default password, please consider configuring it '
                'via cloud-init'
            ))

    # TODO: ask about synchronizing with the host timezone

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_VM,
            ohostedcons.Stages.CONFIG_CLOUD_INIT_OPTIONS,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_VM,
        ),
        condition=lambda self: self._enable,
        name=ohostedcons.Stages.CONFIG_CLOUD_INIT_VM_NETWORKING,
    )
    def _customize_vm_networking(self):
        self._customize_vm_addressing()
        self._customize_vm_dns()

        if self.environment[
            ohostedcons.CloudInit.VM_ETC_HOSTS
        ] is None:
            self.environment[
                ohostedcons.CloudInit.VM_ETC_HOSTS
            ] = self.dialog.queryString(
                name='CI_VM_ETC_HOST',
                note=_(
                    'Add lines for the appliance itself and for this host '
                    'to /etc/hosts on the engine VM?\n'
                    'Note: ensuring that this host could resolve the '
                    'engine VM hostname is still up to you\n'
                    '(@VALUES@)[@DEFAULT@] '
                ),
                prompt=True,
                validValues=(_('Yes'), _('No')),
                caseSensitive=False,
                default=_('No')
            ) == _('Yes').lower()
        if (
            self.environment[
                ohostedcons.CloudInit.VM_ETC_HOSTS
            ] and self.environment[
                ohostedcons.CoreEnv.UPGRADING_APPLIANCE
            ]
        ):
            self.logger.warning(_(
                'Please take care that this will simply add an entry for this '
                'host under /etc/hosts on the engine VM. '
                'If in the past you added other entries there, recovering '
                'them is up to you.'
            ))

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        condition=lambda self: self._enable,
    )
    def _misc(self):
        # TODO: find a way to properly get this at runtime
        # see: https://bugzilla.redhat.com/1228215
        _interface_name = 'eth0'

        self._directory_name = tempfile.mkdtemp()
        user_data = (
            '#cloud-config\n'
            '# vim: syntax=yaml\n'
        )
        f_user_data = os.path.join(self._directory_name, 'user-data')
        if self.environment[ohostedcons.CloudInit.ROOTPWD]:
            # TODO: use salted hashed password
            user_data += (
                'ssh_pwauth: True\n'
                'chpasswd:\n'
                '  list: |\n'
                '    root:{password}\n'
                '  expire: False\n'
            ).format(
                password=self.environment[
                    ohostedcons.CloudInit.ROOTPWD
                ],
            )

        if (
            self.environment[
                ohostedcons.CloudInit.VM_ETC_HOSTS
            ] or
            self.environment[
                ohostedcons.CloudInit.VM_STATIC_CIDR
            ]
        ):
            user_data += (
                'bootcmd:\n'
            )

            if self.environment[
                ohostedcons.CloudInit.VM_ETC_HOSTS
            ]:
                user_data += (
                    ' - echo "{myip} {myfqdn}" >> /etc/hosts\n'
                ).format(
                    myip=self._getMyIPAddress().ip,
                    myfqdn=self.environment[
                        ohostedcons.NetworkEnv.HOST_NAME
                    ],
                )
                if self.environment[
                    ohostedcons.CloudInit.VM_STATIC_CIDR
                ] and self.environment[
                    ohostedcons.CloudInit.INSTANCE_HOSTNAME
                ]:
                    ip = netaddr.IPNetwork(
                        self.environment[ohostedcons.CloudInit.VM_STATIC_CIDR]
                    )
                    user_data += (
                        ' - echo "{ip} {fqdn}" >> /etc/hosts\n'
                    ).format(
                        ip=ip.ip,
                        fqdn=self.environment[
                            ohostedcons.CloudInit.INSTANCE_HOSTNAME
                        ],
                    )

            # Due to a cloud-init bug
            # (https://bugs.launchpad.net/cloud-init/+bug/1225922)
            # we have to deactivate and reactive the interface just after
            # the boot on static IP configurations
            if self.environment[
                ohostedcons.CloudInit.VM_STATIC_CIDR
            ]:

                if self.environment[ohostedcons.CloudInit.VM_DNS]:
                    fname = (
                        '/etc/sysconfig/network-scripts/ifcfg-{iname}'.format(
                            iname=_interface_name
                        )
                    )
                    dnslist = [
                        d.strip()
                        for d
                        in self.environment[
                            ohostedcons.CloudInit.VM_DNS
                        ].split(',')
                    ]
                    dn = 1
                    for dns in dnslist:
                        user_data += ' - echo "DNS{dn}={dns}" >> {f}\n'.format(
                            dn=dn,
                            dns=dns,
                            f=fname,
                        )
                        dn += 1
                    if self.environment[
                        ohostedcons.CloudInit.INSTANCE_DOMAINNAME
                    ]:
                        user_data += ' - echo "DOMAIN={d}" >> {f}\n'.format(
                            d=self.environment[
                                ohostedcons.CloudInit.INSTANCE_DOMAINNAME
                            ],
                            f=fname,
                        )
                user_data += (
                    ' - ifdown {iname}\n'
                    ' - ifup {iname}\n'
                ).format(iname=_interface_name)

        if self.environment[ohostedcons.CloudInit.EXECUTE_ESETUP]:
            org = 'Test'
            if '.' in self.environment[
                ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
            ]:
                org = self.environment[
                    ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
                ].split('.', 1)[1]

            engine_restore = ''
            adminPwd = (
                '     OVESETUP_CONFIG/adminPassword=str:{password}\n'
            ).format(
                password=self.environment[
                    ohostedcons.EngineEnv.ADMIN_PASSWORD
                ],
            )
            if self.environment[
                ohostedcons.CoreEnv.UPGRADING_APPLIANCE
            ]:
                engine_restore = (
                    ' - engine-backup --mode=restore --file={backup_file}'
                    ' --log=engine_restore.log --restore-permissions'
                    ' --provision-db {p_dwh_db} {p_reports_db}'
                    ' 1>{port}'
                    ' 2>&1\n'
                    ' - if [ $? -eq 0 ];'
                    ' then echo "{success_string}" >{port};'
                    ' else echo "{fail_string}" >{port};'
                    ' fi\n'
                ).format(
                    backup_file=self.environment[
                        ohostedcons.Upgrade.BACKUP_FILE
                    ],
                    p_dwh_db='--provision-dwh-db' if self.environment[
                        ohostedcons.Upgrade.RESTORE_DWH
                    ] else '',
                    p_reports_db='--provision-reports-db' if self.environment[
                        ohostedcons.Upgrade.RESTORE_REPORTS
                    ] else '',
                    port=(
                        ohostedcons.Const.VIRTIO_PORTS_PATH +
                        ohostedcons.Const.OVIRT_HE_CHANNEL_NAME
                    ),
                    success_string=ohostedcons.Const.E_RESTORE_SUCCESS_STRING,
                    fail_string=ohostedcons.Const.E_RESTORE_FAIL_STRING,
                )
                adminPwd = ''
            self.logger.debug('engine_restore: {er}'.format(er=engine_restore))

            user_data += (
                'write_files:\n'
                ' - content: |\n'
                '     [environment:init]\n'
                '     DIALOG/autoAcceptDefault=bool:True\n'
                '     [environment:default]\n'
                '{adminPwd}'
                '     OVESETUP_CONFIG/fqdn=str:{fqdn}\n'
                '     OVESETUP_PKI/organization=str:{org}\n'
                '   path: {heanswers}\n'
                '   owner: root:root\n'
                '   permissions: \'0640\'\n'
                'runcmd:\n'
                '{engine_restore}'
                ' - /usr/bin/engine-setup --offline'
                ' --config-append={applianceanswers}'
                ' --config-append={heanswers}'
                ' 1>{port}'
                ' 2>&1\n'
                ' - if [ $? -eq 0 ];'
                ' then echo "{success_string}" >{port};'
                ' else echo "{fail_string}" >{port};'
                ' fi\n'
                ' - rm {heanswers}\n'
            ).format(
                fqdn=self.environment[
                    ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
                ],
                org=org,
                adminPwd=adminPwd,
                applianceanswers=ohostedcons.Const.CLOUD_INIT_APPLIANCEANSWERS,
                heanswers=ohostedcons.Const.CLOUD_INIT_HEANSWERS,
                port=(
                    ohostedcons.Const.VIRTIO_PORTS_PATH +
                    ohostedcons.Const.OVIRT_HE_CHANNEL_NAME
                ),
                success_string=ohostedcons.Const.E_SETUP_SUCCESS_STRING,
                fail_string=ohostedcons.Const.E_SETUP_FAIL_STRING,
                engine_restore=engine_restore,
            )

        if 'runcmd:\n' not in user_data:
            user_data += 'runcmd:\n'
        user_data += (
            ' - systemctl mask cloud-init-local || '
            ' chkconfig cloud-init-local off\n'
            ' - systemctl mask cloud-init || ('
            ' chkconfig cloud-init off &&'
            ' chkconfig cloud-config off &&'
            ' chkconfig cloud-final off'
            ' )\n'
        )

        f = open(f_user_data, 'w')
        f.write(user_data)
        f.close()

        meta_data = 'instance-id: {instance}\n'.format(
            instance=self.environment[ohostedcons.VMEnv.VM_UUID],
        )
        f_meta_data = os.path.join(self._directory_name, 'meta-data')
        if self.environment[ohostedcons.CloudInit.INSTANCE_HOSTNAME]:
            meta_data += (
                'local-hostname: {hostname}\n'
            ).format(
                instance=self.environment[
                    ohostedcons.VMEnv.VM_UUID
                ],
                hostname=self.environment[
                    ohostedcons.CloudInit.INSTANCE_HOSTNAME
                ],
            )

        if self.environment[ohostedcons.CloudInit.VM_STATIC_CIDR]:
            ip = netaddr.IPNetwork(
                self.environment[ohostedcons.CloudInit.VM_STATIC_CIDR]
            )
            meta_data += (
                'network-interfaces: |\n'
                '  auto {iname}\n'
                '  iface {iname} inet static\n'
                '    address {ip_addr}\n'
                '    network {network}\n'
                '    netmask {netmask}\n'
                '    broadcast {broadcast}\n'
                '    gateway {gateway}\n'
            ).format(
                ip_addr=ip.ip,
                network=ip.network,
                netmask=ip.netmask,
                broadcast=ip.broadcast,
                gateway=self.environment[
                    ohostedcons.NetworkEnv.GATEWAY
                ],
                iname=_interface_name,
            )

        f = open(f_meta_data, 'w')
        f.write(meta_data)
        f.close()

        f_cloud_init_iso = os.path.join(self._directory_name, 'seed.iso')
        rc, stdout, stderr = self.execute(
            (
                self.command.get('genisoimage'),
                '-output',
                f_cloud_init_iso,
                '-volid',
                'cidata',
                '-joliet',
                '-rock',
                '-input-charset',
                'utf-8',
                f_meta_data,
                f_user_data,
            )
        )
        if rc != 0:
            raise RuntimeError(_('Error generating cloud-init ISO image'))
        os.unlink(f_meta_data)
        os.unlink(f_user_data)
        self.environment[ohostedcons.VMEnv.CDROM] = f_cloud_init_iso
        os.chown(
            self._directory_name,
            pwd.getpwnam('qemu').pw_uid,
            pwd.getpwnam('qemu').pw_uid,
        )
        os.chmod(f_cloud_init_iso, 0o600)
        os.chown(
            f_cloud_init_iso,
            pwd.getpwnam('qemu').pw_uid,
            pwd.getpwnam('qemu').pw_uid,
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CLEANUP,
        condition=lambda self: self._enable,
    )
    def _cleanup(self):
        if self._directory_name is not None:
            shutil.rmtree(self._directory_name)
        self.environment[ohostedcons.VMEnv.CDROM] = None


# vim: expandtab tabstop=4 shiftwidth=4
