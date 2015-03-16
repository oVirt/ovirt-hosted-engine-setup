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


"""FQDN plugin."""


import gettext
import re
import socket


from otopi import plugin
from otopi import util


from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """Misc plugin."""

    _IPADDR_RE = re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')

    _DOMAIN_RE = re.compile(
        flags=re.VERBOSE,
        pattern=r"""
            ^
            [\w\.\-\_]+
            \w+
            $
        """
    )

    _DIG_LOOKUP_RE = re.compile(
        flags=re.VERBOSE,
        pattern=r"""
            ^
            [\w.-]+
            \s+
            \d+
            \s+
            IN
            \s+
            (A|CNAME)
            \s+
            [\w.-]+
        """
    )

    _DIG_REVLOOKUP_RE = re.compile(
        flags=re.VERBOSE,
        pattern=r"""
            ^
            (?P<query>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).in-addr.arpa.
            \s+
            \d+
            \s+
            IN
            \s+
            PTR
            \s+
            (?P<answer>[\w.-]+)
            \.
            $
        """
    )

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    def _validateFQDN(self, fqdn):
        if self._IPADDR_RE.match(fqdn):
            raise RuntimeError(
                _(
                    '{fqdn} is an IP address and not a FQDN. '
                    'A FQDN is needed to be able to generate '
                    'certificates correctly.'
                ).format(
                    fqdn=fqdn,
                )
            )

        if not fqdn:
            raise RuntimeError(
                _('Please specify host FQDN')
            )

        if len(fqdn) > 1000:
            raise RuntimeError(
                _('FQDN has invalid length')
            )

        components = fqdn.split('.', 1)
        if len(components) == 1 or not components[0]:
            self.logger.warning(
                _('Host name {fqdn} has no domain suffix').format(
                    fqdn=fqdn,
                )
            )
        else:
            if not self._DOMAIN_RE.match(components[1]):
                raise RuntimeError(
                    _('Host name {fqdn} has invalid domain name').format(
                        fqdn=fqdn,
                    )
                )

    def _validateFQDNresolvability(self, fqdn):
        try:
            resolvedAddresses = set([
                address[0] for __, __, __, __, address in
                socket.getaddrinfo(
                    fqdn,
                    None
                )
            ])
            self.logger.debug(
                '{fqdn} resolves to: {addresses}'.format(
                    fqdn=fqdn,
                    addresses=resolvedAddresses,
                )
            )
            resolvedAddressesAsString = ' '.join(resolvedAddresses)
        except socket.error:
            raise RuntimeError(
                _('{fqdn} did not resolve into an IP address').format(
                    fqdn=fqdn,
                )
            )

        resolvedByDNS = self._resolvedByDNS(fqdn)
        if not resolvedByDNS:
            self.logger.warning(
                _(
                    'Failed to resolve {fqdn} using DNS, '
                    'it can be resolved only locally'
                ).format(
                    fqdn=fqdn,
                )
            )
        elif self.environment[ohostedcons.NetworkEnv.FQDN_REVERSE_VALIDATION]:
            revResolved = False
            for address in resolvedAddresses:
                for name in self._dig_reverse_lookup(address):
                    revResolved = name.lower() == fqdn.lower()
                    if revResolved:
                        break
                if revResolved:
                    break
            if not revResolved:
                raise RuntimeError(
                    _(
                        'The following addresses: {addresses} did not reverse'
                        'resolve into {fqdn}'
                    ).format(
                        addresses=resolvedAddressesAsString,
                        fqdn=fqdn
                    )
                )

    def _resolvedByDNS(self, fqdn):
        args = (
            self.command.get('dig'),
            fqdn,
        )
        rc, stdout, stderr = self.execute(
            args=args,
            raiseOnError=False
        )
        resolved = False
        if rc == 0:
            for line in stdout:
                if self._DIG_LOOKUP_RE.search(line):
                    resolved = True
        return resolved

    def _dig_reverse_lookup(self, addr):
        names = set()
        args = (
            self.command.get('dig'),
            '-x',
            addr,
        )
        rc, stdout, stderr = self.execute(
            args=args,
            raiseOnError=False
        )
        if rc == 0:
            for line in stdout:
                found = self._DIG_REVLOOKUP_RE.search(line)
                if found:
                    names.add(found.group('answer'))
        return names

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN,
            None
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.FQDN_REVERSE_VALIDATION,
            False
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        # Can't use python api here, it will call sys.exit
        self.command.detect('dig')

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
        if (
            self.environment[
                ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
            ] is None and
            self.environment[
                ohostedcons.VMEnv.CLOUD_INIT_INSTANCE_HOSTNAME
            ] is not None
        ):
            self.environment[
                ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
            ] = self.environment[
                ohostedcons.VMEnv.CLOUD_INIT_INSTANCE_HOSTNAME
            ]

        interactive = self.environment[
            ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
        ] is None
        valid = False
        while not valid:
            if interactive:
                self.environment[
                    ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
                ] = self.dialog.queryString(
                    name='OVEHOSTED_NETWORK_FQDN',
                    note=_(
                        'Please provide the FQDN for the engine '
                        'you would like to use.\nThis needs to match '
                        'the FQDN that you will use for the engine '
                        'installation within the VM.\n'
                        'Note: This will be the FQDN of the VM '
                        'you are now going to create,\nit should not '
                        'point to the base host or to any other '
                        'existing machine.\nEngine FQDN: '
                    ),
                    prompt=True,
                    caseSensitive=True,
                )
            try:
                self._validateFQDN(
                    self.environment[
                        ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
                    ]
                )
                self._validateFQDNresolvability(
                    self.environment[
                        ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
                    ]
                )
                valid = True
            except RuntimeError as e:
                self.logger.debug('exception', exc_info=True)
                if interactive:
                    self.logger.error(
                        _('Host name is not valid: {error}').format(
                            error=e,
                        ),
                    )
                else:
                    raise RuntimeError(
                        _('Host name is not valid: {error}').format(
                            error=e,
                        ),
                    )

    @plugin.event(
        stage=plugin.Stages.STAGE_VALIDATION,
    )
    def _validation(self):
        self._validateFQDN(socket.gethostname())
        self._validateFQDNresolvability(socket.gethostname())

# vim: expandtab tabstop=4 shiftwidth=4
