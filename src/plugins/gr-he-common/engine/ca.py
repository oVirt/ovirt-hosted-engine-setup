#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2016 Red Hat, Inc.
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
Engine CA plugin.
"""

import gettext
import os
import tempfile


from otopi import constants as otopicons
from otopi import plugin
from otopi import util


from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import pkissh


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    Engine CA plugin.
    """

    VDSM_RETRIES = 600
    VDSM_DELAY = 1

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._interactive_admin_pwd = True

    def _getCA(self):
        fqdn = self.environment[
            ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
        ]
        fd, cert = tempfile.mkstemp(
            prefix='engine-ca',
            suffix='.crt',
        )
        os.close(fd)
        self.environment[
            ohostedcons.EngineEnv.TEMPORARY_CERT_FILE
        ] = cert
        valid = False
        interactive = True
        if self.environment[
            ohostedcons.EngineEnv.INSECURE_SSL
        ]:
            valid = True
            if cert is not None and os.path.exists(cert):
                os.unlink(cert)
            self.environment[
                ohostedcons.EngineEnv.TEMPORARY_CERT_FILE
            ] = None
        elif self.environment[
            ohostedcons.EngineEnv.INSECURE_SSL
        ] is False:
            interactive = False
        pkihelper = pkissh.PKIHelper()

        while not valid:
            cafile = ohostedcons.FileLocations.SYS_CUSTOMCA_CERT
            if not os.path.isfile(ohostedcons.FileLocations.SYS_CUSTOMCA_CERT):
                cafile = None
            try:
                content = pkihelper.getPKICert(
                    fqdn,
                    cafile,
                )
            except RuntimeError as ex:
                self.logger.error(
                    _('Error acquiring CA cert').format(
                        message=ex.message,
                    )
                )
            else:
                try:
                    with open(cert, 'w') as fileobj:
                        fileobj.write(content)
                except EnvironmentError as ex:
                    raise RuntimeError(
                        'Unable to write cert file: ' + ex.message
                    )
                if pkihelper.validateCA(fqdn, cert):
                    valid = True
            if not valid:
                if interactive:
                    if cafile:
                        catype = _('custom')
                    else:
                        catype = _('internal')
                    insecure = self.dialog.queryString(
                        name='SSL_VALIDATE_CA',
                        note=_(
                            'The REST API cert couldn\'t be trusted with the '
                            '{catype} CA cert\n'
                            'Would you like to continue in insecure mode '
                            '(not recommended)?\n'
                            'If not, please provide your CA cert at {path} '
                            'before continuing\n'
                            '(@VALUES@)[@DEFAULT@]? '
                        ).format(
                            catype=catype,
                            path=ohostedcons.FileLocations.SYS_CUSTOMCA_CERT,
                        ),
                        prompt=True,
                        validValues=(_('Yes'), _('No')),
                        caseSensitive=False,
                        default=_('No')
                    ) == _('Yes').lower()
                    if insecure:
                        valid = True
                        self.environment[
                            ohostedcons.EngineEnv.INSECURE_SSL
                        ] = True
                        cert = self.environment[
                            ohostedcons.EngineEnv.TEMPORARY_CERT_FILE
                        ]
                        if cert is not None and os.path.exists(cert):
                            os.unlink(cert)
                        self.environment[
                            ohostedcons.EngineEnv.TEMPORARY_CERT_FILE
                        ] = None
                else:
                    raise RuntimeError('Failed trusting the REST API cert')

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.EngineEnv.ADMIN_PASSWORD,
            None
        )
        self.environment[otopicons.CoreEnv.LOG_FILTER_KEYS].append(
            ohostedcons.EngineEnv.ADMIN_PASSWORD
        )
        self.environment.setdefault(
            ohostedcons.EngineEnv.TEMPORARY_CERT_FILE,
            None
        )
        self.environment.setdefault(
            ohostedcons.EngineEnv.INSECURE_SSL,
            None
        )
        self.environment.setdefault(
            ohostedcons.EngineEnv.INTERACTIVE_ADMIN_PASSWORD,
            None
        )

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
        self.environment[ohostedcons.EngineEnv.INTERACTIVE_ADMIN_PASSWORD] = (
            self.environment[ohostedcons.EngineEnv.ADMIN_PASSWORD] is None
        )
        while self.environment[ohostedcons.EngineEnv.ADMIN_PASSWORD] is None:
            password = self.dialog.queryString(
                name='ENGINE_ADMIN_PASSWORD',
                note=_(
                    "Enter engine admin password: "
                ),
                prompt=True,
                hidden=True,
            )
            if password:
                password_check = self.dialog.queryString(
                    name='ENGINE_ADMIN_PASSWORD',
                    note=_(
                        "Confirm engine admin password: "
                    ),
                    prompt=True,
                    hidden=True,
                )
                if password == password_check:
                    self.environment[
                        ohostedcons.EngineEnv.ADMIN_PASSWORD
                    ] = password
                else:
                    self.logger.error(_('Passwords do not match'))
            else:
                if self.environment[
                    ohostedcons.EngineEnv.INTERACTIVE_ADMIN_PASSWORD
                ]:
                    self.logger.error(_('Please specify a password'))
                else:
                    raise RuntimeError(
                        _('Empty password not allowed for user admin')
                    )

    @plugin.event(
        stage=plugin.Stages.STAGE_VALIDATION,
        name=ohostedcons.Stages.VALIDATION_CA_ACQUIRED,
        condition=lambda self: (
            self.environment[ohostedcons.CoreEnv.UPGRADING_APPLIANCE]
        ),
    )
    def _validation(self):
        self._getCA()

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        after=(
            ohostedcons.Stages.ENGINE_ALIVE,
        ),
        name=ohostedcons.Stages.CLOSEUP_CA_ACQUIRED,
        condition=lambda self: (
            not self.environment[ohostedcons.CoreEnv.UPGRADING_APPLIANCE]
        ),
    )
    def _closeup(self):
        self._getCA()

    @plugin.event(
        stage=plugin.Stages.STAGE_CLEANUP,
    )
    def _cleanup(self):
        cert = self.environment[ohostedcons.EngineEnv.TEMPORARY_CERT_FILE]
        try:
            if cert is not None and os.path.exists(cert):
                os.unlink(cert)
        except EnvironmentError as ex:
            self.log.error(
                _(
                    'Unable to cleanup temporary CA cert file: {msg}'
                ).format(
                    msg=ex.message,
                )
            )


# vim: expandtab tabstop=4 shiftwidth=4
