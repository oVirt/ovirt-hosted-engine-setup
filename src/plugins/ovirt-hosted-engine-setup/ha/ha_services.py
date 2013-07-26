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


"""
HA services
"""


import gettext


from otopi import util
from otopi import plugin


from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import tasks


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    HA services plugin.
    """

    SHUTDOWN_DELAY_SECS = '10'

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        after=[
            ohostedcons.Stages.HOST_ADDED,
        ],
        name=ohostedcons.Stages.HA_START,
    )
    def _closeup(self):
        # shutdown the vm if this is first host.
        if not self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]:
            self.dialog.note(
                _(
                    'Please shutdown the VM allowing the system to launch it '
                    'as a monitored service.\n'
                    'The system will wait until the VM is down.'
                )
            )
            waiter = tasks.VMDownWaiter(self.environment)
            if not waiter.wait():
                #The VM is down but not destroyed
                vdscommand = [self.command.get('vdsClient')]
                if self.environment[ohostedcons.VDSMEnv.USE_SSL]:
                    vdscommand.append('-s')
                vdscommand += [
                    'localhost',
                    'destroy',
                    self.environment[ohostedcons.VMEnv.VM_UUID],
                ]
                self.execute(
                    vdscommand,
                    raiseOnError=True
                )
        # enable and start HA services
        for service in (
            ohostedcons.Const.HA_AGENT_SERVICE,
            ohostedcons.Const.HA_BROCKER_SERVICE,
        ):
            self.services.startup(
                name=service,
                state=True,
            )
            self.services.state(
                name=service,
                state=True,
            )

# vim: expandtab tabstop=4 shiftwidth=4
