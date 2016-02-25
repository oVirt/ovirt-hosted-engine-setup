#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2013-2016 Red Hat, Inc.
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


"""Answer file fetcher plugin"""


import configparser
import gettext
import os
import paramiko
import socket
import tempfile


from otopi import common
from otopi import constants as otopicons
from otopi import plugin
from otopi import util


from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_setup_lib import dialog


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """Answer file fetcher plugin"""

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._config = configparser.ConfigParser()
        self._config.optionxform = str
        self._tmp_ans = None

    def _check_he35_from_answerfile(self):
        if self.environment[
            ohostedcons.StorageEnv.CONF_IMG_UUID
        ] is None:
            return True
        return False

    def _get_fqdn(self):
        fqdn_interactive = self.environment[
            ohostedcons.FirstHostEnv.FQDN
        ] is None
        valid = False
        while not valid:
            if fqdn_interactive:
                self.environment[
                    ohostedcons.FirstHostEnv.FQDN
                ] = self.dialog.queryString(
                    name='OVEHOSTED_NET_FIRST_HOST_FQDN',
                    note=_(
                        'Please provide the FQDN or IP of an active '
                        'HE host: '
                    ),
                    prompt=True,
                    caseSensitive=True,
                )
            transport = None
            try:
                transport = paramiko.Transport((self.environment[
                    ohostedcons.FirstHostEnv.FQDN
                ], 22))
                valid = True
            except (paramiko.SSHException, socket.gaierror) as e:
                self.logger.debug('exception', exc_info=True)
                if fqdn_interactive:
                    self.logger.error(
                        _(
                            'Unable to connect to {fqdn}. Error: {error}'
                        ).format(
                            fqdn=self.environment[
                                ohostedcons.FirstHostEnv.FQDN
                            ],
                            error=e,
                        )
                    )
                else:
                    raise RuntimeError(
                        _(
                            'Unable to connect to {fqdn}. Error: {error}'
                        ).format(
                            fqdn=self.environment[
                                ohostedcons.FirstHostEnv.FQDN
                            ],
                            error=e,
                        )
                    )
            finally:
                if transport is not None:
                    transport.close()

    def _fetch_answer_file(self):
        self.logger.debug('_fetch_answer_file')
        fqdn = self.environment[ohostedcons.FirstHostEnv.FQDN]
        interactive = (
            self.environment[ohostedcons.FirstHostEnv.ROOT_PASSWORD] is None
        )
        password_correct = False
        while not password_correct:
            if interactive:
                self.environment[
                    ohostedcons.FirstHostEnv.ROOT_PASSWORD
                ] = self.dialog.queryString(
                    name='HOST_FIRST_HOST_ROOT_PASSWORD',
                    note=_(
                        "Enter 'root' user password for host {fqdn}: "
                    ).format(
                        fqdn=fqdn,
                    ),
                    prompt=True,
                    hidden=True,
                )
            transport = None
            try:
                transport = paramiko.Transport(
                    (
                        fqdn,
                        self.environment[ohostedcons.FirstHostEnv.SSHD_PORT],
                    )
                )
                transport.connect(
                    username='root',
                    password=self.environment[
                        ohostedcons.FirstHostEnv.ROOT_PASSWORD
                    ]
                )
                password_correct = True
                try:
                    fd, self._tmp_ans = tempfile.mkstemp(
                        dir=self.environment[ohostedcons.CoreEnv.TEMPDIR],
                    )
                    os.close(fd)
                    sftp = paramiko.SFTPClient.from_transport(transport)
                    sftp.get(
                        self.environment[ohostedcons.CoreEnv.ETC_ANSWER_FILE],
                        self._tmp_ans
                    )
                finally:
                    sftp.close()
            except paramiko.AuthenticationException as e:
                self.logger.error(
                    _('Invalid password for host {fqdn}').format(
                        fqdn=fqdn,
                    )
                )
                if not interactive:
                    raise RuntimeError(
                        _(
                            'Cannot deploy Hosted Engine on additional host: '
                            'unable to fetch the configuration used '
                            'on other hosts'
                        )
                    )
            except (paramiko.SSHException, socket.gaierror) as e:
                self.logger.debug('exception', exc_info=True)
                self.logger.error(
                    _('Unable to connect to {fqdn}. Error:{error}').format(
                        fqdn=fqdn,
                        error=e,
                    )
                )
                if not interactive:
                    raise RuntimeError(
                        _(
                            'Cannot deploy Hosted Engine on additional host: '
                            'unable to fetch the configuration used '
                            'on other hosts'
                        )
                    )
            finally:
                if transport is not None:
                    transport.close()
        self.logger.info(_('Answer file successfully downloaded'))

    def _parse_answer_file(self):
        self._config.read(self._tmp_ans)
        for name, value in self._config.items(
            otopicons.Const.CONFIG_SECTION_DEFAULT
        ):
            try:
                value = common.parseTypedValue(value)
                self.logger.debug('%s=%s' % (name, value))
            except Exception as e:
                raise RuntimeError(
                    _(
                        "Cannot parse configuration file key "
                        "{key} at section {section}: {exception}"
                    ).format(
                        key=name,
                        section=otopicons.Const.CONFIG_SECTION_DEFAULT,
                        exception=e,
                    )
                )
            self.environment[name] = value

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.FirstHostEnv.FQDN,
            None
        )
        self.environment.setdefault(
            ohostedcons.FirstHostEnv.ROOT_PASSWORD,
            None
        )
        self.environment[otopicons.CoreEnv.LOG_FILTER_KEYS].append(
            ohostedcons.FirstHostEnv.ROOT_PASSWORD
        )
        self.environment.setdefault(
            ohostedcons.FirstHostEnv.FETCH_ANSWER,
            None
        )
        self.environment.setdefault(
            ohostedcons.FirstHostEnv.SSHD_PORT,
            ohostedcons.Defaults.DEFAULT_SSHD_PORT
        )
        self.environment.setdefault(
            ohostedcons.FirstHostEnv.DEPLOY_WITH_HE_35_HOSTS,
            None
        )

    @plugin.event(
        name=ohostedcons.Stages.REQUIRE_ANSWER_FILE,
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.DIALOG_TITLES_E_STORAGE,
            ohostedcons.Stages.DIALOG_TITLES_S_SYSTEM,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_SYSTEM,
        ),
        condition=lambda self: (
            self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]
        ),
    )
    def _customization(self):
        self.logger.warning(
            _(
                'A configuration file must be supplied to deploy '
                'Hosted Engine on an additional host.'
            )
        )

        interactive = self.environment[
            ohostedcons.FirstHostEnv.FETCH_ANSWER
        ] is None
        if interactive:
            if self.environment[otopicons.CoreEnv.CONFIG_FILE_APPEND] is None:
                additional = _(
                    'If you do not want to download it '
                    'automatically you can abort the setup answering no '
                    'to the following question.\n'
                )
            else:
                additional = _(
                    'If the supplied answerfile is complete, answer no '
                    'to the following question to continue just with that.\n'
                )
            self.environment[
                ohostedcons.FirstHostEnv.FETCH_ANSWER
            ] = self.dialog.queryString(
                name='OVEHOSTED_CORE_FETCH_ANSWER',
                note=_(
                    'The answer file may be fetched from an active HE host '
                    'using scp.\n'
                    '{additional}'
                    'Do you want to scp the answer file from another HE host? '
                    '(@VALUES@)[@DEFAULT@]: '
                ).format(additional=additional),
                prompt=True,
                validValues=(_('Yes'), _('No')),
                caseSensitive=False,
                default=_('Yes')
            ) == _('Yes').lower()

        if not self.environment[ohostedcons.FirstHostEnv.FETCH_ANSWER]:
            if self.environment[otopicons.CoreEnv.CONFIG_FILE_APPEND] is None:
                raise RuntimeError(
                    _(
                        'Cannot deploy Hosted Engine on additional hosts '
                        'without access to the configuration used on '
                        'other hosts'
                    )
                )
            else:
                self.logger.info(
                    _(
                        "Setup will proceed assuming that '{answfile}' "
                        "was correctly and completely generated "
                        "on another HE host"
                    ).format(
                        answfile=self.environment[
                            otopicons.CoreEnv.CONFIG_FILE_APPEND
                        ]
                    )
                )
        else:
            self._get_fqdn()
            self._fetch_answer_file()
            self._parse_answer_file()

    @plugin.event(
        stage=plugin.Stages.STAGE_VALIDATION,
        condition=lambda self: (
            self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]
        ),
    )
    def _validation(self):
        # Prevent directly deploying an HE host from 3.6 if the answerfile of
        # the first host is at 3.5 since in that case the configuration volume
        # is not on the shared storage and we are not going to create it.

        he_answerfile_from_35 = self._check_he35_from_answerfile()

        if self.environment[
            ohostedcons.FirstHostEnv.DEPLOY_WITH_HE_35_HOSTS
        ] is None and he_answerfile_from_35:
            self.dialog.note(
                text=_(
                    'It seems like your existing HE infrastructure was '
                    'deployed with version 3.5 (or before) and never upgraded '
                    'to current release.\n'
                    'Mixing hosts with HE from 3.5 (or before) and current '
                    'release is not supported.\n'
                    'Please upgrade the existing HE hosts to current release '
                    'before adding this host.\n'
                    'Please check the log file for more details.\n'
                ),
            )
            self.environment[
                ohostedcons.FirstHostEnv.DEPLOY_WITH_HE_35_HOSTS
            ] = dialog.queryBoolean(
                dialog=self.dialog,
                name='OVEHOSTED_PREVENT_MIXING_HE_35_CURRENT',
                note=_(
                    'Replying "No" will abort Setup.\n'
                    'Continue? '
                    '(@VALUES@) [@DEFAULT@]: '
                ),
                prompt=True,
                default=False,
            )

        if not self.environment[
            ohostedcons.FirstHostEnv.DEPLOY_WITH_HE_35_HOSTS
        ] and he_answerfile_from_35:
            raise RuntimeError(
                _('other hosted-engine host is still at version 3.5')
            )

    @plugin.event(
        stage=plugin.Stages.STAGE_CLEANUP,
    )
    def _cleanup(self):
        if self._tmp_ans and os.path.exists(self._tmp_ans):
            os.unlink(self._tmp_ans)


# vim: expandtab tabstop=4 shiftwidth=4
