#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2015 Red Hat, Inc.
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


""" HEConf lib"""


import os
import subprocess
import tarfile
import tempfile

from io import StringIO

from . import constants as ohostedcons
from ovirt_hosted_engine_setup import config as ohostedconfig

_CONF_FILES = [
    ohostedcons.FileLocations.HECONFD_VERSION,
    ohostedcons.FileLocations.HECONFD_ANSWERFILE,
    ohostedcons.FileLocations.HECONFD_HECONF,
    ohostedcons.FileLocations.HECONFD_BROKER_CONF,
    ohostedcons.FileLocations.HECONFD_VM_CONF,
]


def _add_to_tar(tar, fname, content):
    value = StringIO(unicode(content))
    info = tarfile.TarInfo(name=fname)
    value.seek(0, os.SEEK_END)
    info.size = value.tell()
    value.seek(0, os.SEEK_SET)
    tar.addfile(tarinfo=info, fileobj=value)


def _dd_pipe_tar(logger, path, tar_parameters):
    cmd_dd_list = [
        'dd',
        'if={source}'.format(source=path),
        'bs=4k',
    ]
    cmd_tar_list = ['tar', ]
    cmd_tar_list.extend(tar_parameters)
    if logger:
        logger.debug("executing: '{cmd}'".format(cmd=' '.join(cmd_dd_list)))
        logger.debug("executing: '{cmd}'".format(cmd=' '.join(cmd_tar_list)))
    dd_pipe = subprocess.Popen(
        cmd_dd_list,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    tar_pipe = subprocess.Popen(
        cmd_tar_list,
        stdin=dd_pipe.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Allow dd_pipe to receive a SIGPIPE if tar_pipe exits.
    dd_pipe.stdout.close()
    stdout, stderr = tar_pipe.communicate()
    tar_pipe.wait()
    if logger:
        logger.debug('stdout: ' + str(stdout))
        logger.debug('stderr: ' + str(stderr))
    return tar_pipe.returncode, stdout, stderr


def validateConfImage(logger, imagepath):
    """
    Validates the HE configuration image
    :param logger: a logging instance, None if not needed
    :param imagepath: the path of the HE configuration image on your system
                      it can be obtained with
                      ovirt_hosted_engine_setup.util.get_volume_path
    :returns: True if valid, False otherwise
    :type: Boolean
    """
    rc, stdout, stderr = _dd_pipe_tar(logger, imagepath, ['-tvf', '-', ])
    if rc != 0:
        return False
    for f in _CONF_FILES:
        if f not in stdout:
            if logger:
                logger.debug(
                    "'{f}' is not stored in the HE configuration image".format(
                        f=f
                    )
                )
            return False
    return True


def extractConfFile(logger, imagepath, file):
    """
    Extracts a single configuration file from the HE configuration image
    :param logger: a logging instance, None if not needed
    :param imagepath: the path of the HE configuration image on your system
                      it can be obtained with
                      ovirt_hosted_engine_setup.util.get_volume_path
    :param file: the file you ar asking for; valid values are:
                 ohostedcons.FileLocations.HECONFD_VERSION,
                 ohostedcons.FileLocations.HECONFD_ANSWERFILE,
                 ohostedcons.FileLocations.HECONFD_HECONF,
                 ohostedcons.FileLocations.HECONFD_BROKER_CONF,
                 ohostedcons.FileLocations.HECONFD_VM_CONF
    :returns: The content of the file you asked for, None on errors
    :type: String or None
    """
    if logger:
        logger.debug(
            "extracting '{file}' from '{imagepath}'".format(
                file=file,
                imagepath=imagepath,
            )
        )
    if file not in _CONF_FILES:
        if logger:
            logger.debug(
                "'{file}' is not in the HE configuration image".format(
                )
            )
        return None
    rc, stdout, stderr = _dd_pipe_tar(logger, imagepath, ['-xOf', '-', file, ])
    if rc != 0:
        return None
    return stdout


def create_heconfimage(
        logger,
        answefile_content,
        heconf_content,
        broker_conf_content,
        vm_conf_content,
        dest,
):
    """
    Re-Creates the whole HE configuration image on the specified path
    :param logger: a logging instance, None if not needed
    :param answefile_content: the whole content of
                              ohostedcons.FileLocations.HECONFD_ANSWERFILE
                              as a String
    :param heconf_content: the whole content of
                           ohostedcons.FileLocations.HECONFD_HECONF
                           as a String
    :param broker_conf_content: the whole content of
                                ohostedcons.FileLocations.HECONFD_BROKER_CONF
                                as a String
    :param vm_conf_content: the whole content of
                            ohostedcons.FileLocations.HECONFD_VM_CONF
                            as a String
    :param dest: the path of the HE configuration image on your system
                 it can be obtained with
                 ovirt_hosted_engine_setup.util.get_volume_path
    """
    tempdir = tempfile.gettempdir()
    fd, _tmp_tar = tempfile.mkstemp(
        suffix='.tar',
        dir=tempdir,
    )
    os.close(fd)
    if logger:
        logger.debug('temp tar file: ' + _tmp_tar)
    tar = tarfile.TarFile(name=_tmp_tar, mode='w')
    _add_to_tar(
        tar,
        ohostedcons.FileLocations.HECONFD_VERSION,
        ohostedconfig.PACKAGE_VERSION,
    )
    _add_to_tar(
        tar,
        ohostedcons.FileLocations.HECONFD_ANSWERFILE,
        answefile_content,
    )
    _add_to_tar(
        tar,
        ohostedcons.FileLocations.HECONFD_HECONF,
        heconf_content,
    )
    _add_to_tar(
        tar,
        ohostedcons.FileLocations.HECONFD_BROKER_CONF,
        broker_conf_content,
    )
    _add_to_tar(
        tar,
        ohostedcons.FileLocations.HECONFD_VM_CONF,
        vm_conf_content,
    )
    tar.close()

    if logger:
        logger.debug('saving on: ' + dest)

    cmd_list = [
        'dd',
        'if={source}'.format(source=_tmp_tar),
        'of={dest}'.format(dest=dest),
        'bs=4k',
    ]
    if logger:
        logger.debug("executing: '{cmd}'".format(cmd=' '.join(cmd_list)))
    pipe = subprocess.Popen(
        cmd_list,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = pipe.communicate()
    pipe.wait()
    if logger:
        logger.debug('stdout: ' + str(stdout))
        logger.debug('stderr: ' + str(stderr))
    os.unlink(_tmp_tar)
    if pipe.returncode != 0:
        raise RuntimeError('Unable to write HEConfImage')


# vim: expandtab tabstop=4 shiftwidth=4
