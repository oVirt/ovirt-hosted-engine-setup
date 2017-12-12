
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


"""Ansible Utils"""


import gettext
import json
import os
import subprocess
import tempfile

from otopi import base

from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


class AnsibleHelper(base.Base):

    def __init__(
        self,
        playbook_name,
        custom_path=None,
        extra_vars={},
        inventory_source='localhost,',
        raise_on_error=True,
    ):
        super(AnsibleHelper, self).__init__()
        self._playbook_name = playbook_name
        self._module_path = custom_path if custom_path \
            else ohostedcons.FileLocations.HOSTED_ENGINE_ANSIBLE_PATH
        self._inventory_source = inventory_source
        self._extra_vars = extra_vars
        self._cb_results = {}
        self._raise_on_error = raise_on_error

    def _process_output(self, d):
        try:
            data = json.loads(d)
            if (
                ohostedcons.AnsibleCallback.TYPE in data and
                ohostedcons.AnsibleCallback.BODY in data
            ):
                t = data[ohostedcons.AnsibleCallback.TYPE]
                b = data[ohostedcons.AnsibleCallback.BODY]
                if t == ohostedcons.AnsibleCallback.DEBUG:
                    self.logger.debug(b)
                elif t == ohostedcons.AnsibleCallback.WARNING:
                    self.logger.warning(b)
                elif t == ohostedcons.AnsibleCallback.ERROR:
                    self.logger.error(b)
                elif t == ohostedcons.AnsibleCallback.INFO:
                    self.logger.info(b)
                elif t == ohostedcons.AnsibleCallback.RESULT:
                    self._cb_results = b
                else:
                    self.logger.error(_('Unknown data type: {t}').format(t=t))
        except Exception as e:
            self.logger.error(
                _('Failed decoding json data: {e} - "{b}"').format(
                    e=str(e),
                    b=b,
                )
            )

    def run(self):
        out_fd, out_path = tempfile.mkstemp()
        vars_fd, vars_path = tempfile.mkstemp()
        self.logger.debug('out_path: {p}'.format(p=out_path))
        self.logger.debug('vars_path: {p}'.format(p=vars_path))

        env = os.environ.copy()
        env[ohostedcons.AnsibleCallback.OTOPI_CALLBACK_OF] = out_path
        env[
            'ANSIBLE_CALLBACK_WHITELIST'
        ] = ohostedcons.AnsibleCallback.CALLBACK_NAME
        env[
            'ANSIBLE_STDOUT_CALLBACK'
        ] = ohostedcons.AnsibleCallback.CALLBACK_NAME

        rc = None
        with open(vars_path, 'w') as vars_fh:
            json.dump(self._extra_vars, vars_fh)
        with open(out_path, 'r') as out_fh:
            buffer = ''
            proc = subprocess.Popen(
                [
                    '/bin/ansible-playbook',
                    '--module-path={mp}'.format(mp=self._module_path),
                    '--inventory={i}'.format(i=self._inventory_source),
                    '--extra-vars=@{vf}'.format(vf=vars_path),
                    '{pname}'.format(
                        pname=os.path.join(
                            self._module_path,
                            self._playbook_name
                        )
                    ),
                ],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            while True:
                output = out_fh.readline()
                if output == '' and proc.poll() is not None:
                    break
                if output:
                    buffer += output
                    if buffer[-1] == '\n':
                        self._process_output(buffer)
                        buffer = ''
            rc = proc.poll()
            self.logger.debug('ansible-playbook rc: {rc}'.format(rc=rc))
            while True:
                output = out_fh.readline()
                if output == '':
                    break
                if output:
                    self._process_output(output)
            self.logger.debug('ansible-playbook stdout:')
            for ln in proc.stdout:
                self.logger.debug(ln)
            self.logger.debug('ansible-playbook stderr:')
            for ln in proc.stderr:
                self.logger.error(ln)
            if rc != 0 and self._raise_on_error:
                raise RuntimeError(_('Failed executing ansible-playbook'))
        os.unlink(out_path)
        os.unlink(vars_path)
        return self._cb_results


# vim: expandtab tabstop=4 shiftwidth=4
