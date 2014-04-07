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


"""Answer file fetcher plugin"""


import configparser
import gettext
import os
import paramiko
import tempfile


from otopi import constants as otopicons
from otopi import util
from otopi import common
from otopi import plugin


from ovirt_hosted_engine_setup import constants as ohostedcons


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """Answer file fetcher plugin"""

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._config = configparser.ConfigParser()
        self._config.optionxform = str
        self._tmp_ans = None

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
                        'Please provide the FQDN or IP of the first host: '
                    ),
                    prompt=True,
                    caseSensitive=True,
                )
            try:
                transport = paramiko.Transport((self.environment[
                    ohostedcons.FirstHostEnv.FQDN
                ], 22))
                valid = True
            except paramiko.SSHException as e:
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
                transport.close()

    def _fetch_answer_file(self):
        self.logger.debug('_fetch_answer_file')
        fqdn = self.environment[ohostedcons.FirstHostEnv.FQDN]
        interactive = (
            self.environment[ohostedcons.FirstHostEnv.ROOT_PASSWORD] is None
        )
        while self.environment[ohostedcons.FirstHostEnv.ROOT_PASSWORD] is None:
            if interactive:
                password = self.dialog.queryString(
                    name='HOST_FIRST_HOST_ROOT_PASSWORD',
                    note=_(
                        "Enter 'root' user password for host {fqdn}: "
                    ).format(
                        fqdn=fqdn,
                    ),
                    prompt=True,
                    hidden=True,
                )

            try:
                transport = paramiko.Transport(
                    (
                        fqdn,
                        self.environment[ohostedcons.FirstHostEnv.SSHD_PORT],
                    )
                )
                transport.connect(username='root', password=password)
                self.environment[
                    ohostedcons.FirstHostEnv.ROOT_PASSWORD
                ] = password
                self.environment[otopicons.CoreEnv.LOG_FILTER].append(
                    password
                )
                try:
                    fd, self._tmp_ans = tempfile.mkstemp(
                        dir=self.environment[ohostedcons.CoreEnv.TEMPDIR],
                    )
                    os.close(fd)
                    sftp = paramiko.SFTPClient.from_transport(transport)
                    sftp.get(
                        '/etc/ovirt-hosted-engine/answers.conf',
                        self._tmp_ans
                    )
                finally:
                    sftp.close()
            except paramiko.AuthenticationException:
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
                            'on first host'
                        )
                    )
            except paramiko.SSHException as e:
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
                            'on first host'
                        )
                    )
            finally:
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
        self.environment.setdefault(
            ohostedcons.FirstHostEnv.FETCH_ANSWER,
            None
        )
        self.environment.setdefault(
            ohostedcons.FirstHostEnv.SSHD_PORT,
            ohostedcons.Defaults.DEFAULT_SSHD_PORT
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
            self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST] and
            self.environment[otopicons.CoreEnv.CONFIG_FILE_APPEND] is None
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
            self.environment[
                ohostedcons.FirstHostEnv.FETCH_ANSWER
            ] = self.dialog.queryString(
                name='OVEHOSTED_CORE_FETCH_ANSWER',
                note=_(
                    'The answer file may be fetched from the first host '
                    'using scp.\n'
                    'If you do not want to download it '
                    'automatically you can abort the setup answering no '
                    'to the following question.\n'
                    'Do you want to scp the answer file from the first host? '
                    '(@VALUES@)[@DEFAULT@]: '
                ),
                prompt=True,
                validValues=(_('Yes'), _('No')),
                caseSensitive=False,
                default=_('Yes')
            ) == _('Yes').lower()

        if not self.environment[ohostedcons.FirstHostEnv.FETCH_ANSWER]:
            raise RuntimeError(
                _(
                    'Cannot deploy Hosted Engine on additional hosts '
                    'without access to the configuration used on '
                    'the first host'
                )
            )

        self._get_fqdn()
        self._fetch_answer_file()
        self._parse_answer_file()

    @plugin.event(
        stage=plugin.Stages.STAGE_CLEANUP,
    )
    def _cleanup(self):
        if self._tmp_ans and os.path.exists(self._tmp_ans):
            os.unlink(self._tmp_ans)


# vim: expandtab tabstop=4 shiftwidth=4
