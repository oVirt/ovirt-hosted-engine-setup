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


"""oVirt setup HTTPSHandler."""
# TODO: move to engine-lib for 4.0


import contextlib
import gettext
import ssl
import sys

from otopi import base


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-setup-lib')


class OVHTTPSHandler(base.Base):
    def __init__(self):
        super(OVHTTPSHandler, self).__init__()

    def fetchUrl(self, url, ca_certs=None):
        """
        :param url: a string identifying the url to fetch
        :param ca_certs: a string identifying a file with the CA cert to be
        used to trust the remote cert. Pass None to proceed in insecure mode.
        If a CA cert filename is passed, it will try to verify the remote cert
        signature and it will verify that it matches the remote host hostname.
        It handles the differences between python < / >= 2.7.9.

        Returns http exit code, http info and the URL content.
        Raise RuntimeError if something goes wrong.
        """
        self.logger.debug(
            'Downloading from {url} - ca_certs={ca_certs}'.format(
                url=url,
                ca_certs=ca_certs,
            )
        )
        from six.moves.urllib.request import HTTPSHandler
        from six.moves.urllib.request import build_opener

        if getattr(ssl, 'create_default_context', None):
            # new in python 3.4/2.7.9 (backported by Redhat to 2.7.5)
            # TODO: calling context = ssl.create_default_context()
            # will load by default also the system defined CA certs which
            # in general is a good idea but oVirt python SDK will instead
            # ignore them so, until rhbz#1326386 will get fixed, it's better
            # to ignore them also here for coherency reasons.
            if ca_certs:
                context = ssl.create_default_context(cafile=ca_certs)
                context.verify_mode = ssl.CERT_REQUIRED
                context.check_hostname = ssl.match_hostname
            else:
                context = ssl.create_default_context()
                context.check_hostname = None
                context.verify_mode = ssl.CERT_NONE

            https_context = contextlib.closing(
                build_opener(HTTPSHandler(context=context)).open(url)
            )
        else:
            # for compatibility with older python releases
            import socket
            if sys.version_info[0] < 3:
                from httplib import HTTPSConnection
            else:
                from http.client import HTTPSConnection

            class MyHTTPSConnection(HTTPSConnection):
                def __init__(self, host, **kwargs):
                    self._ca_certs = kwargs.pop('ca_certs', None)
                    HTTPSConnection.__init__(self, host, **kwargs)

                def connect(self):
                    self.sock = ssl.wrap_socket(
                        socket.create_connection((self.host, self.port)),
                        cert_reqs=(
                            ssl.CERT_REQUIRED if self._ca_certs
                            else ssl.CERT_NONE
                        ),
                        ca_certs=self._ca_certs,
                    )
                    if self._ca_certs:
                        cert = self.sock.getpeercert()
                        for field in cert.get('subject', []):
                            if field[0][0] == 'commonName':
                                expected = field[0][1]
                                break
                        else:
                            raise RuntimeError(
                                _('No CN in peer certificate')
                            )

                        if expected != self.host:
                            raise RuntimeError(
                                _(
                                    "Invalid host '{host}' "
                                    "expected '{expected}'"
                                ).format(
                                    expected=expected,
                                    host=self.host,
                                )
                            )

            class MyHTTPSHandler(HTTPSHandler):

                def __init__(self, ca_certs=None):
                    HTTPSHandler.__init__(self)
                    self._ca_certs = ca_certs

                def https_open(self, req):
                    return self.do_open(self._get_connection, req)

                def _get_connection(self, host, timeout):
                    return MyHTTPSConnection(
                        host=host,
                        timeout=timeout,
                        ca_certs=self._ca_certs,
                    )

            https_context = contextlib.closing(
                build_opener(MyHTTPSHandler(ca_certs=ca_certs)).open(url)
            )

        with https_context as cont:
            info = {}
            for key, value in cont.info().items():
                info[key] = value
            code = cont.getcode()
            content = cont.read().decode('utf-8', 'replace')
            self.logger.debug('code: %s', code)
            self.logger.debug('info: %s', info)
            self.logger.debug('content: %s', content)
            return code, info, content


# vim: expandtab tabstop=4 shiftwidth=4
