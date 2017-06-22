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
VM misc plugin.
"""


import gettext

from otopi import plugin
from otopi import util

from vdsm.client import ServerError

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import tasks
from ovirt_hosted_engine_setup import vm_status


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    VM misc plugin.
    """

    SHUTDOWN_DELAY_SECS = '10'

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_LATE_SETUP,
        after=(
            ohostedcons.Stages.VDSMD_CONF_LOADED,
            ohostedcons.Stages.VDSM_LIBVIRT_CONFIGURED,
        ),
        name=ohostedcons.Stages.CHECK_MAINTENANCE_MODE,
        condition=lambda self: (
            self.environment[ohostedcons.CoreEnv.UPGRADING_APPLIANCE] or
            self.environment[ohostedcons.CoreEnv.ROLLBACK_UPGRADE]
        )
    )
    def _late_setup(self):
        self.logger.info('Checking maintenance mode')
        vmstatus = vm_status.VmStatus()
        status = vmstatus.get_status()
        self.logger.debug('hosted-engine-status: {s}'.format(s=status))
        if not status['global_maintenance']:
            self.logger.error(_(
                'Please enable global maintenance mode before '
                'upgrading or restoring'
            ))
            raise RuntimeError(_('Not in global maintenance mode'))

        if self.environment[ohostedcons.CoreEnv.ROLLBACK_UPGRADE]:
            if status['engine_vm_up']:
                self.logger.error(_(
                    'The engine VM seams up, please stop it before '
                    'restoring.'
                ))
                raise RuntimeError(_('Engine VM is up'))
            else:
                self.logger.info(_(
                    'The engine VM is down.'
                ))
        if self.environment[ohostedcons.CoreEnv.UPGRADING_APPLIANCE]:
            cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
            try:
                vmList = cli.Host.getVMList()
                self.logger.debug(vmList)
            except ServerError as e:
                raise RuntimeError(
                    _('Unable to get VM list from VDSM. Error: {m}').format(
                        m=str(e)
                    )
                )

            vms = set(vmList)
            if self.environment[ohostedcons.VMEnv.VM_UUID] not in vms:
                raise RuntimeError(_(
                    'The engine VM is not running on this host'
                ))

            self.logger.info('The engine VM is running on this host')

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        after=(
            ohostedcons.Stages.VDSCLI_RECONNECTED,
            ohostedcons.Stages.CONF_IMAGE_AVAILABLE,
            ohostedcons.Stages.UPGRADE_BACKUP_DISK_REGISTERED,
        ),
        condition=lambda self: (
            not self.environment[ohostedcons.CoreEnv.ROLLBACK_UPGRADE]
        ),
        name=ohostedcons.Stages.VM_SHUTDOWN,
    )
    def _closeup(self):
        if self.environment[
            ohostedcons.VMEnv.AUTOMATE_VM_SHUTDOWN
        ]:
            self.logger.info(_('Shutting down the engine VM'))
            cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
            try:
                cli.VM.shutdown(
                    vmID=self.environment[ohostedcons.VMEnv.VM_UUID]
                )
            except ServerError as e:
                self.logger.debug(str(e))

        else:
            self.dialog.note(
                _(
                    'Please shutdown the VM allowing the system '
                    'to launch it as a monitored service.\n'
                    'The system will wait until the VM is down.'
                )
            )
        waiter = tasks.VMDownWaiter(self.environment)
        if not waiter.wait():
            # The VM is down but not destroyed
            cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
            try:
                cli.VM.destroy(
                    vmID=self.environment[ohostedcons.VMEnv.VM_UUID]
                )
            except ServerError as e:
                self.logger.error(
                    _('Cannot destroy the Hosted Engine VM: {error}').format(
                        error=str(e)
                    )
                )
                raise RuntimeError(str(e))


# vim: expandtab tabstop=4 shiftwidth=4
