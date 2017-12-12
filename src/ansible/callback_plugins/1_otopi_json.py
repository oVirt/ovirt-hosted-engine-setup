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


"""OTOPI Json callback"""


# there is a default ansible callback plugin called json.py
from __future__ import (absolute_import, division, print_function)


import json
import os


from ansible.plugins.callback import CallbackBase


from ovirt_hosted_engine_setup import constants as ohostedcons


class CallbackModule(CallbackBase):

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'stdout'
    CALLBACK_NAME = ohostedcons.AnsibleCallback.CALLBACK_NAME
    CALLBACK_NEEDS_WHITELIST = True

    def __init__(self):
        super(CallbackModule, self).__init__()
        self.cb_results = {}
        OTOPI_CALLBACK_OF = os.environ.get(
            ohostedcons.AnsibleCallback.OTOPI_CALLBACK_OF
        )
        if not OTOPI_CALLBACK_OF:
            self._display.error(
                'Unable to find {ek}'.format(
                    ek=ohostedcons.AnsibleCallback.OTOPI_CALLBACK_OF
                )
            )
            self._fd = None
        else:
            self._fd = open(OTOPI_CALLBACK_OF, 'w')

    def write_msg(self, data_type, body):
        payload = {
            ohostedcons.AnsibleCallback.TYPE: data_type,
            ohostedcons.AnsibleCallback.BODY: body,
        }

        if self._fd:
            try:
                json.dump(payload, self._fd)
                self._fd.write('\n')
                self._fd.flush()
            except Exception as e:
                self._display.error(
                    'Error serializing JSON data: {e}'.format(e=str(e))
                )
        else:
            self._display.display(str(body))

    def v2_runner_on_failed(self, result, ignore_errors=False):
        delegated_vars = result._result.get(
            '_ansible_delegated_vars',
            None
        )
        self.write_msg(ohostedcons.AnsibleCallback.DEBUG, result._result)
        if 'exception' in result._result:
            error = result._result['exception'].strip().split('\n')[-1]
            self.write_msg(ohostedcons.AnsibleCallback.ERROR, error)
            del result._result['exception']
        if result._task.loop and 'results' in result._result:
            self._process_items(result)
        else:
            if delegated_vars:
                self.write_msg(
                    ohostedcons.AnsibleCallback.ERROR,
                    "fatal: [{h1} -> {h2}]: FAILED! => {r}".format(
                        h1=result._host.get_name(),
                        h2=delegated_vars['ansible_host'],
                        r=self._dump_results(result._result)
                    )
                )
            else:
                self.write_msg(
                    ohostedcons.AnsibleCallback.ERROR,
                    "fatal: [{h}]: FAILED! => {r}".format(
                        h=result._host.get_name(),
                        r=self._dump_results(result._result)
                    )
                )

    def v2_runner_on_ok(self, result):
        self._clean_results(result._result, result._task.action)
        delegated_vars = result._result.get(
            '_ansible_delegated_vars',
            None
        )
        if result._task.action == 'include':
            return
        elif result._result.get('changed', False):
            if delegated_vars:
                msg = "changed: [{h1} -> {h2}]".format(
                    h1=result._host.get_name(),
                    h2=delegated_vars['ansible_host']
                )
            else:
                msg = "changed: [{h}]".format(h=result._host.get_name())
        else:
            if delegated_vars:
                msg = "ok: [{h1} -> {h2}]".format(
                    h1=result._host.get_name(),
                    h2=delegated_vars['ansible_host']
                )
            else:
                msg = "ok: [{h}]".format(h=result._host.get_name())

        if not (result._task.loop and 'results' in result._result):
            if result.task_name == 'debug':
                for i in result._result:
                    if not i.startswith('_'):
                        self.write_msg(
                            ohostedcons.AnsibleCallback.DEBUG,
                            '{i}: {v}'.format(
                                i=i,
                                v=result._result[i]
                            )
                        )
            else:
                self.write_msg(ohostedcons.AnsibleCallback.INFO, msg)

        register = result._task_fields['register']
        if register and register.startswith(
            ohostedcons.Const.ANSIBLE_R_OTOPI_PREFIX
        ):
            self.cb_results[register] = {}
            for r in result._result:
                self.cb_results[register][r] = result._result[r]

    def v2_runner_on_skipped(self, result):
        if result._task.loop and 'results' in result._result:
            self._process_items(result)
        else:
            msg = "skipping: [{h}]".format(h=result._host.get_name())
            self.write_msg(ohostedcons.AnsibleCallback.INFO, msg)

    def v2_runner_on_unreachable(self, result):
        delegated_vars = result._result.get(
            '_ansible_delegated_vars', None
        )
        if delegated_vars:
            self.write_msg(
                ohostedcons.AnsibleCallback.ERROR,
                "fatal: [{h1} -> {h2}]: UNREACHABLE! => {r}".format(
                    h1=result._host.get_name(),
                    h2=delegated_vars['ansible_host'],
                    r=self._dump_results(result._result)
                )
            )
        else:
            self.write_msg(
                ohostedcons.AnsibleCallback.ERROR,
                "fatal: [{h}]: UNREACHABLE! => {r}".format(
                    h=result._host.get_name(),
                    r=self._dump_results(result._result)
                )
            )

    def v2_runner_on_no_hosts(self, task):
        self.write_msg(
            ohostedcons.AnsibleCallback.WARNING,
            "skipping: no hosts matched"
        )

    def v2_playbook_on_task_start(self, task, is_conditional):
        task_name = task.get_name().strip()
        if task_name != 'debug':
            self.write_msg(
                ohostedcons.AnsibleCallback.INFO,
                "TASK [{t}]".format(
                    t=task_name
                )
            )
        else:
            self.write_msg(
                ohostedcons.AnsibleCallback.DEBUG,
                "TASK [{t}]".format(
                    t=task_name
                )
            )

    def v2_playbook_on_play_start(self, play):
        name = play.get_name().strip()
        if not name:
            msg = "PLAY"
        else:
            msg = "PLAY [{p}]".format(p=name)

        self.write_msg(ohostedcons.AnsibleCallback.DEBUG, msg)

    def v2_playbook_item_on_ok(self, result):
        delegated_vars = result._result.get(
            '_ansible_delegated_vars',
            None
        )
        if result._task.action == 'include':
            return
        elif result._result.get('changed', False):
            if delegated_vars:
                msg = "changed: [{h1} -> {h2}]".format(
                    h1=result._host.get_name(),
                    h2=delegated_vars['ansible_host'],
                )
            else:
                msg = "changed: [{h}]".format(h=result._host.get_name())
        else:
            if delegated_vars:
                msg = "ok: [%s -> %s]" % (
                    result._host.get_name(),
                    delegated_vars['ansible_host']
                )
            else:
                msg = "ok: [{h}]".format(h=result._host.get_name())

        msg += " => (item={i})".format(i=result._result['item'])

        self.write_msg(ohostedcons.AnsibleCallback.INFO, msg)

    def v2_playbook_item_on_failed(self, result):
        delegated_vars = result._result.get(
            '_ansible_delegated_vars',
            None
        )
        if 'exception' in result._result:
            error = result._result['exception'].strip().split('\n')[-1]
            self.write_msg(ohostedcons.AnsibleCallback.DEBUG, error)
            del result._result['exception']
        if delegated_vars:
            self.write_msg(
                ohostedcons.AnsibleCallback.ERROR,
                "failed: [{h1} -> {h2}] => (item={i}) => {r}".format(
                    h1=result._host.get_name(),
                    h2=delegated_vars['ansible_host'],
                    i=result._result['item'],
                    r=self._dump_results(result._result)
                )
            )
        else:
            self.write_msg(
                ohostedcons.AnsibleCallback.ERROR,
                "failed: [{h}] => (item={i}) => {r}".format(
                    h=result._host.get_name(),
                    i=result._result['item'],
                    r=self._dump_results(result._result)
                )
            )

    def v2_playbook_item_on_skipped(self, result):
        msg = "skipping: [{h}] => (item={i}) ".format(
            h=result._host.get_name(),
            i=result._result['item']
        )
        self.write_msg(ohostedcons.AnsibleCallback.INFO, msg)

    def v2_playbook_on_stats(self, stats):
        hosts = sorted(stats.processed.keys())
        if self.cb_results:
            self.write_msg(ohostedcons.AnsibleCallback.RESULT, self.cb_results)
        for h in hosts:
            t = stats.summarize(h)

            msg = "PLAY RECAP [{h}] : {o} {c} {u} {s} {f}".format(
                h=h,
                o="ok: {n}".format(n=t['ok']),
                c="changed: {n}".format(n=t['changed']),
                u="unreachable: {n}".format(n=t['unreachable']),
                s="skipped: {n}".format(n=t['skipped']),
                f="failed: {n}".format(n=t['failures']),
            )
            self.write_msg(ohostedcons.AnsibleCallback.DEBUG, msg)
