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
VM cpu configuration plugin.
"""


import gettext
import multiprocessing

from otopi import plugin
from otopi import util

from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    VM cpu configuration plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    def _getMaxVCpus(self):
        return str(multiprocessing.cpu_count())

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.VMEnv.VCPUS,
            None
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.APPLIANCEVCPUS,
            None
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.MAXVCPUS,
            None
        )
        # fixing values from answerfiles badly generated prior than 3.6
        if type(self.environment[ohostedcons.VMEnv.VCPUS]) == int:
            self.environment[
                ohostedcons.VMEnv.VCPUS
            ] = str(self.environment[ohostedcons.VMEnv.VCPUS])

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.CUSTOMIZATION_CPU_NUMBER,
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_VM,
            ohostedcons.Stages.CONFIG_OVF_IMPORT,
            ohostedcons.Stages.CUSTOMIZATION_CPU_MODEL,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_VM,
        ),
    )
    def _customization(self):
        interactive = self.environment[
            ohostedcons.VMEnv.VCPUS
        ] is None
        valid = False
        self.environment[ohostedcons.VMEnv.MAXVCPUS] = self._getMaxVCpus()
        maxvcpus = int(self.environment[ohostedcons.VMEnv.MAXVCPUS])

        default = ohostedcons.Defaults.DEFAULT_VM_VCPUS
        default_msg = _('minimum requirement')
        if self.environment[
            ohostedcons.VMEnv.APPLIANCEVCPUS
        ] is not None:
            default = self.environment[ohostedcons.VMEnv.APPLIANCEVCPUS]
            default_msg = _('appliance OVF value')

        while not valid:
            if interactive:
                self.environment[
                    ohostedcons.VMEnv.VCPUS
                ] = self.dialog.queryString(
                    name='ovehosted_vmenv_cpu',
                    note=_(
                        'Please specify the number of virtual CPUs for the VM. '
                        'The default is the {default_msg} [@DEFAULT@]: '
                    ).format(default_msg=default_msg),
                    prompt=True,
                    default=default,
                )
            try:
                valid = True
                if int(
                    self.environment[ohostedcons.VMEnv.VCPUS]
                ) < ohostedcons.Defaults.DEFAULT_VM_VCPUS:
                    self.logger.warning(
                        _('Minimum requirements for CPUs not met')
                    )
                    if (
                        interactive and
                        self.environment[
                            ohostedcons.CoreEnv.REQUIREMENTS_CHECK_ENABLED
                        ] and
                        not self.dialog.queryString(
                            name=ohostedcons.Confirms.CPU_PROCEED,
                            note=_(
                                'Continue with specified CPUs? '
                                '(@VALUES@)[@DEFAULT@]: '
                            ),
                            prompt=True,
                            validValues=(_('Yes'), _('No')),
                            caseSensitive=False,
                            default=_('No')
                        ) == _('Yes').lower()
                    ):
                        valid = False
                if int(
                    self.environment[ohostedcons.VMEnv.VCPUS]
                ) > maxvcpus:
                    message = _(
                        'Invalid number of cpu specified: {vcpu}, '
                        'while only {maxvcpus} are available on '
                        'the host'
                    ).format(
                        vcpu=self.environment[
                            ohostedcons.VMEnv.VCPUS
                        ],
                        maxvcpus=maxvcpus
                    )
                    if interactive:
                        self.logger.warning(message)
                        valid = False
                    else:
                        raise RuntimeError(message)
            except ValueError:
                valid = False
                if not interactive:
                    raise RuntimeError(
                        _('Invalid number of cpu specified: {vcpu}').format(
                            vcpu=self.environment[
                                ohostedcons.VMEnv.VCPUS
                            ],
                        )
                    )
                else:
                    self.logger.error(
                        _('Invalid number of cpu specified: {vcpu}').format(
                            vcpu=self.environment[
                                ohostedcons.VMEnv.VCPUS
                            ],
                        )
                    )


# vim: expandtab tabstop=4 shiftwidth=4
