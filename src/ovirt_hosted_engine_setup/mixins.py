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

"""VM Utils"""

import string
import random
import gettext
import time

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import tasks


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


class VmOperations(object):
    """
    Hosted engine VM manipulation features for otopi Plugin objects
    """

    TICKET_MAX_TRIES = 10
    TICKET_DELAY = 1
    POWEROFF_CHECK_INTERVALL = 1

    @property
    def _vdscommand(self):
        if not hasattr(self, '_vdscommand_val'):
            self._vdscommand_val = [self.command.get('vdsClient')]
            if self.environment[ohostedcons.VDSMEnv.USE_SSL]:
                self._vdscommand_val.append('-s')
            self._vdscommand_val.append('localhost')
        return self._vdscommand_val

    def _generateTempVncPassword(self):
        self.logger.info(
            _('Generating a temporary VNC password.')
        )
        return '%s%s' % (
            ''.join([random.choice(string.digits) for _i in range(4)]),
            ''.join([random.choice(string.letters) for _i in range(4)]),
        )

    def _generateUserMessage(self, console_type):
        displayPort = 5900
        displaySecurePort = 5901
        serv = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        try:
            stats = serv.s.getVmStats(
                self.environment[ohostedcons.VMEnv.VM_UUID]
            )
            self.logger.debug(stats)
            if not stats['status']['code'] == 0:
                self.logger.error(stats['status']['message'])
            else:
                statsList = stats['statsList'][0]
                displaySecurePort = statsList['displaySecurePort']
                displayPort = statsList['displayPort']
        except Exception:
            self.logger.debug(
                'Error getting VM stats',
                exc_info=True,
            )
        if console_type == 'vnc':
            return _(
                'You can now connect to the VM with the following command:\n'
                '\t{remote} vnc://localhost:{displayPort}\n'
                'Use temporary password "{password}" '
                'to connect to vnc console.\n'
            ).format(
                remote=self.command.get('remote-viewer'),
                password=self.environment[
                    ohostedcons.VMEnv.VM_PASSWD
                ],
                displayPort=displayPort
            )
        elif console_type == 'qxl':
            if displaySecurePort < 0:
                displaySecurePort = displayPort
            return _(
                'You can now connect to the VM with the following command:\n'
                '\t{remote} --spice-ca-file={ca_cert} '
                'spice://localhost?tls-port={displaySecurePort} '
                '--spice-host-subject="{subject}"\nUse temporary password '
                '"{password}" to connect to spice console.'
            ).format(
                remote=self.command.get('remote-viewer'),
                ca_cert=ohostedcons.FileLocations.LIBVIRT_SPICE_CA_CERT,
                subject=self.environment[ohostedcons.VDSMEnv.SPICE_SUBJECT],
                password=self.environment[
                    ohostedcons.VMEnv.VM_PASSWD
                ],
                displaySecurePort=displaySecurePort
            )

        else:
            raise RuntimeError(
                _(
                    'Unsuppored console type "{console}" requested'.format(
                        console=console_type
                    )
                )
            )

    def _create_vm(self):
        if not self._wait_vm_destroyed():
            self.logger.warning(
                _(
                    'The Hosted Engine VM has been found still powered on:\n'
                    'please turn it off using "hosted-engine --vm-poweroff".\n'
                    'The system will wait until the VM is powered off.'
                )
            )
            while not self._wait_vm_destroyed():
                time.sleep(self.POWEROFF_CHECK_INTERVALL)

        self.logger.info(_('Creating VM'))
        cmd = self._vdscommand + [
            'create',
            ohostedcons.FileLocations.ENGINE_VM_CONF,
        ]
        self.execute(
            cmd,
            raiseOnError=True
        )
        password_set = False
        tries = self.TICKET_MAX_TRIES
        while not password_set and tries > 0:
            tries -= 1
            try:
                cmd = self._vdscommand + [
                    'setVmTicket',
                    self.environment[ohostedcons.VMEnv.VM_UUID],
                    self.environment[ohostedcons.VMEnv.VM_PASSWD],
                    self.environment[
                        ohostedcons.VMEnv.VM_PASSWD_VALIDITY_SECS
                    ],
                ]
                self.execute(
                    cmd,
                    raiseOnError=True
                )
                password_set = True
            except RuntimeError as e:
                self.logger.debug(str(e))
                time.sleep(self.TICKET_DELAY)
        if not password_set:
            raise RuntimeError(
                _(
                    'Cannot set temporary password for console connection.\n'
                    'The VM may not have been created: please check VDSM logs'
                )
            )
        else:
            self.dialog.note(
                self._generateUserMessage(
                    self.environment[
                        ohostedcons.VMEnv.CONSOLE_TYPE
                    ]
                )
            )
            host = 'localhost'
            spice_values = [
                x.strip()
                for x in self.environment[
                    ohostedcons.VDSMEnv.SPICE_SUBJECT
                ].split(',')
                if x
            ]
            for items in spice_values:
                key, val = items.split('=', 1)
                if key == 'CN':
                    host = val
                    break

            self.dialog.note(
                _(
                    'Please note that in order to use remote-viewer you need '
                    'to be able to run graphical applications.\n'
                    'This means that if you are using ssh you have to supply '
                    'the -Y flag (enables trusted X11 forwarding).\n'
                    'Otherwise you can run the command from a terminal in '
                    'your preferred desktop environment.\n'
                    'If you cannot run graphical applications you can '
                    'connect to the graphic console from another host or '
                    'connect to the console using the following command:\n'
                    'virsh -c qemu+tls://{host}/system console HostedEngine'
                ).format(
                    host=host
                )
            )
            self.dialog.note(
                _(
                    'If you need to reboot the VM you will need to start it '
                    'manually using the command:\n'
                    'hosted-engine --vm-start\n'
                    'You can then set a temporary password using '
                    'the command:\n'
                    'hosted-engine --add-console-password'
                )
            )

    def _destroy_vm(self):
        cmd = self._vdscommand + [
            'destroy',
            self.environment[ohostedcons.VMEnv.VM_UUID]
        ]
        self.execute(cmd, raiseOnError=True)

    def _wait_vm_destroyed(self):
        waiter = tasks.VMDownWaiter(self.environment)
        return waiter.wait()
