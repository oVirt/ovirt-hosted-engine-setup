#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2015 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


"""oVirt setup PKI/SSH Handler."""
# TODO: move to engine-lib for 4.0
# TODO: Use in engine:packaging/setup/plugins/ovirt-engine-setup/
# ovirt-engine/all-in-one/sshd.py, perhaps other places

import gettext
import os
import re
import ssl
import urllib2

from otopi import base

from M2Crypto import X509

from . import ohttpshandler


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-setup-lib')


class PKIHelper(base.Base):

    _FORMAT_X509_PEM = 'X509-PEM-CA'
    _FORMAT_OPENSSH = 'OPENSSH-PUBKEY'
    _RESOURCE_CA = 'ca-certificate'
    _RESOURCE_ENGINE = 'engine-certificate'
    _PKI_RESOURCE_SERVLET_PATH_TEMPATE = (
        '/ovirt-engine/services/pki-resource?'
        'resource={resource}&format={format}'
    )
    _CA_PEM_CERT_PATH = _PKI_RESOURCE_SERVLET_PATH_TEMPATE.format(
        resource=_RESOURCE_CA,
        format=_FORMAT_X509_PEM,
    )
    _ENGINE_SSH_CERT_PATH = _PKI_RESOURCE_SERVLET_PATH_TEMPATE.format(
        resource=_RESOURCE_ENGINE,
        format=_FORMAT_OPENSSH,
    )
    _URL_TEMPLATE = 'https://{fqdn}{path}'
    _RE_SSHPUB = re.compile(
        flags=re.VERBOSE,
        pattern=r"""
            ^
            \s*
            ssh-(?P<algo>rsa|dss)
            \s+
            (?P<public>[A-Za-z0-9+/]+={0,2})
            (?P<alias>\s+[^\s]+)?
            \s*
            $
        """
    )

    def __init__(self):
        super(PKIHelper, self).__init__()

    def getPKICert(self, fqdn, customcafname=None):
        if customcafname:
            self.logger.info(
                'Reading custom CA cert from {fname}'.format(
                    fname=customcafname,
                )
            )
            try:
                with open(customcafname) as f:
                    content = f.read()
            except EnvironmentError:
                raise RuntimeError(
                    _('Unable to read CA cert from {fname}').format(
                        fname=customcafname,
                    )
                )
        else:
            self.logger.info('Acquiring internal CA cert from the engine')
            he_https_handler = ohttpshandler.OVHTTPSHandler()
            code, info, content = he_https_handler.fetchUrl(
                url=self._URL_TEMPLATE.format(
                    fqdn=fqdn,
                    path=self._CA_PEM_CERT_PATH,
                ),
            )
        if not content:
            raise RuntimeError(_('Unable to acquire CA cert'))
        try:
            cert = X509.load_cert_string(str(content))
            self.logger.info(_(
                'The following CA certificate is going to be used, '
                'please immediately interrupt if not correct:'
            ))
            self.logger.info(
                _(
                    'Issuer: {issuer}, Subject: {subject}, '
                    'Fingerprint (SHA-1): {fingerprint}'
                ).format(
                    issuer=cert.get_issuer().as_text(),
                    subject=cert.get_subject().as_text(),
                    fingerprint=cert.get_fingerprint(md='sha1'),
                )
            )
        except X509.X509Error as ex:
            self.logger.debug('Cannot parse CA', exc_info=True)
            raise RuntimeError(
                _('The CA certificate is not valid: {ex}').format(ex=ex)
            )
        return content

    def validateCA(self, fqdn, ca_certs):
        he_https_handler = ohttpshandler.OVHTTPSHandler()
        try:
            he_https_handler.fetchUrl(
                url=self._URL_TEMPLATE.format(
                    fqdn=fqdn,
                    path=self._CA_PEM_CERT_PATH,
                ),
                ca_certs=ca_certs,
            )

            return True
        except urllib2.URLError as ex:
            self.logger.debug(ex)
            if isinstance(ex.args[0], ssl.SSLError):
                return False
            else:
                raise ex
        except RuntimeError as ex:
            self.logger.debug(ex)
            return False
        return False

    def getSSHkey(self, fqdn, ca_certs):
        self.logger.debug('Acquiring SSH key from the engine')
        he_https_handler = ohttpshandler.OVHTTPSHandler()
        code, info, authorized_keys_line = he_https_handler.fetchUrl(
            url=self._URL_TEMPLATE.format(
                fqdn=fqdn,
                path=self._ENGINE_SSH_CERT_PATH,
            ),
            ca_certs=ca_certs,
        )
        if not authorized_keys_line:
            raise RuntimeError(_('Unable to fetch SSH pub key'))
        return authorized_keys_line

    def mergeAuthKeysFile(self, authKeysFile, sshKey):
        found = False
        content = []
        current = []
        if not os.path.exists(authKeysFile):
            return sshKey

        with open(authKeysFile, 'r') as f:
            current = f.read().splitlines()

        keymatch = self._RE_SSHPUB.match(sshKey)
        for line in current:
            linematch = self._RE_SSHPUB.match(line)
            if linematch is not None:
                if (
                    (
                        linematch.group('algo'),
                        linematch.group('public'),
                    ) == (
                        keymatch.group('algo'),
                        keymatch.group('public'),
                    )
                ):
                    found = True
            content.append(line)
        if not found:
            content.append(sshKey)
        return content


# vim: expandtab tabstop=4 shiftwidth=4
