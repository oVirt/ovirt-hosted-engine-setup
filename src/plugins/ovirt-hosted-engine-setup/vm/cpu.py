#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2013 Red Hat, Inc.
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


from otopi import util
from otopi import plugin


from ovirt_hosted_engine_setup import constants as ohostedcons


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    VM cpu configuration plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.VMEnv.VCPUS,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=[
            ohostedcons.Stages.CONFIG_OVF_IMPORT,
        ],
        condition=lambda self: not self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
    )
    def _customization(self):
        interactive = self.environment[
            ohostedcons.VMEnv.VCPUS
        ] is None
        valid = False
        while not valid:
            if interactive:
                self.environment[
                    ohostedcons.VMEnv.VCPUS
                ] = self.dialog.queryString(
                    name='ovehosted_vmenv_cpu',
                    note=_(
                        'Please specify the number of virtual CPUs for the VM '
                        '[Minimum requirement: @DEFAULT@]: '
                    ),
                    prompt=True,
                    default=ohostedcons.Defaults.DEFAULT_VM_VCPUS,
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
                        not self.dialog.confirm(
                            name=ohostedcons.Confirms.CPU_PROCEED,
                            description='Confirm CPUs',
                            note=_(
                                'Continue with specified CPUs? (yes/no) '
                            ),
                            prompt=True,
                        )
                    ):
                        valid = False
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
