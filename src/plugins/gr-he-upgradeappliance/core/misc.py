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


"""Misc plugin."""


import gettext


from otopi import constants as otopicons
from otopi import context as otopicontext
from otopi import plugin
from otopi import util


from ovirt_hosted_engine_ha.env import config
from ovirt_hosted_engine_ha.lib import util as ohautil
from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """Misc plugin."""

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self._config = config.Config(logger=self.logger)
        # TODO: catch error if not configured and properly raise
        self.environment.setdefault(
            ohostedcons.StorageEnv.DOMAIN_TYPE,
            self._config.get(config.ENGINE, config.STORAGE),
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.SD_UUID,
            self._config.get(config.ENGINE, config.SD_UUID),
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.CONF_IMG_UUID,
            self._config.get(config.ENGINE, config.CONF_IMAGE_UUID),
        )
        self.environment.setdefault(
            ohostedcons.StorageEnv.CONF_VOL_UUID,
            self._config.get(config.ENGINE, config.CONF_VOLUME_UUID),
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.VM_UUID,
            self._config.get(config.ENGINE, config.HEVMID),
        )
        self.environment.setdefault(
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST,
            False,
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
        priority=plugin.Stages.PRIORITY_FIRST,
    )
    def _setup(self):
        self.dialog.note(
            _(
                'During customization use CTRL-D to abort.'
            )
        )
        interactive = self.environment[
            ohostedcons.CoreEnv.UPGRADE_PROCEED
        ] is None
        if interactive:
            self.environment[
                ohostedcons.CoreEnv.UPGRADE_PROCEED
            ] = self.dialog.queryString(
                name=ohostedcons.Confirms.UPGRADE_PROCEED,
                note=_(
                    'Continuing will upgrade the engine VM running on this '
                    'hosts deploying and configuring '
                    'a new appliance.\n'
                    'If your engine VM is already based on el7 you can also '
                    'simply upgrade the engine there.\n'
                    'This procedure will create a new disk on the '
                    'hosted-engine storage domain and it will backup '
                    'there the content of your current engine VM disk.\n'
                    'The new el7 based appliance will be deployed over the '
                    'existing disk destroying its content; '
                    'at any time you will be able to rollback using the '
                    'content of the backup disk.\n'
                    'You will be asked to take a backup of the running engine '
                    'and copy it to this host.\n'
                    'The engine backup will be automatically injected '
                    'and recovered on the new appliance.\n'
                    'Are you sure you want to continue? '
                    '(@VALUES@)[@DEFAULT@]: '
                ),
                # TODO: point to our site for troubleshooting info...
                prompt=True,
                validValues=(_('Yes'), _('No')),
                caseSensitive=False,
                default=_('Yes')
            ) == _('Yes').lower()
        if not self.environment[ohostedcons.CoreEnv.UPGRADE_PROCEED]:
            raise otopicontext.Abort('Aborted by user')

        self.environment[
            ohostedcons.CoreEnv.UPGRADING_APPLIANCE
        ] = True

        self.environment[
            ohostedcons.VDSMEnv.VDS_CLI
        ] = ohautil.connect_vdsm_json_rpc(
            logger=self.logger,
            timeout=ohostedcons.Const.VDSCLI_SSL_TIMEOUT,
        )

        self.environment.setdefault(
            ohostedcons.CoreEnv.REQUIREMENTS_CHECK_ENABLED,
            True
        )
        try:
            # avoid: pyflakes 'Config' imported but unused error
            import ovirt.node.utils.fs
            if hasattr(ovirt.node.utils.fs, 'Config'):
                self.environment[ohostedcons.CoreEnv.NODE_SETUP] = True
        except ImportError:
            self.logger.debug('Disabling persisting file configuration')

    @plugin.event(
        stage=plugin.Stages.STAGE_TERMINATE,
        priority=plugin.Stages.PRIORITY_LAST,
    )
    def _terminate(self):
        if self.environment[otopicons.BaseEnv.ERROR]:
            self.logger.error(_(
                'Hosted Engine upgrade failed: this system is not reliable. '
                'If necessary you can use --rollback-upgrade option to '
                'recover the engine VM disk from a backup'
            ))
            # TODO: point to our site for troubleshooting info...
            self.dialog.note(
                text=_('Log file is located at {path}').format(
                    path=self.environment[
                        otopicons.CoreEnv.LOG_FILE_NAME
                    ],
                ),
            )
        else:
            self.logger.info(_('Hosted Engine successfully upgraded'))
            self.logger.info(_(
                'Please exit global maintenance mode to '
                'restart the new engine VM.'
            ))


# vim: expandtab tabstop=4 shiftwidth=4
