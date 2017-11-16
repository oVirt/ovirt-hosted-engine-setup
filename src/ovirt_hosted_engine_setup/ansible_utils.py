
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
import os


from collections import namedtuple

from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.inventory.manager import InventoryManager
from ansible.parsing.dataloader import DataLoader
from ansible.playbook import Playbook
from ansible.plugins.callback import CallbackBase
from ansible.vars.manager import VariableManager

from otopi import base

from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


class ResultCallback(CallbackBase):

    def __init__(self, logger):
        super(ResultCallback, self).__init__()
        self.logger = logger
        self.cb_results = {}

    def v2_runner_on_failed(self, result, ignore_errors=False):
        delegated_vars = result._result.get(
            '_ansible_delegated_vars',
            None
        )
        self.logger.debug(result._result)
        if 'exception' in result._result:
            error = result._result['exception'].strip().split('\n')[-1]
            self.logger.error(error)
            del result._result['exception']
        if result._task.loop and 'results' in result._result:
            self._process_items(result)
        else:
            if delegated_vars:
                self.logger.error(
                    "fatal: [{h1} -> {h2}]: FAILED! => {r}".format(
                        h1=result._host.get_name(),
                        h2=delegated_vars['ansible_host'],
                        r=self._dump_results(result._result)
                    )
                )
            else:
                self.logger.error(
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

        if result._task.loop and 'results' in result._result:
            self._process_items(result)
        else:
            if result.task_name == 'debug':
                for i in result._result:
                    if not i.startswith('_'):
                        self.logger.debug(
                            '{i}: {v}'.format(
                                i=i,
                                v=result._result[i]
                            )
                        )
            else:
                self.logger.info(msg)

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
            self.logger.info(msg)

    def v2_runner_on_unreachable(self, result):
        delegated_vars = result._result.get(
            '_ansible_delegated_vars', None
        )
        if delegated_vars:
            self.logger.debug(
                "fatal: [{h1} -> {h2}]: UNREACHABLE! => {r}".format(
                    h1=result._host.get_name(),
                    h2=delegated_vars['ansible_host'],
                    r=self._dump_results(result._result)
                )
            )
        else:
            self.logger.debug(
                "fatal: [{h}]: UNREACHABLE! => {r}".format(
                    h=result._host.get_name(),
                    r=self._dump_results(result._result)
                )
            )

    def v2_runner_on_no_hosts(self, task):
        self.logger.debug("skipping: no hosts matched")

    def v2_playbook_on_task_start(self, task, is_conditional):
        task_name = task.get_name().strip()
        if task_name != 'debug':
            self.logger.info("TASK [{t}]".format(
                t=task_name)
            )
        else:
            self.logger.debug("TASK [{t}]".format(
                t=task_name)
            )

    def v2_playbook_on_play_start(self, play):
        name = play.get_name().strip()
        if not name:
            msg = "PLAY"
        else:
            msg = "PLAY [{p}]".format(p=name)

        self.logger.debug(msg)

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

        self.logger.info(msg)

    def v2_playbook_item_on_failed(self, result):
        delegated_vars = result._result.get(
            '_ansible_delegated_vars',
            None
        )
        if 'exception' in result._result:
            error = result._result['exception'].strip().split('\n')[-1]
            self.logger.debug(error)
            del result._result['exception']
        if delegated_vars:
            self.logger.error(
                "failed: [{h1} -> {h2}] => (item={i}) => {r}".format(
                    h1=result._host.get_name(),
                    h2=delegated_vars['ansible_host'],
                    i=result._result['item'],
                    r=self._dump_results(result._result)
                )
            )
        else:
            self.logger.error(
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
        self.logger.info(msg)

    def v2_playbook_on_stats(self, stats):
        hosts = sorted(stats.processed.keys())
        for h in hosts:
            t = stats.summarize(h)

            msg = "PLAY RECAP [{h}] : %s %s %s %s %s".format(
                h=h,
                o="ok: {n}".format(n=t['ok']),
                c="changed: {n}".format(n=t['changed']),
                u="unreachable: {n}".format(n=t['unreachable']),
                s="skipped: {n}".format(n=t['skipped']),
                f="failed: {n}".format(n=t['failures']),
            )

            self.logger.debug(msg)


class AnsibleHelper(base.Base):

    def __init__(
        self,
        playbook_name,
        custom_path=None,
        extra_vars=None,
        inventory_source='localhost,',
    ):
        super(AnsibleHelper, self).__init__()

        Options = namedtuple(
            'Options',
            [
                'connection',
                'module_path',
                'forks',
                'become',
                'become_method',
                'become_user',
                'check',
                'diff'
            ],
        )
        self._loader = DataLoader()
        self._options = Options(
            connection='local',
            module_path=custom_path if custom_path
            else ohostedcons.FileLocations.HOSTED_ENGINE_ANSIBLE_PATH,
            forks=100,
            become=None,
            become_method=None,
            become_user=None,
            check=False,
            diff=False
        )
        self._passwords = dict(vault_pass='secret')
        self._results_callback = ResultCallback(self.logger)
        self._inventory = InventoryManager(
            loader=self._loader,
            sources=inventory_source,
        )
        self._variable_manager = VariableManager(
            loader=self._loader,
            inventory=self._inventory
        )
        self.logger.debug('extra_vars: {ev}'.format(ev=extra_vars))
        if extra_vars:
            self._variable_manager.extra_vars = extra_vars
        self._pb = Playbook.load(
            os.path.join(self._options.module_path, playbook_name),
            variable_manager=self._variable_manager,
            loader=self._loader
        )

    def run(self):
        tqm = None
        try:
            tqm = TaskQueueManager(
                inventory=self._inventory,
                variable_manager=self._variable_manager,
                loader=self._loader,
                options=self._options,
                passwords=self._passwords,
                stdout_callback=self._results_callback,
            )
            plays = self._pb.get_plays()
            for play in plays:
                result = tqm.run(play)
            if result != 0:
                raise RuntimeError('Failed running ansible playbook')
        finally:
            if tqm is not None:
                tqm.cleanup()
        return self._results_callback.cb_results


# vim: expandtab tabstop=4 shiftwidth=4
