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

import time
import gettext


from otopi import base
from otopi import util


from ovirt_hosted_engine_setup import constants as ohostedcons


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class TaskWaiter(base.Base):
    """
    Task waiting utility.
    """

    def __init__(self, environment):
        super(TaskWaiter, self).__init__()
        self.environment = environment

    def wait(self):
        serv = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        wait = True
        while wait:
            self.logger.debug('Waiting for existing tasks to complete')
            statuses = serv.s.getAllTasksStatuses()
            code = statuses['status']['code']
            message = statuses['status']['message']
            if code != 0:
                raise RuntimeError(
                    _(
                        'Error getting task status: {error}'
                    ).format(
                        error=message
                    )
                )
            tasksStatuses = statuses['allTasksStatus']
            all_completed = True
            for taskID in tasksStatuses:
                if tasksStatuses[taskID]['taskState'] != 'finished':
                    all_completed = False
                else:
                    serv.clearTask([taskID])
            if all_completed:
                wait = False
            else:
                time.sleep(1)


@util.export
class VMDownWaiter(base.Base):
    """
    VM down waiting utility.
    """

    POLLING_INTERVAL = 5

    def __init__(self, environment):
        super(VMDownWaiter, self).__init__()
        self.environment = environment

    def wait(self):
        serv = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        down = False
        destroyed = False
        while not down:
            time.sleep(self.POLLING_INTERVAL)
            self.logger.debug('Waiting for VM down')
            response = serv.s.getVmStats(
                self.environment[ohostedcons.VMEnv.VM_UUID]
            )
            code = response['status']['code']
            message = response['status']['message']
            self.logger.debug(message)
            if code == 0:
                stats = response['statsList'][0]
                down = (stats['status'] == 'Down')
            elif code == 1:
                #assuming VM destroyed
                down = True
                destroyed = True
            else:
                raise RuntimeError(_('Error acquiring VM status'))
        return destroyed


@util.export
class DomainMonitorWaiter(base.Base):
    """
    VM down waiting utility.
    """

    POLLING_INTERVAL = 5

    def __init__(self, environment):
        super(DomainMonitorWaiter, self).__init__()
        self.environment = environment

    def wait(self, sdUUID):
        serv = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        acquired = False
        while not acquired:
            time.sleep(self.POLLING_INTERVAL)
            self.logger.debug('Waiting for domain monitor')
            response = serv.s.getVdsStats()
            self.logger.debug(response)
            if response['status']['code'] != 0:
                self.logger.debug(response['status']['message'])
                raise RuntimeError(_('Error acquiring VDS status'))
            try:
                domains = response['info']['storageDomains']
                acquired = domains[sdUUID]['acquired']
            except KeyError:
                self.logger.debug(
                    'Error getting VDS status',
                    exc_info=True,
                )
                raise RuntimeError(_('Error acquiring VDS status'))


# vim: expandtab tabstop=4 shiftwidth=4
