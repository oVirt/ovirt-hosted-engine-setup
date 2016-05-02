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
VM state plugin.
"""


import gettext

from otopi import plugin
from otopi import util


from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import tasks


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    VM shutdown plugin.
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
        name=ohostedcons.Stages.VDSMD_LATE_SETUP_READY,
    )
    def _late_setup(self):
        cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        response = cli.list()
        self.logger.debug(response)
        if response['status']['code'] == 0 and 'items' in response:
            if 'items' in response and response['items']:
                self.logger.error(
                    _(
                        'The following VMs has been found: '
                        '{vms}'
                    ).format(
                        vms=', '.join(response['items'])
                    )
                )
                raise RuntimeError(
                    _('Cannot setup Hosted Engine with other VMs running')
                )

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        after=(
            ohostedcons.Stages.VDSCLI_RECONNECTED,
            ohostedcons.Stages.CONF_IMAGE_AVAILABLE,
            ohostedcons.Stages.UPGRADED_APPLIANCE_RUNNING,
        ),
        condition=lambda self: (
            not self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]
        ),
        name=ohostedcons.Stages.VM_SHUTDOWN,
    )
    def _closeup(self):
        if self.environment[
            ohostedcons.VMEnv.AUTOMATE_VM_SHUTDOWN
        ]:
            self.logger.info(_('Shutting down the engine VM'))
            cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
            res = cli.shutdown(self.environment[ohostedcons.VMEnv.VM_UUID])
            self.logger.debug(res)
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
            status = self.environment[
                ohostedcons.VDSMEnv.VDS_CLI
            ].destroy(
                self.environment[ohostedcons.VMEnv.VM_UUID]
            )
            self.logger.debug(status)
            if status['status']['code'] != 0:
                self.logger.error(
                    _(
                        'Cannot destroy the Hosted Engine VM: ' +
                        status['status']['message']
                    )
                )
                raise RuntimeError(status['status']['message'])


# vim: expandtab tabstop=4 shiftwidth=4
