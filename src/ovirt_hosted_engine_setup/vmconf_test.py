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

from . import vmconf

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
    'display': 'vnc',
    'xml': b'<?xml version="1.0" encoding="UTF-8"?><domain type="kvm" '
           b'xmlns:ovirt-tune="http://ovirt.org/vm/tune/1.0" '
           b'xmlns:ovirt-vm="http://ovirt.org/vm/1.0"><name>HostedEngine'
           b'</name><uuid>dbc9d98d-4a5c-4e4e-bc9b-621b189709fd</uuid><memory>'
           b'2097152</memory><currentMemory>2097152</currentMemory><maxMemory '
           b'slots="16">8390656</maxMemory><vcpu current="2">16</vcpu><sysinfo'
           b' type="smbios"><system><entry name="manufacturer">oVirt</entry>'
           b'<entry name="product">OS-NAME:</entry><entry name="version">'
           b'OS-VERSION:</entry><entry name="serial">HOST-SERIAL:</entry>'
           b'<entry name="uuid">dbc9d98d-4a5c-4e4e-bc9b-621b189709fd</entry>'
           b'</system></sysinfo><clock offset="variable" adjustment="0"><timer'
           b' name="rtc" tickpolicy="catchup"></timer><timer name="pit" '
           b'tickpolicy="delay"></timer><timer name="hpet" present="no">'
           b'</timer></clock><features><acpi></acpi></features><cpu '
           b'match="exact"><model>Nehalem</model><topology cores="1" '
           b'threads="1" sockets="16"></topology><numa><cell cpus="0,1" '
           b'memory="2097152"></cell></numa></cpu><cputune></cputune><devices>'
           b'<input type="tablet" bus="usb"></input><channel type="unix">'
           b'<target type="virtio" name="ovirt-guest-agent.0"></target><source'
           b' mode="bind" path="/var/lib/libvirt/qemu/channels/'
           b'dbc9d98d-4a5c-4e4e-bc9b-621b189709fd.ovirt-guest-agent.0">'
           b'</source></channel><channel type="unix"><target type="virtio" '
           b'name="org.qemu.guest_agent.0"></target><source mode="bind" '
           b'path="/var/lib/libvirt/qemu/channels/dbc9d98d-4a5c-4e4e-bc9b-'
           b'621b189709fd.org.qemu.guest_agent.0"></source></channel><console '
           b'type="pty"><target type="virtio" port="0"></target></console>'
           b'<controller type="virtio-serial" index="0" ports="16"><address '
           b'bus="0x00" domain="0x0000" function="0x0" slot="0x05" type="pci">'
           b'</address></controller><graphics type="vnc" port="-1" '
           b'autoport="yes" passwd="*****" passwdValidTo="1970-01-01T00:00:01"'
           b' keymap="en-us"><listen type="network" network="vdsm-ovirtmgmt">'
           b'</listen></graphics><controller type="usb" model="piix3-uhci" '
           b'index="0"><address bus="0x00" domain="0x0000" function="0x2" '
           b'slot="0x01" type="pci"></address></controller><controller '
           b'type="scsi" model="virtio-scsi" index="0"><address bus="0x00" '
           b'domain="0x0000" function="0x0" slot="0x04" type="pci"></address>'
           b'</controller><controller type="ide" index="0"><address bus="0x00"'
           b' domain="0x0000" function="0x1" slot="0x01" type="pci"></address>'
           b'</controller><memballoon model="none"></memballoon><disk '
           b'type="file" device="cdrom" snapshot="no"><driver name="qemu" '
           b'type="raw" error_policy="report"></driver><source file="" '
           b'startupPolicy="optional"></source><target dev="hdc" bus="ide">'
           b'</target><readonly></readonly><address bus="1" controller="0" '
           b'unit="0" type="drive" target="0"></address></disk><disk '
           b'snapshot="no" type="file" device="disk"><target dev="vda" '
           b'bus="virtio"></target><source file="/rhev/data-center/'
           b'5a609fd1-0299-0052-0087-0000000003bd/19e6c946-f8c1-4d38-845c-'
           b'883e7478876b/images/42af46eb-571c-4aaa-be73-0cca671147e1/'
           b'b5aa283c-7646-4d61-9669-ed6a52556b30"></source><driver '
           b'name="qemu" io="threads" type="raw" error_policy="stop" '
           b'cache="none"></driver><address bus="0x00" domain="0x0000" '
           b'function="0x0" slot="0x06" type="pci"></address><serial>'
           b'42af46eb-571c-4aaa-be73-0cca671147e1</serial></disk></devices>'
           b'<pm><suspend-to-disk enabled="no"></suspend-to-disk>'
           b'<suspend-to-mem enabled="no"></suspend-to-mem></pm><os><type '
           b'arch="x86_64" machine="pc-i440fx-rhel7.3.0">hvm</type><smbios '
           b'mode="sysinfo"></smbios></os><metadata><ovirt-tune:qos>'
           b'</ovirt-tune:qos><ovirt-vm:vm><minGuaranteedMemoryMb type="int">'
           b'2048</minGuaranteedMemoryMb><clusterVersion>4.2</clusterVersion>'
           b'<ovirt-vm:custom></ovirt-vm:custom><ovirt-vm:device '
           b'devtype="disk" name="vda"><ovirt-vm:imageID>42af46eb-571c-4aaa-'
           b'be73-0cca671147e1</ovirt-vm:imageID><ovirt-vm:poolID>5a609fd1-'
           b'0299-0052-0087-0000000003bd</ovirt-vm:poolID><ovirt-vm:volumeID>'
           b'b5aa283c-7646-4d61-9669-ed6a52556b30</ovirt-vm:volumeID>'
           b'<ovirt-vm:domainID>19e6c946-f8c1-4d38-845c-883e7478876b'
           b'</ovirt-vm:domainID></ovirt-vm:device><launchPaused>false'
           b'</launchPaused><resumeBehavior>auto_resume</resumeBehavior>'
           b'</ovirt-vm:vm></metadata></domain>'
}


def testParseVmConfFile():
    # test parsing a sample configuration file
    params = vmconf.parseVmConfFile(TEST_FILE)
    assert params == EXPECTED_VM_CONF_DICT


# vim: expandtab tabstop=4 shiftwidth=4
