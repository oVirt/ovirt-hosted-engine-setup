#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2017 Red Hat, Inc.
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

import os
import vmconf

TEST_FILE = os.path.join(
    os.path.dirname(__file__),
    'vm_test.conf'
)

EXPECTED_VM_CONF_DICT = {
    'cpuType': 'SandyBridge',
    'emulatedMachine': 'pc',
    'vmId': '82a24281-8a25-4772-b9c9-45971e811cb3',
    'devices': [
        {
            'index': '2',
            'iface': 'ide',
            'shared': 'false',
            'specParams': {},
            'readonly': 'true',
            'deviceId': '55aab7ab-7ad7-4b8b-be58-a17295d00782',
            'address': {
                'bus': '1',
                'controller': '0',
                'type': 'drive',
                'target': '0',
                'unit': '0'
            },
            'device': 'cdrom',
            'path': '',
            'type': 'disk'
        },
        {
            'index': '0',
            'iface': 'virtio',
            'bootOrder': '1',
            'format': 'raw',
            'type': 'disk',
            'address': {
                'slot': '0x06',
                'bus': '0x00',
                'domain': '0x0000',
                'type': 'pci',
                'function': '0x0'
            },
            'volumeID': '19cc3c17-5c81-4750-b807-09db88a67ad5',
            'imageID': 'f270b541-a113-4815-b72e-b0ec3e1ed6b6',
            'specParams': {},
            'readonly': 'false',
            'domainID': '2164faa8-b18b-4036-b686-5a6eec95081b',
            'deviceId': 'f270b541-a113-4815-b72e-b0ec3e1ed6b6',
            'poolID': '00000000-0000-0000-0000-000000000000',
            'device': 'disk',
            'shared': 'exclusive',
            'propagateErrors': 'off',
            'optional': 'false'
        },
        {
            'device': 'scsi',
            'model': 'virtio-scsi',
            'type': 'controller'
        },
        {
            'nicModel': 'pv',
            'macAddr': '00:16:3e:35:83:68',
            'linkActive': 'true',
            'network': 'ovirtmgmt',
            'specParams': {},
            'deviceId': '7dceb6c4-f555-4da0-a0b5-26ce9ef66c73',
            'address': {
                'slot': '0x03',
                'bus': '0x00',
                'domain': '0x0000',
                'type': 'pci',
                'function': '0x0'
            },
            'device': 'bridge',
            'type': 'interface'
        },
        {
            'device': 'console',
            'specParams': {},
            'type': 'console',
            'deviceId': '64170743-d86f-4c32-810b-5ff9e540eed0',
            'alias': 'console0'
        },
        {
            'device': 'vga',
            'alias': 'video0',
            'type': 'video'
        },
        {
            'device': 'vnc',
            'type': 'graphics'
        },
        {
            'device': 'virtio',
            'specParams': {
                'source': 'random'
            },
            'model': 'virtio',
            'type': 'rng'
        }
    ],
    'smp': '4',
    'memSize': '4096',
    'maxVCpus': '4',
    'spiceSecureChannels': (
        'smain,'
        'sdisplay,'
        'sinputs,'
        'scursor,'
        'splayback,'
        'srecord,'
        'ssmartcard,'
        'susbredir'
    ),
    'vmName': 'HostedEngine',
    'display': 'vnc'
}


def testParseVmConfFile():
    # test parsing a sample configuration file
    params = vmconf.parseVmConfFile(TEST_FILE)
    assert params == EXPECTED_VM_CONF_DICT


# vim: expandtab tabstop=4 shiftwidth=4
