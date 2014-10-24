#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2013-2014 Red Hat, Inc.
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
import re
import datetime


from otopi import util
from otopi import plugin


from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import util as ohostedutil


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """VDSM PKI plugin."""

    _RE_SUBJECT = re.compile(
        flags=re.VERBOSE,
        pattern=r"""
            ^
            \s+
            Subject:\s*
            (?P<subject>\w+=\w+.*)
            $
        """
    )

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._tmpdir = None

    def _generateVDSMcerts(self):
        self.logger.info(_('Generating VDSM certificates'))
        rc, stdout, stderr = self.execute(
            (
                ohostedcons.FileLocations.VDSM_GEN_CERTS,
            ),
            raiseOnError=True
        )

    def _safecopy(self, s, d):
        self.logger.debug("%s %s" % (s, d))
        suffix = datetime.datetime.now().strftime('%Y%m%d%H%M%S'),
        if os.path.exists(d):
            os.rename(d, "%s.%s" % (d, suffix))
        shutil.copyfile(s, d)

    def _copy_vdsm_pki(self):
        if not os.path.exists(ohostedcons.FileLocations.LIBVIRT_PKI):
            os.makedirs(ohostedcons.FileLocations.LIBVIRT_PKI)
        if not os.path.exists(ohostedcons.FileLocations.LIBVIRT_PKI_PRIVATE):
            os.makedirs(ohostedcons.FileLocations.LIBVIRT_PKI_PRIVATE)
            os.chmod(ohostedcons.FileLocations.LIBVIRT_PKI_PRIVATE, 0o750)
            os.chown(
                ohostedcons.FileLocations.LIBVIRT_PKI_PRIVATE,
                self.environment[
                    ohostedcons.VDSMEnv.VDSM_UID
                ],
                self.environment[
                    ohostedcons.VDSMEnv.KVM_GID
                ]
            )

        for s, d in (
            (ohostedcons.FileLocations.VDSM_CA_CERT,
                ohostedcons.FileLocations.SYS_CA_CERT),
            (ohostedcons.FileLocations.VDSMCERT,
                ohostedcons.FileLocations.LIBVIRT_CLIENT_CERT),
            (ohostedcons.FileLocations.VDSMKEY,
                ohostedcons.FileLocations.LIBVIRT_CLIENT_KEY),
            (ohostedcons.FileLocations.LIBVIRT_CLIENT_CERT,
                ohostedcons.FileLocations.LIBVIRT_SERVER_CERT),
            (ohostedcons.FileLocations.LIBVIRT_CLIENT_KEY,
                ohostedcons.FileLocations.LIBVIRT_SERVER_KEY),
        ):
            self._safecopy(s, d)
            os.chown(d, 0, 0)

        for f in (
            ohostedcons.FileLocations.LIBVIRT_CLIENT_KEY,
            ohostedcons.FileLocations.LIBVIRT_SERVER_KEY,
        ):
            os.chmod(f, 0o600)

    def _getSPICEcerts(self):
        subject = None
        rc, stdout, stderr = self.execute(
            (
                self.command.get('openssl'),
                'x509',
                '-noout',
                '-text',
                '-in', ohostedcons.FileLocations.LIBVIRT_SPICE_SERVER_CERT
            ),
            raiseOnError=True
        )
        for line in stdout:
            matcher = self._RE_SUBJECT.match(line)
            if matcher is not None:
                subject = matcher.group('subject')
                break
        if subject is None:
            raise RuntimeError(_('Error parsing libvirt certificate'))
        self.environment[ohostedcons.VDSMEnv.SPICE_SUBJECT] = subject

    def _generateSPICEcerts(self):
        # 'https://fedoraproject.org/wiki/
        # QA:Testcase_Virtualization_Manually_
        # set_spice_listening_port_with_TLS_port_set'
        self.logger.info(_('Generating libvirt-spice certificates'))
        self._tmpdir = tempfile.mkdtemp()
        expire = '1095'  # FIXME: configurable?
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
                '-subj', self.environment[ohostedcons.VDSMEnv.CA_SUBJECT]
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
                '-subj', self.environment[ohostedcons.VDSMEnv.PKI_SUBJECT]
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
            ohostedcons.FileLocations.LIBVIRT_SPICE_SERVER_CERT
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
        if self._selinux_enabled:
            rc, stdout, stderr = self.execute(
                (
                    self.command.get('restorecon'),
                    '-r',
                    cert_dir
                )
            )
            if rc != 0:
                self.logger.error(
                    _('Failed to refresh SELINUX context for {path}').format(
                        path=cert_dir
                    )
                )

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.VDSMEnv.PKI_SUBJECT,
            ohostedcons.Defaults.DEFAULT_PKI_SUBJECT
        )
        self.environment.setdefault(
            ohostedcons.VDSMEnv.CA_SUBJECT,
            ohostedcons.Defaults.DEFAULT_CA_SUBJECT
        )
        self.environment.setdefault(
            ohostedcons.VDSMEnv.SPICE_SUBJECT,
            None
        )
        self._selinux_enabled = False

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        # TODO:
        # remove when we understand how to replace the openssl command
        # with m2crypto code
        self.command.detect('openssl')
        self.command.detect('restorecon')
        self.command.detect('selinuxenabled')

    @plugin.event(
        stage=plugin.Stages.STAGE_LATE_SETUP,
        name=ohostedcons.Stages.VDSMD_PKI,
        after=(
            ohostedcons.Stages.VDSM_LIBVIRT_CONFIGURED,
        ),
    )
    def _late_setup(self):
        if self.command.get('selinuxenabled', optional=True) is None:
            self._selinux_enabled = False
        else:
            rc, stdout, stderr = self.execute(
                (
                    self.command.get('selinuxenabled'),
                ),
                raiseOnError=False,
            )
            self._selinux_enabled = (rc == 0)
        if not os.path.exists(ohostedcons.FileLocations.VDSMCERT):
            self._generateVDSMcerts()
            self._copy_vdsm_pki()
        if not os.path.exists(
            ohostedcons.FileLocations.LIBVIRT_SPICE_SERVER_CERT
        ):
            self._generateSPICEcerts()
        self._getSPICEcerts()

    @plugin.event(
        stage=plugin.Stages.STAGE_VALIDATION,
    )
    def _validation(self):
        if os.path.exists(ohostedcons.FileLocations.LIBVIRT_SPICE_SERVER_CERT):
            self._getSPICEcerts()

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        after=(
            ohostedcons.Stages.NODE_FILES_PERSIST_S,
        ),
        before=(
            ohostedcons.Stages.NODE_FILES_PERSIST_E,
        ),
        condition=lambda self: self.environment[
            ohostedcons.CoreEnv.NODE_SETUP
        ],
    )
    def _persist_files_start(self):
        self.logger.debug('Saving persisting PKI configuration')
        for path in (
            ohostedcons.FileLocations.VDSMCERT,
            ohostedcons.FileLocations.LIBVIRT_SPICE_SERVER_CERT,
        ):
            try:
                if os.path.exists(path):
                    # here we need the whole directory to be persisted
                    ohostedutil.persist(os.path.dirname(path))
            except Exception as e:
                self.logger.debug(
                    'Error persisting {path}'.format(
                        path=path,
                    ),
                    exc_info=True,
                )
                self.logger.error(e)

    @plugin.event(
        stage=plugin.Stages.STAGE_CLEANUP,
    )
    def _cleanup(self):
        if self._tmpdir and os.path.exists(self._tmpdir):
            shutil.rmtree(self._tmpdir)


# vim: expandtab tabstop=4 shiftwidth=4
