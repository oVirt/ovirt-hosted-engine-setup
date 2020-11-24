#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2013-2017 Red Hat, Inc.
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


"""
VM memory configuration plugin.
"""


import gettext

from otopi import plugin
from otopi import util

from ovirt_setup_lib import dialog

from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    VM memory configuration plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    def _getMaxMemorySize(self):
        with open('/proc/meminfo', 'r') as mem:
            memAvailable = 0
            for i in mem:
                sline = i.split()
                if str(sline[0]) in ('MemFree:', 'Buffers:', 'Cached:'):
                    memAvailable += int(sline[1])
        return memAvailable/1024

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.VMEnv.MEM_SIZE_MB,
            None
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.APPLIANCEMEM,
            None
        )
        self.environment.setdefault(
            ohostedcons.CoreEnv.MEM_REQUIREMENTS_CHECK_ENABLED,
            True
        )
        # fixing values from answerfiles badly generated prior than 3.6
        if type(self.environment[ohostedcons.VMEnv.MEM_SIZE_MB]) == int:
            self.environment[
                ohostedcons.VMEnv.MEM_SIZE_MB
            ] = str(self.environment[ohostedcons.VMEnv.MEM_SIZE_MB])

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.CONFIG_OVF_IMPORT,
            ohostedcons.Stages.DIALOG_TITLES_S_VM,
        ),
        before=(
            ohostedcons.Stages.CUSTOMIZATION_CPU_MODEL,
            ohostedcons.Stages.CUSTOMIZATION_MAC_ADDRESS,
            ohostedcons.Stages.DIALOG_TITLES_E_VM,
        ),
    )
    def _customization(self):
        maxmem = int(self._getMaxMemorySize()) - \
            ohostedcons.Const.HOST_RESERVED_MEMORY_MB

        default_proceed_value = _('No')
        if maxmem < ohostedcons.Defaults.MINIMAL_MEM_SIZE_MB:
            self.logger.warning(
                _(
                    'Minimum requirements not met by available memory: '
                    'Required: {memsize} MB. Available: {maxmem} MB'
                ).format(
                    memsize=ohostedcons.Defaults.MINIMAL_MEM_SIZE_MB,
                    maxmem=maxmem,
                )
            )
            default_proceed_value = _('Abort')

        default = ohostedcons.Defaults.MINIMAL_MEM_SIZE_MB
        default_msg = _('minimum requirement')
        if self.environment[
            ohostedcons.VMEnv.APPLIANCEMEM
        ] is not None:
            default = self.environment[ohostedcons.VMEnv.APPLIANCEMEM]
            default_msg = _('appliance OVF value')
        if default > maxmem:
            default = maxmem
            default_msg = _('maximum available')

        def _check_min_memory(mem_size_mb):
            if not self.environment[
                ohostedcons.CoreEnv.REQUIREMENTS_CHECK_ENABLED
            ]:
                return None
            try:
                if int(
                    mem_size_mb
                ) < ohostedcons.Defaults.MINIMAL_MEM_SIZE_MB:
                    return _(
                        'Minimum requirements for memory size not met'
                    )
            except ValueError:
                return _(
                    'Invalid memory size specified: {size}'
                ).format(
                    size=mem_size_mb,
                )

        def _check_memory_is_int(mem_size_mb):
            try:
                int(mem_size_mb)
            except ValueError:
                return _(
                    'Invalid memory size specified: {size}'
                ).format(
                    size=mem_size_mb,
                )

        def _check_memory_value(mem_size_mb):
            if not self.environment[
                ohostedcons.CoreEnv.REQUIREMENTS_CHECK_ENABLED
            ] or not self.environment[
                ohostedcons.CoreEnv.MEM_REQUIREMENTS_CHECK_ENABLED
            ]:
                return None
            if int(
                mem_size_mb
            ) < ohostedcons.Defaults.MINIMAL_MEM_SIZE_MB:
                return _(
                    'Minimum requirements for memory size not met'
                )
            if int(
                mem_size_mb
            ) > maxmem:
                return _(
                    'Invalid memory size specified: {memsize}, '
                    'while only {maxmem} are available on '
                    'the host'
                ).format(
                    memsize=mem_size_mb,
                    maxmem=maxmem,
                )
        mem_size_mb_was_set = self.environment[
            ohostedcons.VMEnv.MEM_SIZE_MB
        ]

        dialog.queryEnvKey(
            dialog=self.dialog,
            logger=self.logger,
            env=self.environment,
            key=ohostedcons.VMEnv.MEM_SIZE_MB,
            name='ovehosted_vmenv_mem',
            note=_(
                'Please specify the memory size of the VM in MB. '
                'The default is the {default_msg} [@DEFAULT@]: '
            ).format(
                default_msg=default_msg,
            ),
            prompt=True,
            hidden=False,
            tests=(
                {
                    'test': _check_memory_is_int,
                    'is_error': True,
                },
                {
                    'test': _check_memory_value,
                    'warn_name': ohostedcons.Confirms.MEMORY_PROCEED,
                    'warn_note': _(
                        'Continue with specified memory size?'
                    ),
                    'is_error': False,
                    'default': default_proceed_value,
                },
            ),
            default=default,
            store=True,
        )

        # ensure that value is stored as integer. _check_memory_is_int
        # already ensured that value is a valid integer before.
        self.environment[ohostedcons.VMEnv.MEM_SIZE_MB] = int(
            self.environment[ohostedcons.VMEnv.MEM_SIZE_MB]
        )

        # For the 'interactive-only' flow.
        # set the memory size check to false if the user chose to continue.
        if not mem_size_mb_was_set and ((
            self.environment[ohostedcons.VMEnv.MEM_SIZE_MB]
        ) < ohostedcons.Defaults.MINIMAL_MEM_SIZE_MB or (
            self.environment[ohostedcons.VMEnv.MEM_SIZE_MB]
        ) > maxmem):
            self.environment[
                ohostedcons.CoreEnv.MEM_REQUIREMENTS_CHECK_ENABLED
            ] = False


# vim: expandtab tabstop=4 shiftwidth=4
