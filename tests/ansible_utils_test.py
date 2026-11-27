#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2026 oVirt Authors
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

"""AnsibleHelper return-code race."""


import importlib
import json
import logging
import os
import sys
import tempfile
import types


def _src_root():
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'src')
    )


def _stub_otopi():
    if 'otopi.util' in sys.modules and 'otopi.base' in sys.modules:
        return

    def identity(obj):
        return obj

    util = types.ModuleType('otopi.util')
    util.export = identity
    util.codegen = identity

    class Base(object):
        def __init__(self):
            self.logger = logging.getLogger('ansible_utils_test')

    base = types.ModuleType('otopi.base')
    base.Base = Base
    otopi = types.ModuleType('otopi')
    otopi.util = util
    otopi.base = base
    sys.modules['otopi'] = otopi
    sys.modules['otopi.util'] = util
    sys.modules['otopi.base'] = base


def _stub_config():
    name = 'ovirt_hosted_engine_setup.config'
    if name in sys.modules:
        return
    config = types.ModuleType(name)
    config.PACKAGE_NAME = 'ovirt-hosted-engine-setup'
    config.PACKAGE_VERSION = 'test'
    config.APPLIANCE_RPM_PREFIX = 'ovirt-engine'
    config.APPLIANCE40_RPM_PREFIX = 'ovirt-engine'
    config.SYSCONFDIR = '/etc'
    config.DATADIR = '/usr/share'
    config.LOCALSTATEDIR = '/var'
    config.DOCDIR = '/usr/share/doc/ovirt-hosted-engine-setup'
    sys.modules[name] = config


def _prepare_imports():
    src = _src_root()
    if src not in sys.path:
        sys.path.insert(0, src)
    try:
        importlib.import_module('otopi.base')
        importlib.import_module('otopi.util')
    except ImportError:
        _stub_otopi()
    try:
        importlib.import_module('ovirt_hosted_engine_setup.config')
    except ImportError:
        _stub_config()


def _modules():
    _prepare_imports()
    callback = importlib.import_module('he_ansible.constants')
    ansible_utils = importlib.import_module(
        'ovirt_hosted_engine_setup.ansible_utils'
    )
    return callback.AnsibleCallback, ansible_utils.AnsibleHelper


def _line(callback, kind, body):
    payload = {
        callback.TYPE: kind,
        callback.BODY: body,
    }
    return json.dumps(payload) + '\n'


def _result_line(callback):
    body = {
        'otopi_localvm_dir': {'path': '/var/tmp/localvmtest'},
    }
    return _line(callback, callback.RESULT, body)


def _recap_line(callback):
    return _line(
        callback,
        callback.DEBUG,
        'PLAY RECAP [localhost] : ok: 214 failed: 0',
    )


class _Proc(object):
    def __init__(self, mode):
        self.mode = mode
        self.stdout = []
        self.stderr = []
        self.returncode = None
        self.polls = 0

    def poll(self):
        self.polls += 1
        if self.mode == 'early':
            if self.polls < 2:
                return None
            self.returncode = 0
            return 0
        if self.returncode is None:
            return None
        return self.returncode


def _run(monkeypatch, mode):
    callback, helper_cls = _modules()
    state = {'path': None, 'wrote': False}
    proc = _Proc(mode)
    module = sys.modules[
        'ovirt_hosted_engine_setup.ansible_utils'
    ]
    real_mkstemp = tempfile.mkstemp

    def closing_mkstemp():
        fd, path = real_mkstemp()
        os.close(fd)
        return fd, path

    def fake_popen(cmd, env=None, stdout=None, stderr=None):
        del cmd, stdout, stderr
        state['path'] = env[callback.OTOPI_CALLBACK_OF]
        if mode == 'early':
            with open(state['path'], 'a') as handle:
                handle.write(_result_line(callback))
                handle.write(_recap_line(callback))
        return proc

    def fake_sleep(_seconds):
        if mode != 'late' or state['wrote']:
            return
        with open(state['path'], 'a') as handle:
            handle.write(_result_line(callback))
            handle.write(_recap_line(callback))
        proc.returncode = 0
        state['wrote'] = True

    monkeypatch.setattr(module.tempfile, 'mkstemp', closing_mkstemp)
    monkeypatch.setattr(module.subprocess, 'Popen', fake_popen)
    monkeypatch.setattr(module.time, 'sleep', fake_sleep)
    helper = helper_cls(raise_on_error=True)
    return helper.run()


def test_result_already_read_keeps_return_code(monkeypatch):
    result = _run(monkeypatch, 'early')
    assert result['ansible-playbook_rc'] == 0
    assert result['otopi_localvm_dir']['path'] == (
        '/var/tmp/localvmtest'
    )


def test_result_written_during_sleep_keeps_return_code(monkeypatch):
    result = _run(monkeypatch, 'late')
    assert result['ansible-playbook_rc'] == 0
    assert result['otopi_localvm_dir']['path'] == (
        '/var/tmp/localvmtest'
    )
