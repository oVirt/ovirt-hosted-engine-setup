
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
import random
import string
import subprocess
import tempfile
import time

from otopi import base

from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')

# TODO do this nicely
_FILTERED_VARS = (
    'ADMIN_PASSWORD',
    'APPLIANCE_PASSWORD',
    'ISCSI_PASSWORD',
    'ISCSI_DISCOVER_PASSWORD',
    'ROOTPWD',
    'he_appliance_password',
    'he_hashed_appliance_password',
    'he_admin_password',
    'he_iscsi_password',
    'he_iscsi_discover_password',
    'ansible_ssh_pass',
)

_FILTERED_REs = (
    'BEGIN PRIVATE KEY(?P<filter>.*)END PRIVATE KEY',
)

_EXTRA_VARS_FOR_FILTERING = {
    'he_filtered_tokens_vars': list(_FILTERED_VARS),
    'he_filtered_tokens_re': list(_FILTERED_REs),
}


class AnsibleHelper(base.Base):

    def __init__(
        self,
        playbook_name=ohostedcons.FileLocations.HE_AP_TRIGGER_ROLE,
        custom_path=None,
        extra_vars={},
        user_extra_vars=None,
        inventory_source='localhost,',
        raise_on_error=True,
        tags=None,
        skip_tags='always',
    ):
        super(AnsibleHelper, self).__init__()
        self._playbook_name = playbook_name
        self._module_path = custom_path if custom_path \
            else ohostedcons.FileLocations.HOSTED_ENGINE_ANSIBLE_PATH
        self._playbook_path = os.path.join(
            self._module_path,
            self._playbook_name
        )
        self._inventory_source = inventory_source
        self._extra_vars = extra_vars
        self._extra_vars.update(_EXTRA_VARS_FOR_FILTERING)
        self._user_extra_vars = user_extra_vars
        self._cb_results = {}
        self._raise_on_error = raise_on_error
        self._tags = tags
        self._skip_tags = skip_tags

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
                _('Failed decoding json data: {e} - "{d}"').format(
                    e=str(e),
                    d=d,
                )
            )

    def _format_tags_option(self, tags, tag_option):
        if tags and tag_option:
            if isinstance(tags, list) or isinstance(tags, tuple):
                tags = ','.join(tags)
            return '%s=%s' % (tag_option, tags)

        return ''

    def run(self):
        out_fd, out_path = tempfile.mkstemp()
        vars_fd, vars_path = tempfile.mkstemp()
        ansible_playbook_cmd = [
            '/bin/ansible-playbook',
            '--module-path={mp}'.format(mp=self._module_path),
            '--inventory={i}'.format(i=self._inventory_source),
            '--extra-vars=@{vf}'.format(vf=vars_path),
        ]
        if self._user_extra_vars:
            ansible_playbook_cmd.append(
                '--extra-vars={}'.format(self._user_extra_vars)
            )

        tags = self._format_tags_option(self._tags, '--tags')
        skip_tags = self._format_tags_option(self._skip_tags, '--skip-tags')
        if tags:
            ansible_playbook_cmd.append(tags)
        if skip_tags:
            ansible_playbook_cmd.append(skip_tags)

        ansible_playbook_cmd.append(self._playbook_path)

        env = os.environ.copy()
        env[ohostedcons.AnsibleCallback.OTOPI_CALLBACK_OF] = out_path
        env[
            'ANSIBLE_CALLBACK_WHITELIST'
        ] = '{com},{log}'.format(
            com=ohostedcons.AnsibleCallback.CALLBACK_NAME,
            log=ohostedcons.AnsibleCallback.LOGGER_CALLBACK_NAME,
        )
        env[
            'ANSIBLE_STDOUT_CALLBACK'
        ] = ohostedcons.AnsibleCallback.CALLBACK_NAME

        dname = os.path.splitext(self._playbook_name)[0]
        if self._tags:
            if isinstance(self._tags, list) or isinstance(self._tags, tuple):
                tag_name = self._tags[0]
            else:
                tag_name = self._tags
            dname = tag_name

        env[
            'HE_ANSIBLE_LOG_PATH'
        ] = os.path.join(
            ohostedcons.FileLocations.OVIRT_HOSTED_ENGINE_SETUP_LOGDIR,
            "%s-ansible-%s-%s-%s.log" % (
                ohostedcons.FileLocations.OVIRT_HOSTED_ENGINE_SETUP,
                dname,
                time.strftime("%Y%m%d%H%M%S"),
                ''.join(
                    [
                        random.choice(
                            string.ascii_lowercase +
                            string.digits
                        ) for i in range(6)
                    ]
                )
            )
        )

        self.logger.debug('ansible-playbook: cmd: %s' % ansible_playbook_cmd)
        self.logger.debug('ansible-playbook: out_path: %s' % out_path)
        self.logger.debug('ansible-playbook: vars_path: %s' % vars_path)
        self.logger.debug('ansible-playbook: env: %s' % env)

        rc = None
        with open(vars_path, 'w') as vars_fh:
            json.dump(self._extra_vars, vars_fh)
        with open(out_path, 'r') as out_fh:
            buffer = ''
            proc = subprocess.Popen(
                ansible_playbook_cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            while True:
                output = out_fh.readline()
                time.sleep(0.1)
                if output == '' and proc.poll() is not None:
                    break
                if output:
                    buffer += output
                    if buffer[-1] == '\n':
                        self._process_output(buffer)
                        buffer = ''
            rc = proc.poll()
            self._cb_results['ansible-playbook_rc'] = rc
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
