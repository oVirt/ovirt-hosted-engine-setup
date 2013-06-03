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


"""VDSM PKI plugin."""


import gettext
import glob
import os
import shutil
import tempfile


from otopi import util
from otopi import plugin


from ovirt_hosted_engine_setup import constants as ohostedcons


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """VDSM PKI plugin."""

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._tmpdir = None

    def _generateVDSMcerts(self):
        self.logger.info(_('Generating VDSM certificates'))
        rc, stdout, stderr = self.execute(
            [
                ohostedcons.FileLocations.VDSM_GEN_CERTS
            ],
            raiseOnError=True
        )

    def _generateSPICEcerts(self):
        #'https://fedoraproject.org/wiki/
        #QA:Testcase_Virtualization_Manually_
        #set_spice_listening_port_with_TLS_port_set'
        self.logger.info(_('Generating libvirt-spice certificates'))
        self._tmpdir = tempfile.mkdtemp()
        expire = '1095'  # FIXME: configurable?
        subj = self.environment[ohostedcons.VDSMEnv.PKI_SUBJECT]
        # FIXME: configurable?
        for key in ('ca-key.pem', 'server-key.pem'):
            self.execute(
                (
                    self.command.get('openssl'),
                    'genrsa',
                    '-out', os.path.join(self._tmpdir, key),
                    '1024'
                ),
                raiseOnError=True
            )
        self.execute(
            (
                self.command.get('openssl'),
                'req',
                '-new',
                '-x509',
                '-days', expire,
                '-key', os.path.join(self._tmpdir, 'ca-key.pem'),
                '-out', os.path.join(self._tmpdir, 'ca-cert.pem'),
                '-subj', subj
            ),
            raiseOnError=True
        )
        self.execute(
            (
                self.command.get('openssl'),
                'req',
                '-new',
                '-key', os.path.join(self._tmpdir, 'server-key.pem'),
                '-out', os.path.join(self._tmpdir, 'server-key.csr'),
                '-subj', subj
            ),
            raiseOnError=True
        )
        self.execute(
            (
                self.command.get('openssl'),
                'x509',
                '-req',
                '-days', expire,
                '-in', os.path.join(self._tmpdir, 'server-key.csr'),
                '-CA', os.path.join(self._tmpdir, 'ca-cert.pem'),
                '-CAkey', os.path.join(self._tmpdir, 'ca-key.pem'),
                '-set_serial', '01',
                '-out', os.path.join(self._tmpdir, 'server-cert.pem'),
            ),
            raiseOnError=True
        )
        pem_files = glob.glob(os.path.join(self._tmpdir, '*.pem'))
        cert_dir = os.path.dirname(
            ohostedcons.FileLocations.LIBVIRT_SERVER_CERT
        )
        if not os.path.exists(cert_dir):
            os.makedirs(cert_dir)
        for src in pem_files:
            dest = os.path.join(cert_dir, os.path.basename(src))
            shutil.move(src, dest)
            os.chmod(dest, 0o640)
            os.chown(
                dest,
                self.environment[
                    ohostedcons.VDSMEnv.VDSM_UID
                ],
                self.environment[
                    ohostedcons.VDSMEnv.KVM_GID
                ]
            )

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.VDSMEnv.PKI_SUBJECT,
            ohostedcons.Defaults.DEFAULT_PKI_SUBJECT
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        # TODO:
        # remove when we understand how to replace the openssl command
        # with m2crypto code
        self.command.detect('openssl')

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        name=ohostedcons.Stages.VDSMD_PKI,
    )
    def _misc(self):
        if not os.path.exists(ohostedcons.FileLocations.VDSMCERT):
            self._generateVDSMcerts()
        if not os.path.exists(ohostedcons.FileLocations.LIBVIRT_SERVER_CERT):
            self._generateSPICEcerts()

    @plugin.event(
        stage=plugin.Stages.STAGE_CLEANUP,
    )
    def _cleanup(self):
        if self._tmpdir and os.path.exists(self._tmpdir):
            shutil.rmtree(self._tmpdir)


# vim: expandtab tabstop=4 shiftwidth=4
