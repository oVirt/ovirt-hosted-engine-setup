#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2013-2015 Red Hat, Inc.
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

    POWER_MAX_TRIES = 10
    POWER_DELAY = 1
    TICKET_MAX_TRIES = 10
    TICKET_DELAY = 1
    POWEROFF_CHECK_INTERVALL = 1

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
        cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        try:
            stats = cli.getVmStats(
                self.environment[ohostedcons.VMEnv.VM_UUID]
            )
            self.logger.debug(stats)
            if stats['status']['code'] != 0:
                self.logger.error(stats['status']['message'])
            else:
                statsList = stats['statsList'][0]
                displaySecurePort = statsList.get(
                    'displaySecurePort', displaySecurePort
                )
                displayPort = statsList.get('displayPort', displayPort)
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
        # TODO: check if we can move this to configurevm.py
        # and get rid of the template.
        conf = {
            'vmId': self.environment[ohostedcons.VMEnv.VM_UUID],
            'memSize': self.environment[ohostedcons.VMEnv.MEM_SIZE_MB],
            'display': self.environment[ohostedcons.VMEnv.CONSOLE_TYPE],
            'emulatedMachine': self.environment[
                ohostedcons.VMEnv.EMULATED_MACHINE
            ],
            'cpuType': self.environment[
                ohostedcons.VDSMEnv.VDSM_CPU
            ].replace('model_', ''),
            'spiceSecureChannels': (
                'smain,sdisplay,sinputs,scursor,splayback,'
                'srecord,ssmartcard,susbredir'
            ),
            'vmName': ohostedcons.Const.HOSTED_ENGINE_VM_NAME,
            'smp': self.environment[ohostedcons.VMEnv.VCPUS],
            'devices': [
                {
                    'device': 'scsi',
                    'model': 'virtio-scsi',
                    'type': 'controller'
                },
                {
                    'device': 'console',
                    'specParams': {},
                    'type': 'console',
                    'deviceId': self.environment[
                        ohostedcons.VMEnv.CONSOLE_UUID
                    ],
                    'alias': 'console0'
                },
            ],
        }
        cdrom = {
            'index': '2',
            'iface': 'ide',
            'address': {
                'controller': '0',
                'target': '0',
                'unit': '0',
                'bus': '1',
                'type': 'drive'
            },
            'specParams': {},
            'readonly': 'true',
            'deviceId': self.environment[ohostedcons.VMEnv.CDROM_UUID],
            'path': (
                self.environment[ohostedcons.VMEnv.SUBST]['@CDROM@']
                if self.environment[ohostedcons.VMEnv.SUBST]['@CDROM@'] != ''
                else ''
            ),
            'device': 'cdrom',
            'shared': 'false',
            'type': 'disk',
        }
        if self.environment[
            ohostedcons.VMEnv.SUBST
        ]['@BOOT_CDROM@'] == ',bootOrder:1':
            cdrom['bootOrder'] = '1'
        conf['devices'].append(cdrom)
        disk = {
            'index': '0',
            'iface': 'virtio',
            'format': 'raw',
            'poolID': ohostedcons.Const.BLANK_UUID,
            'volumeID': self.environment[ohostedcons.StorageEnv.VOL_UUID],
            'imageID': self.environment[ohostedcons.StorageEnv.IMG_UUID],
            'specParams': {},
            'readonly': 'false',
            'domainID': self.environment[ohostedcons.StorageEnv.SD_UUID],
            'optional': 'false',
            'deviceId': self.environment[ohostedcons.StorageEnv.IMG_UUID],
            'address': {
                'bus': '0x00',
                'slot': '0x06',
                'domain': '0x0000',
                'type': 'pci',
                'function': '0x0'
            },
            'device': 'disk',
            'shared': 'exclusive',
            'propagateErrors': 'off',
            'type': 'disk',
        }
        if self.environment[
            ohostedcons.VMEnv.SUBST
        ]['@BOOT_DISK@'] == ',bootOrder:1':
            disk['bootOrder'] = '1'
        conf['devices'].append(disk)
        nic = {
            'nicModel': 'pv',
            'macAddr': self.environment[ohostedcons.VMEnv.MAC_ADDR],
            'linkActive': 'true',
            'network': self.environment[ohostedcons.NetworkEnv.BRIDGE_NAME],
            'filter': 'vdsm-no-mac-spoofing',
            'specParams': {},
            'deviceId': self.environment[ohostedcons.VMEnv.NIC_UUID],
            'address': {
                'bus': '0x00',
                'slot': '0x03',
                'domain': '0x0000',
                'type': 'pci',
                'function': '0x0'
            },
            'device': 'bridge',
            'type': 'interface',
        }
        if self.environment[
            ohostedcons.VMEnv.SUBST
        ]['@BOOT_PXE@'] == ',bootOrder:1':
            nic['bootOrder'] = '1'
        conf['devices'].append(nic)

        cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        status = cli.create(conf)
        self.logger.debug(status)
        if status['status']['code'] != 0:
            raise RuntimeError(
                _(
                    'Cannot create the VM: {message}'
                ).format(
                    message=status['status']['message']
                )
            )
        # Now it's in WaitForLaunch, need to be on powering up
        powering = False
        tries = self.POWER_MAX_TRIES
        while not powering and tries > 0:
            tries -= 1
            stats = cli.getVmStats(
                self.environment[ohostedcons.VMEnv.VM_UUID]
            )
            self.logger.debug(stats)
            if stats['status']['code'] != 0:
                raise RuntimeError(stats['status']['message'])
            else:
                statsList = stats['statsList'][0]
                if statsList['status'] in ('Powering up', 'Up'):
                    powering = True
                elif statsList['status'] == 'Down':
                    # VM creation failure
                    tries = 0
                else:
                    time.sleep(self.POWER_DELAY)
        if not powering:
            raise RuntimeError(
                _(
                    'The VM is not powering up: please check VDSM logs'
                )
            )

        password_set = False
        tries = self.TICKET_MAX_TRIES
        while not password_set and tries > 0:
            tries -= 1
            status = cli.setVmTicket(
                self.environment[ohostedcons.VMEnv.VM_UUID],
                self.environment[ohostedcons.VMEnv.VM_PASSWD],
                self.environment[
                    ohostedcons.VMEnv.VM_PASSWD_VALIDITY_SECS
                ],
            )
            self.logger.debug(status)
            if status['status']['code'] == 0:
                password_set = True
            else:
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
        cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        res = cli.destroy(self.environment[ohostedcons.VMEnv.VM_UUID])
        self.logger.debug(res)

    def _wait_vm_destroyed(self):
        waiter = tasks.VMDownWaiter(self.environment)
        return waiter.wait()
