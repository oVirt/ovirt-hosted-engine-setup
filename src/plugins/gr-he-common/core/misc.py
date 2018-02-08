#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2016-2017 Red Hat, Inc.
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
import os
import time

from otopi import constants as otopicons
from otopi import plugin
from otopi import util

from ovirt_hosted_engine_ha.lib.exceptions import BrokerConnectionError

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import util as ohostedutil
from ovirt_hosted_engine_setup import vm_status


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """Misc plugin."""

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_BOOT,
        before=(
            otopicons.Stages.CORE_LOG_INIT,
        ),
    )
    def _preinit(self):
        self.environment.setdefault(
            otopicons.CoreEnv.LOG_FILE_NAME_PREFIX,
            ohostedcons.FileLocations.OVIRT_HOSTED_ENGINE_SETUP
        )
        self.environment.setdefault(
            otopicons.CoreEnv.LOG_DIR,
            ohostedcons.FileLocations.OVIRT_HOSTED_ENGINE_SETUP_LOGDIR
        )
        self.environment.setdefault(
            otopicons.CoreEnv.CONFIG_FILE_NAME,
            self.resolveFile(
                os.environ.get(
                    otopicons.SystemEnvironment.CONFIG,
                    self.resolveFile(
                        ohostedcons.
                        FileLocations.OVIRT_HOSTED_ENGINE_SETUP_CONFIG_FILE
                    )
                )
            )
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.CoreEnv.DEPLOY_PROCEED,
            None
        )
        self.environment.setdefault(
            ohostedcons.CoreEnv.UPGRADE_PROCEED,
            None
        )
        self.environment.setdefault(
            ohostedcons.CoreEnv.ROLLBACK_PROCEED,
            None
        )
        self.environment.setdefault(
            ohostedcons.CoreEnv.UPGRADING_APPLIANCE,
            False
        )
        self.environment.setdefault(
            ohostedcons.CoreEnv.ROLLBACK_UPGRADE,
            False
        )
        self.environment.setdefault(
            ohostedcons.CoreEnv.ANSIBLE_DEPLOYMENT,
            False
        )
        self.environment.setdefault(
            ohostedcons.EngineEnv.HOST_CLUSTER_NAME,
            None
        )
        self.environment[ohostedcons.CoreEnv.NODE_SETUP] = False
        self.environment[ohostedcons.CoreEnv.MISC_REACHED] = False

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        priority=plugin.Stages.PRIORITY_FIRST,
    )
    def _misc_reached(self):
        self.environment[ohostedcons.CoreEnv.MISC_REACHED] = True

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        name=ohostedcons.Stages.NODE_FILES_PERSIST_S,
        after=(
            ohostedcons.Stages.HA_START,
        ),
        before=(
            ohostedcons.Stages.NODE_FILES_PERSIST_E,
        ),
        condition=lambda self: self.environment[
            ohostedcons.CoreEnv.NODE_SETUP
        ],
    )
    def _persist_files_start(self):
        # Using two stages here because some files can be written out of
        # transactions
        self.logger.debug('Saving persisting file configuration')
        for path in self.environment[
            otopicons.CoreEnv.MODIFIED_FILES
        ] + [
            self.environment[otopicons.CoreEnv.LOG_DIR],
        ]:
            try:
                ohostedutil.persist(path)
            except Exception as e:
                self.logger.debug(
                    'Error persisting {path}'.format(
                        path=path,
                    ),
                    exc_info=True,
                )
                self.logger.error(e)

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        name=ohostedcons.Stages.NODE_FILES_PERSIST_E,
        after=(
            ohostedcons.Stages.NODE_FILES_PERSIST_S,
        ),
        condition=lambda self: self.environment[
            ohostedcons.CoreEnv.NODE_SETUP
        ],
    )
    def _persist_files_end(self):
        # Using two stages here because some files can be written out of
        # transactions
        self.logger.debug('Finished persisting file configuration')

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        after=(
            ohostedcons.Stages.HA_START,
        ),
        name=ohostedcons.Stages.ENGINE_VM_UP_CHECK,
        condition=lambda self: (
            not self.environment[ohostedcons.CoreEnv.ANSIBLE_DEPLOYMENT]
        ),
    )
    def engine_vm_up_check(self):
        timeout = ohostedcons.Const.VM_LIVELINESS_CHECK_TIMEOUT
        vmstatus = vm_status.VmStatus()
        self.logger.info('Waiting for engine to start...')
        health_good = False
        while timeout >= 0:
            try:
                status = vmstatus.get_status()
                for host in status['all_host_stats'].values():
                    if 'engine-status' in host:
                        if '"health": "good"' in host['engine-status']:
                            health_good = True
                            break

            except (BrokerConnectionError, RuntimeError) as e:
                self.logger.debug(str(e))

            if health_good:
                self.logger.info('Engine is up')
                break

            time.sleep(5)
            timeout -= 5

            if timeout % 60 == 0:
                self.logger.info('Still waiting for engine to start...')

        if timeout < 0:
            self.logger.info(
                'Engine vm is still powering up, please check the vm\'s '
                'status using: \'hosted-engine --vm-status\''
            )

    @plugin.event(
        stage=plugin.Stages.STAGE_TERMINATE,
        priority=plugin.Stages.PRIORITY_LAST,
    )
    def _terminate(self):
        successfully = _('Hosted Engine successfully deployed')
        failed_early = _('Hosted Engine deployment failed')
        failed_hard = failed_early + _(
            ': please check the logs for the issue, '
            'fix accordingly or re-deploy from scratch.'
        )
        if self.environment[ohostedcons.CoreEnv.UPGRADING_APPLIANCE]:
            successfully = _('Hosted Engine successfully upgraded')
            failed_early = _('Hosted Engine upgrade failed')
            failed_hard = failed_early + _(
                ': you can use --rollback-upgrade option to recover the '
                'engine VM disk from a backup.'
            )
        elif self.environment[ohostedcons.CoreEnv.ROLLBACK_UPGRADE]:
            successfully = _('Hosted Engine successfully rolled back')
            failed_early = _('Hosted Engine rollback failed')
            failed_hard = failed_early + _(
                ': please check the logs and try again this '
                'procedure to reach a stable status.'
            )
        if self.environment[otopicons.BaseEnv.ERROR]:
            self.logger.error(
                failed_hard if self.environment[
                    ohostedcons.CoreEnv.MISC_REACHED
                ] else failed_early
            )
            self.dialog.note(
                text=_('Log file is located at {path}').format(
                    path=self.environment[
                        otopicons.CoreEnv.LOG_FILE_NAME
                    ],
                ),
            )
        else:
            self.logger.info(successfully)
            if (
                self.environment[ohostedcons.CoreEnv.UPGRADING_APPLIANCE] or
                self.environment[ohostedcons.CoreEnv.ROLLBACK_UPGRADE]
            ):
                self.logger.info(_(
                    'Please exit global maintenance mode to '
                    'restart the engine VM.'
                ))
                self.logger.info(_(
                    'Please note that the engine VM ssh keys have changed. '
                    'Please remove the engine VM entry in ssh known_hosts on '
                    'your clients.'
                ))

# vim: expandtab tabstop=4 shiftwidth=4
