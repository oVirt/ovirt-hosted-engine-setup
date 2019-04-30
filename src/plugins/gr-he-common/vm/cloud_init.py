#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2015-2017 Red Hat, Inc.
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


import ethtool
import gettext
import netaddr
import os
import re
import tempfile

from otopi import constants as otopicons
from otopi import plugin
from otopi import util

from ovirt_setup_lib import dialog
from ovirt_setup_lib import hostname as osetuphostname

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import util as ohostedutil


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

    IPv4RE = re.compile(
        pattern=r'^\s+inet\s+(?P<addr>[\d.]*)/(?P<len>\d+)\s',
        flags=re.M,
    )

    IPv6RE = re.compile(
        pattern=r'^\s+inet6\s+(?P<addr>[\d:A-F]*)/(?P<len>\d+)\s',
        flags=re.M | re.I,
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

    def _getMyIPAddrList(self):
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
        alist = []

        addressmatchs4list = re.findall(self.IPv4RE, '\n'.join(stdout))
        addressmatchs6list = re.findall(self.IPv6RE, '\n'.join(stdout))

        for amatch in (addressmatchs4list + addressmatchs6list):
            addr = '{a}/{pl}'.format(
                a=amatch[0],
                pl=amatch[1],
            )
            self.logger.debug('address: {a}'.format(a=addr))
            try:
                ipna = netaddr.IPNetwork(addr)
                alist.append(ipna)
            except netaddr.AddrFormatError:
                self.logger.error(
                    _('Invalid nic/bridge address: {a}').format(a=addr)
                )
        if not alist:
            raise RuntimeError(
                _('Cannot acquire nic/bridge address')
            )

        return alist

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
        my_ip = self._getMyIPAddrList()[0]
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
                    default_ip = ''
                    if not netaddr.IPAddress(my_ip).ipv6():
                        default_ip = str(
                            self._getFreeIPAddress(my_ip)
                        )
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
                    proposed_cidr = '{a}/{pl}'.format(
                        a=proposed_ip,
                        pl=my_ip.prefixlen,
                    )
                else:
                    proposed_cidr = self.environment[
                        ohostedcons.CloudInit.VM_STATIC_CIDR
                    ]
                    if '/' not in proposed_cidr:
                        # Answer file contains an IP address without a CIDR
                        # prefix. This should not happen with answerfiles
                        # generated by ovirt-hosted-engine-setup, but does
                        # happen with current cockpit plugin, and we decided
                        # to fix here.
                        proposed_cidr = '{a}/{pl}'.format(
                            a=proposed_ip,
                            pl=my_ip.prefixlen,
                        )
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

    def _get_host_tz(self):
        self.logger.info(_('Detecting host timezone.'))
        tz = ''
        try:
            if os.path.islink(ohostedcons.FileLocations.LOCALTIME):
                tz = os.path.relpath(
                    os.path.realpath(ohostedcons.FileLocations.LOCALTIME),
                    ohostedcons.FileLocations.TZ_PARENT_DIR
                )
            else:
                self.logger.warning(_(
                    '{fname} is not a symlink to a timezone definition.'
                ).format(
                    fname=ohostedcons.FileLocations.LOCALTIME,
                ))
        except OSError:
            pass
        if not tz:
            self.logger.warning(_(
                'Unable to detect host timezone. '
                'Engine VM timezone will be set to UTC. '
            ))
        return tz

    @plugin.event(
        stage=plugin.Stages.STAGE_BOOT,
        before=(
            otopicons.Stages.CORE_LOG_INIT,
        )
    )
    def _boot(self):
        self.environment[otopicons.CoreEnv.LOG_FILTER_KEYS].append(
            ohostedcons.CloudInit.ROOTPWD
        )

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
        self.environment.setdefault(
            ohostedcons.CloudInit.ROOT_SSH_PUBKEY,
            None
        )
        self.environment.setdefault(
            ohostedcons.CloudInit.ROOT_SSH_ACCESS,
            None
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
            ohostedcons.CloudInit.VM_TZ,
            None
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.AUTOMATE_VM_SHUTDOWN,
            None
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.ENABLE_LIBGFAPI,
            None
        )
        self.environment.setdefault(
            ohostedcons.CloudInit.APPLY_OPENSCAP_PROFILE,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        self.command.detect('genisoimage')
        self.command.detect('ssh-keygen')
        self._hostname_helper = osetuphostname.Hostname(plugin=self)
        self.command.detect('ping')

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_VM,
            ohostedcons.Stages.CONFIG_OVF_IMPORT,
            ohostedcons.Stages.UPGRADE_CHECK_UPGRADE_VERSIONS,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_VM,
        ),
        condition=lambda self: (
            self.environment[ohostedcons.VMEnv.CDROM] is None
        ),
        name=ohostedcons.Stages.CONFIG_CLOUD_INIT_OPTIONS,
    )
    def _customization(self):
        if self.environment[
            ohostedcons.CloudInit.VM_TZ
        ] is None:
            self.environment[ohostedcons.CloudInit.VM_TZ] = self._get_host_tz()

        self.environment[
            ohostedcons.CloudInit.GENERATE_ISO
        ] = ohostedcons.Const.CLOUD_INIT_GENERATE
        self.environment[
            ohostedcons.VMEnv.AUTOMATE_VM_SHUTDOWN
        ] = True
        self.environment[
            ohostedcons.CloudInit.EXECUTE_ESETUP
        ] = True

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
                        'the engine.\n'
                        'Note: This will be the FQDN of the engine VM '
                        'you are now going to launch,\nit should not '
                        'point to the base host or to any other '
                        'existing machine.\n'
                        'Engine VM FQDN: '
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
                    allow_empty=False,
                )
                if instancehname:
                    self.environment[
                        ohostedcons.CloudInit.INSTANCE_HOSTNAME
                    ] = instancehname
                else:
                    self.environment[
                        ohostedcons.CloudInit.INSTANCE_HOSTNAME
                    ] = False

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
                        'Please provide the domain name you would like to '
                        'use for the engine appliance.\n'
                        'Engine VM domain: [@DEFAULT@]'
                    ),
                    prompt=True,
                    default=default_domain,
                )

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
            ] = ohostedcons.Defaults.DEFAULT_CLUSTER_NAME

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
                        'Enter root password that '
                        'will be used for the engine appliance: '
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
                    self.logger.error(_('Password is empty'))

            while self.environment[
                ohostedcons.CloudInit.ROOT_SSH_PUBKEY
            ] is None:
                pubkey = self.dialog.queryString(
                    name='CI_ROOT_SSH_PUBKEY',
                    note=_(
                        "Enter ssh public key for the root user that "
                        'will be used for the engine appliance '
                        '(leave it empty to skip): '
                    ),
                    prompt=True,
                    hidden=False,
                    default='',
                ).strip()
                if pubkey:
                    fd, pkfilename = tempfile.mkstemp(suffix='pub')
                    pkfile = os.fdopen(fd, 'w')
                    try:
                        pkfile.write(pubkey)
                    finally:
                        pkfile.close()
                    rc, stdout, stderr = self.execute(
                        (
                            self.command.get('ssh-keygen'),
                            '-lf',
                            pkfilename,
                        ),
                        raiseOnError=False,
                    )
                    os.unlink(pkfilename)
                    if rc != 0:
                        self.logger.error(_(
                            'The ssh key is not valid.'
                        ))
                    else:
                        self.environment[
                            ohostedcons.CloudInit.ROOT_SSH_PUBKEY
                        ] = pubkey
                else:
                    self.environment[
                        ohostedcons.CloudInit.ROOT_SSH_PUBKEY
                    ] = ''
                    self.logger.warning(_(
                        'Skipping appliance root ssh public key'
                    ))

            vv_root_a = (
                'yes',
                'no',
                'without-password',
            )
            dialog.queryEnvKey(
                dialog=self.dialog,
                logger=self.logger,
                env=self.environment,
                key=ohostedcons.CloudInit.ROOT_SSH_ACCESS,
                name='CI_ROOT_SSH_ACCESS',
                note=_(
                    'Do you want to enable ssh access for the root user '
                    '(@VALUES@) [@DEFAULT@]: '
                ),
                prompt=True,
                hidden=False,
                default=vv_root_a[0],
                store=True,
                validValues=vv_root_a,
                caseSensitive=False,
            )

            if self.environment[
                ohostedcons.CloudInit.APPLY_OPENSCAP_PROFILE
            ] is None:
                self.environment[
                    ohostedcons.CloudInit.APPLY_OPENSCAP_PROFILE
                ] = self.dialog.queryString(
                    name='CI_APPLY_OPENSCAP_PROFILE',
                    note=_(
                        'Do you want to apply a default OpenSCAP security '
                        'profile (@VALUES@) [@DEFAULT@]: '
                    ),
                    prompt=True,
                    validValues=(_('Yes'), _('No')),
                    caseSensitive=False,
                    default=_('No')
                ) == _('Yes').lower()

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

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_VM,
            ohostedcons.Stages.CONFIG_CLOUD_INIT_OPTIONS,
            ohostedcons.Stages.CUSTOMIZATION_MAC_ADDRESS,
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


# vim: expandtab tabstop=4 shiftwidth=4
