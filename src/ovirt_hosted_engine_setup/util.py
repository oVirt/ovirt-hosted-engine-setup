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
import glob
import os
import random
import re
import time


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


def get_volume_path(type, sd_uuid, img_uuid, vol_uuid):
    """
    Return path of the volume file inside the domain
    """
    volume_path = ohostedcons.FileLocations.SD_MOUNT_PARENT_DIR
    if type == 'glusterfs':
        volume_path = os.path.join(
            volume_path,
            'glusterSD',
        )
    volume_path = os.path.join(
        volume_path,
        '*',
        sd_uuid,
        'images',
        img_uuid,
        vol_uuid,
    )
    volumes = glob.glob(volume_path)
    if not volumes:
        raise RuntimeError(
            'Path to volume {vol_uuid} not found in {root}'.format(
                vol_uuid=vol_uuid,
                root=ohostedcons.FileLocations.SD_MOUNT_PARENT_DIR,
            )
        )
    return volumes[0]


def task_wait(cli, logger):
    wait = True
    while wait:
        if logger:
            logger.debug('Waiting for existing tasks to complete')
        statuses = cli.getAllTasksStatuses()
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
                cli.clearTask(taskID)
        if all_completed:
            wait = False
        else:
            time.sleep(1)


def create_prepare_image(
        logger,
        cli,
        volFormat,
        preallocate,
        sdUUID,
        spUUID,
        imgUUID,
        volUUID,
        diskType,
        sizeGB,
        desc
):
    # creates a volume on the storage (SPM verb)
    status = cli.createVolume(
        sdUUID,
        spUUID,
        imgUUID,
        str(int(sizeGB) * pow(2, 30)),
        volFormat,
        preallocate,
        diskType,
        volUUID,
        desc,
    )
    if logger:
        logger.debug(status)
    if status['status']['code'] == 0:
        if logger:
            logger.debug(
                (
                    'Created configuration volume {newUUID}, request was:\n'
                    '- image: {imgUUID}\n'
                    '- volume: {volUUID}'
                ).format(
                    newUUID=status['status']['message'],
                    imgUUID=imgUUID,
                    volUUID=volUUID,
                )
            )
    else:
        raise RuntimeError(status['status']['message'])
    task_wait(cli, logger)
    # Expose the image (e.g., activates the lv) on the host (HSM verb).
    if logger:
        logger.debug('configuration volume: prepareImage')
    response = cli.prepareImage(
        spUUID,
        sdUUID,
        imgUUID,
        volUUID
    )
    if logger:
        logger.debug(response)
    if response['status']['code'] != 0:
        raise RuntimeError(response['status']['message'])


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
