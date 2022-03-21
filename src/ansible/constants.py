#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2022 Red Hat, Inc.
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


"""Ansible constants."""


# This module contains constants used by both otopi/ovirt-hosted-engine-setup
# code and the ansible callbacks code, which is used by ansible itself.


class Const(object):
    ANSIBLE_R_OTOPI_PREFIX = 'otopi_'


class AnsibleCallback(object):
    DEBUG = 'OVEHOSTED_AC/debug'
    WARNING = 'OVEHOSTED_AC/warning'
    ERROR = 'OVEHOSTED_AC/error'
    INFO = 'OVEHOSTED_AC/info'
    RESULT = 'OVEHOSTED_AC/result'
    TYPE = 'OVEHOSTED_AC/type'
    BODY = 'OVEHOSTED_AC/body'
    OTOPI_CALLBACK_OF = 'OTOPI_CALLBACK_OF'
    CALLBACK_NAME = '1_otopi_json'
    LOGGER_CALLBACK_NAME = '2_ovirt_logger'


# vim: expandtab tabstop=4 shiftwidth=4
