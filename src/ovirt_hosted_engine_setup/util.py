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


"""Utils."""


import gettext
import os
import random
import re

from otopi import util

from . import constants as ohostedcons

UNICAST_MAC_ADDR = re.compile("[a-fA-F0-9][02468aAcCeE](:[a-fA-F0-9]{2}){5}")


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
def processTemplate(template, subst):
    content = ''
    with open(template, 'r') as f:
        content = f.read()
    for k, v in subst.items():
        content = content.replace(str(k), str(v))
    return content


def randomMAC():
    mac = [
        '00',
        '16',
        '3e',
        '%02x' % random.randint(0x00, 0x7f),
        '%02x' % random.randint(0x00, 0xff),
        '%02x' % random.randint(0x00, 0xff),
    ]
    return ':'.join(mac)


def validMAC(mac):
    """
    Ensure that mac is a valid unicast MAC address.
    @see: https://bugzilla.redhat.com/1116785
    @see: "http://libvirt.org/git/?
        p=libvirt.git;
        a=commitdiff;
        h=0007237301586aa90f58a7cc8d7cb29a16b00470"
    """
    return (UNICAST_MAC_ADDR.match(mac) is not None)


def check_is_pingable(base, address):
    """
    Ensure that an address is pingable
    """
    rc, stdout, stderr = base.execute(
        (
            base.command.get('ping'),
            '-c',
            '1',
            str(address),
        ),
        raiseOnError=False,
    )
    if rc == 0:
        return True
    return False


def persist(path):
    try:
        from ovirt.node.utils.fs import Config
        cfg = Config()
        cfg.persist(path)
    except ImportError:
        raise RuntimeError(
            'Use ohostedcons.CoreEnv.NODE_SETUP for ensuring module '
            'availability'
        )


def transferImage(base, source_path, destination_path):
    try:
        base.execute(
            (
                base.command.get('sudo'),
                '-u',
                'vdsm',
                '-g',
                'kvm',
                base.command.get('qemu-img'),
                'convert',
                '-O',
                'raw',
                source_path,
                destination_path
            ),
            raiseOnError=True
        )
    except RuntimeError as e:
        base.logger.debug('error uploading the image: ' + str(e))
        return (1, str(e))
    return (0, 'OK')


class VirtUserContext(object):
    """
    Switch to vdsm:kvm user with provided umask
    """

    def __init__(self, environment, umask):
        super(VirtUserContext, self).__init__()
        self.environment = environment
        self._euid = None
        self._egid = None
        self._umask = umask
        self._old_umask = None

    def __enter__(self):
        self._euid = os.geteuid()
        self._egid = os.getegid()
        self._old_umask = os.umask(self._umask)
        os.setegid(self.environment[ohostedcons.VDSMEnv.KVM_GID])
        os.seteuid(self.environment[ohostedcons.VDSMEnv.VDSM_UID])

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.seteuid(self._euid)
        os.setegid(self._egid)
        os.umask(self._umask)


# vim: expandtab tabstop=4 shiftwidth=4
