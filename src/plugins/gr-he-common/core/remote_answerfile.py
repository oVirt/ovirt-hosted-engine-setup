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


from io import StringIO

from otopi import constants as otopicons
from otopi import common
from otopi import plugin
from otopi import util

from ovirt_setup_lib import dialog

from ovirt_hosted_engine_ha.lib import heconflib

from ovirt_hosted_engine_setup import constants as ohostedcons


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

    def _fetch_answer_file(self):
        self.logger.debug('_fetch_answer_file')

        source = heconflib.get_volume_path(
            self.environment[ohostedcons.StorageEnv.DOMAIN_TYPE],
            self.environment[ohostedcons.StorageEnv.SD_UUID],
            self.environment[ohostedcons.StorageEnv.CONF_IMG_UUID],
            self.environment[ohostedcons.StorageEnv.CONF_VOL_UUID],
        )
        self.logger.debug('fetching from: ' + str(source))

        if not heconflib.validateConfImage(self.logger, source):
            msg = _('Unable to get the answer file from the shared storage')
            self.logger.error(msg)
            raise RuntimeError(msg)
        self._tmp_ans = heconflib.extractConfFile(
            self.logger,
            source,
            ohostedcons.FileLocations.HECONFD_ANSWERFILE,
        )
        self.logger.debug(
            'Answer file form the shared storage: {content}'.format(
                content=self._tmp_ans
            )
        )
        self.logger.info(_('Answer file successfully loaded'))

    def _parse_answer_file(self):
        buf = StringIO(unicode(self._tmp_ans))
        try:
            self._config.readfp(buf)
        except configparser.Error as ex:
            msg = _(
                'The answer file on the shared storage is invalid, '
                'please check and fix it: {ex}'
            ).format(ex=ex)
            self.logger.error(msg)
            raise RuntimeError(msg)

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
            ohostedcons.FirstHostEnv.SKIP_SHARED_STORAGE_ANSWERF,
            False
        )
        self.environment.setdefault(
            ohostedcons.FirstHostEnv.DEPLOY_WITH_HE_35_HOSTS,
            None
        )

    @plugin.event(
        name=ohostedcons.Stages.REQUIRE_ANSWER_FILE,
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_SYSTEM,
            ohostedcons.Stages.CONFIG_STORAGE_LATE,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_SYSTEM,
        ),
        condition=lambda self: (
            self.environment[ohostedcons.CoreEnv.UPGRADING_APPLIANCE] or
            self.environment[ohostedcons.CoreEnv.ROLLBACK_UPGRADE]
        ),
    )
    def _customization(self):
        if self.environment[
            ohostedcons.FirstHostEnv.SKIP_SHARED_STORAGE_ANSWERF
        ]:
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
            _ovf = self.environment[ohostedcons.VMEnv.OVF]
            if (
                self.environment[ohostedcons.StorageEnv.CONF_IMG_UUID] and
                self.environment[ohostedcons.StorageEnv.CONF_VOL_UUID]
            ):
                self._fetch_answer_file()
                self._parse_answer_file()
                if self.environment[ohostedcons.CoreEnv.UPGRADING_APPLIANCE]:
                    self.environment[ohostedcons.VMEnv.OVF] = _ovf
                    self.environment[ohostedcons.VMEnv.CDROM] = None
                    self.environment[
                        ohostedcons.CloudInit.GENERATE_ISO
                    ] = ohostedcons.Const.CLOUD_INIT_GENERATE
                    self.environment[
                        ohostedcons.CloudInit.EXECUTE_ESETUP
                    ] = True
                    self.environment[
                        ohostedcons.VMEnv.AUTOMATE_VM_SHUTDOWN
                    ] = True
                    self.environment[
                        ohostedcons.Upgrade.BACKUP_SIZE_GB
                    ] = self.environment[ohostedcons.StorageEnv.IMAGE_SIZE_GB]
                    self.environment[
                        ohostedcons.StorageEnv.IMAGE_SIZE_GB
                    ] = None
            else:
                self.logger.error(_(
                    'Unable to find the hosted-engine configuration volume '
                    'on the shared storage.'
                ))

        # Prevent directly deploying an HE host from 3.6 if the answer file of
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


# vim: expandtab tabstop=4 shiftwidth=4
