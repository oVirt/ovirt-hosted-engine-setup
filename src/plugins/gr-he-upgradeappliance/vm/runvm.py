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
VM restart plugin.
"""


import gettext
import os
import re
import tempfile
import time


from otopi import plugin
from otopi import util


from ovirt_hosted_engine_ha.env import config
from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    VM configuration plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._temp_vm_conf = None

    def _createvm(self):
        # TODO: parse the file and use JsonRPC via mixins.py
        self.execute(
            args=(
                self.command.get('vdsClient'),
                '-s',
                '0',
                'create',
                self._temp_vm_conf
            ),
            raiseOnError=True
        )
        POWER_MAX_TRIES = 20
        POWER_DELAY = 3
        cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        # Now it's in WaitForLaunch, need to be on powering up
        powering = False
        tries = POWER_MAX_TRIES
        while not powering and tries > 0:
            tries -= 1
            stats = cli.getVmStats(
                self.environment[ohostedcons.VMEnv.VM_UUID]
            )
            self.logger.debug(stats)
            if stats['status']['code'] != 0:
                raise RuntimeError(stats['status']['message'])
            else:
                statsList = stats['items'][0]
                if statsList['status'] in ('Powering up', 'Up'):
                    powering = True
                elif statsList['status'] == 'Down':
                    # VM creation failure
                    tries = 0
                else:
                    time.sleep(POWER_DELAY)
        if not powering:
            raise RuntimeError(
                _(
                    'The VM is not powering up: please check VDSM logs'
                )
            )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        self.command.detect('vdsClient')

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        name=ohostedcons.Stages.UPGRADED_APPLIANCE_RUNNING,
    )
    def _boot_new_appliance(self):
        try:
            fd, self._temp_vm_conf = tempfile.mkstemp(
                prefix='appliance',
                suffix='.conf',
            )
            os.close(fd)
            _config = config.Config(logger=self.logger)
            _config.refresh_local_conf_file(
                localcopy_filename=self._temp_vm_conf,
                archive_fname=ohostedcons.FileLocations.HECONFD_VM_CONF,
            )

            vm_conf = open(self._temp_vm_conf)
            lines = vm_conf.readlines()
            vm_conf.close()
            # attaching cloud-init iso to configure the new appliance
            plines = []
            for line in lines:
                if 'device:cdrom' in line and 'path:' in line:
                    sline = re.sub(
                        r'path:[^,]*,',
                        'path:{iso},'.format(
                            iso=self.environment[ohostedcons.VMEnv.CDROM]
                        ),
                        line
                    )
                    plines.append(sline)
                else:
                    plines.append(line)
            vm_conf = open(self._temp_vm_conf, 'w')
            vm_conf.writelines(plines)
            vm_conf.close()
        except EnvironmentError as ex:
            self.logger.error(
                _(
                    'Unable to generate the temporary vm.conf file: {msg}'
                ).format(
                    msg=ex.message,
                )
            )
        self._createvm()

    @plugin.event(
        stage=plugin.Stages.STAGE_CLEANUP,
    )
    def _cleanup(self):
        try:
            if (
                self._temp_vm_conf is not None and
                os.path.exists(self._temp_vm_conf)
            ):
                os.unlink(self._temp_vm_conf)
        except EnvironmentError as ex:
            self.logger.error(
                _(
                    'Unable to cleanup the temporary vm.conf file: {msg}'
                ).format(
                    msg=ex.message,
                )
            )


# vim: expandtab tabstop=4 shiftwidth=4
