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


"""VDSM helper for hosted engine"""


import argparse
import functools
import sys
import time

from vdsm.client import ServerError

from ovirt_hosted_engine_ha.lib import util as ohautil

from ovirt_hosted_engine_setup import vmconf

VNC_PORT_TIMEOUT = 30


def handle_server_error(f):
    @functools.wraps(f)
    def func(*args, **kwargs):
        try:
            f(*args, **kwargs)
        except ServerError as e:
            sys.stderr.write(str(e) + '\n')
            sys.exit(1)

    return func


@handle_server_error
def create(args):
    vm_params = vmconf.parseVmConfFile(args.filename)

    # Send only libvirt xml if it is present in the vm.conf
    xml = vm_params.get('xml')

    cli = ohautil.connect_vdsm_json_rpc()

    try:
        response = cli.VM.create(
            vmID=vm_params['vmId'],
            vmParams={'xml': xml} if xml is not None else vm_params
        )
        if response['status'] != "WaitForLaunch":
            sys.stderr.write('VM failed to launch in the create function\n')
            sys.exit(1)

    except ServerError as e:
        sys.stderr.write(str(e) + '\n')
        sys.exit(1)


@handle_server_error
def destroy(args):
    cli = ohautil.connect_vdsm_json_rpc()
    cli.VM.destroy(vmID=args.vmid)


@handle_server_error
def shutdown(args):
    cli = ohautil.connect_vdsm_json_rpc()
    cli.VM.shutdown(
        vmID=args.vmid,
        delay=args.delay,
        message=args.message,
    )


@handle_server_error
def checkVmStatus(args):
    cli = ohautil.connect_vdsm_json_rpc()
    vmstats = cli.VM.getStats(vmID=args.vmid)[0]
    print(vmstats['status'])


@handle_server_error
def setVmTicket(args):
    cli = ohautil.connect_vdsm_json_rpc()
    cli.VM.updateDevice(
        vmID=args.vmid,
        params={
            'deviceType': 'graphics',
            'existingConnAction': 'keep',
            'graphicsType': 'vnc',
            'params': {},
            'ttl': args.ttl,
            'password': args.password,
        }
    )
    vnc_port = None
    delay = 1
    t = VNC_PORT_TIMEOUT
    while not vnc_port and t > 0:
        t = t - delay
        vmstats = cli.VM.getStats(
            vmID=args.vmid,
        )
        displayinfo = vmstats[0]['displayInfo']
        vnc = [x for x in displayinfo if x['type'] == 'vnc']
        if vnc:
            try:
                vnc_p_i = int(vnc[0]['port'])
            except ValueError:
                vnc_p_i = 0
            if vnc_p_i > 0:
                vnc_port = vnc[0]['port']
        if not vnc_port:
            time.sleep(t)

    if vnc_port:
        print(
            (
                "You can now connect the hosted-engine VM with VNC at "
                "{ip}:{port}"
            ).format(
                ip=vnc[0]['ipAddress'],
                port=vnc_port,
            )
        )
    else:
        sys.stderr.write('Failed detecting VNC port\n')
        sys.exit(1)


def _add_vmid_argument(parser):
    parser.add_argument(
        'vmid',
        help='The UUID of the target VM'
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='VDSM helper for hosted engine'
    )
    subparsers = parser.add_subparsers(title="commands")

    checkvmstatus_parser = subparsers.add_parser(
        'checkVmStatus',
        help='check VM status'
    )
    checkvmstatus_parser.set_defaults(command=checkVmStatus)
    _add_vmid_argument(checkvmstatus_parser)

    create_parser = subparsers.add_parser(
        'create',
        help='create VM'
    )
    create_parser.set_defaults(command=create)
    create_parser.add_argument(
        'filename',
        help='A file containing the vm definition'
    )

    destroy_parser = subparsers.add_parser(
        'destroy',
        help='destroy VM'
    )
    destroy_parser.set_defaults(command=destroy)
    _add_vmid_argument(destroy_parser)

    shutdown_parser = subparsers.add_parser(
        'shutdown',
        help='shutdown VM'
    )
    shutdown_parser.set_defaults(command=shutdown)
    _add_vmid_argument(shutdown_parser)
    shutdown_parser.add_argument(
        'delay',
        help='grace period (seconds) to let guest user close his applications'
    )
    shutdown_parser.add_argument(
        'message',
        help='message to be shown to guest user before shutting down his VM'
    )

    setVmTicket_parser = subparsers.add_parser(
        'setVmTicket',
        help='Set the ticket (password) to be used to connect to a VM display'
    )
    setVmTicket_parser.set_defaults(command=setVmTicket)
    _add_vmid_argument(setVmTicket_parser)
    setVmTicket_parser.add_argument(
        'password',
        help='new password'
    )
    setVmTicket_parser.add_argument(
        'ttl',
        help='ticket lifetime (seconds)'
    )

    args = parser.parse_args()
    args.command(args)
    # force module de-import to close the globally
    # shared json rpc client in the right order
    del sys.modules["ovirt_hosted_engine_ha.lib.util"]


# vim: expandtab tabstop=4 shiftwidth=4
