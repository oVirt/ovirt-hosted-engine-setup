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

# based on ansible/lib/ansible/plugins/callback/logstash.py

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import json
import logging
import os


from datetime import datetime

from ansible.plugins.callback import CallbackBase

__metaclass__ = type


DOCUMENTATION = '''
    callback: ovirt_logger
    type: notification
    short_description: Logs to file also without utils/display.py
    description:
      - Logs to file also without utils/display.py, see
        https://github.com/ansible/ansible/issues/25761#issuecomment-324890228
    requirements:
      - whitelisting in configuration
    options:
      server:
        description: log file
        env:
          - name: ANSIBLE_LOG_PATH
        default: None
'''


class CallbackModule(CallbackBase):
    """
    ansible ovirt_logger callback plugin
    This plugin makes use of the following environment variables:
        LOGSTASH_SERVER   (mandatory): defaults to None
    """

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'aggregate'
    CALLBACK_NAME = 'ovirt_logger'
    CALLBACK_NEEDS_WHITELIST = True

    def __init__(self):
        super(CallbackModule, self).__init__()

        logFileName = os.getenv('ANSIBLE_LOG_PATH', None)
        self.playbook = None

        if not logFileName:
            self.disabled = True
            self._display.warning(
                "No log file specified with ANSIBLE_LOG_PATH"
            )
        else:
            try:
                self.handle = open(
                    logFileName,
                    mode='a',
                    buffering=1,
                )
            except IOError:
                self.handle = open(
                    os.devnull,
                    mode='a',
                    buffering=1,
                )

            self._handler = logging.StreamHandler(self.handle)
            self._handler.setLevel(logging.DEBUG)
            self._handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s %(name)s '
                '%(module)s.%(funcName)s:%(lineno)d '
                '%(message)s'
            ))
            self.logger = logging.getLogger(
                "ovirt-hosted-engine-setup-ansible"
            )
            self.logger.addHandler(self._handler)
        self.start_time = datetime.utcnow()
        self.errors = 0

    def v2_playbook_on_start(self, playbook):
        self.playbook = playbook._file_name
        data = {
            'status': "OK",
            'ansible_type': "start",
            'ansible_playbook': self.playbook,
        }
        self.logger.info("ansible start", extra=data)

    def v2_playbook_on_stats(self, stats):
        end_time = datetime.utcnow()
        runtime = end_time - self.start_time
        summarize_stat = {}
        for host in stats.processed.keys():
            summarize_stat[host] = stats.summarize(host)

        if self.errors == 0:
            status = "OK"
        else:
            status = "FAILED"

        data = {
            'status': status,
            'ansible_type': "finish",
            'ansible_playbook': self.playbook,
            'ansible_playbook_duration': runtime.total_seconds(),
            'ansible_result': json.dumps(summarize_stat),
        }
        self.logger.info("ansible stats", extra=data)

    def v2_runner_on_ok(self, result, **kwargs):
        data = {
            'status': "OK",
            'ansible_type': "task",
            'ansible_playbook': self.playbook,
            'ansible_host': result._host.name,
            'ansible_task': result._task,
            'ansible_result': self._dump_results(result._result)
        }
        self.logger.info("ansible ok", extra=data)

    def v2_runner_on_skipped(self, result, **kwargs):
        data = {
            'status': "SKIPPED",
            'ansible_type': "task",
            'ansible_playbook': self.playbook,
            'ansible_task': result._task,
            'ansible_host': result._host.name
        }
        self.logger.info("ansible skipped", extra=data)

    def v2_playbook_on_import_for_host(self, result, imported_file):
        data = {
            'status': "IMPORTED",
            'ansible_type': "import",
            'ansible_playbook': self.playbook,
            'ansible_host': result._host.name,
            'imported_file': imported_file
        }
        self.logger.info("ansible import", extra=data)

    def v2_playbook_on_not_import_for_host(self, result, missing_file):
        data = {
            'status': "NOT IMPORTED",
            'ansible_type': "import",
            'ansible_playbook': self.playbook,
            'ansible_host': result._host.name,
            'missing_file': missing_file
        }
        self.logger.info("ansible import", extra=data)

    def v2_runner_on_failed(self, result, **kwargs):
        data = {
            'status': "FAILED",
            'ansible_type': "task",
            'ansible_playbook': self.playbook,
            'ansible_host': result._host.name,
            'ansible_task': result._task,
            'ansible_result': self._dump_results(result._result)
        }
        self.errors += 1
        self.logger.error("ansible failed", extra=data)

    def v2_runner_on_unreachable(self, result, **kwargs):
        data = {
            'status': "UNREACHABLE",
            'ansible_type': "task",
            'ansible_playbook': self.playbook,
            'ansible_host': result._host.name,
            'ansible_task': result._task,
            'ansible_result': self._dump_results(result._result)
        }
        self.logger.error("ansible unreachable", extra=data)

    def v2_runner_on_async_failed(self, result, **kwargs):
        data = {
            'status': "FAILED",
            'ansible_type': "task",
            'ansible_playbook': self.playbook,
            'ansible_host': result._host.name,
            'ansible_task': result._task,
            'ansible_result': self._dump_results(result._result)
        }
        self.errors += 1
        self.logger.error("ansible async", extra=data)
