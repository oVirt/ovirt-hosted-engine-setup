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


"""Utils."""


import os
import random


from otopi import util


from . import constants as ohostedcons


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
