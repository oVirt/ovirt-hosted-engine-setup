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
VM memory configuration plugin.
"""


import gettext


from otopi import util
from otopi import plugin


from ovirt_hosted_engine_setup import constants as ohostedcons


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    VM memory configuration plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.VMEnv.MEM_SIZE_MB,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        condition=lambda self: not self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
        after=(
            ohostedcons.Stages.CONFIG_OVF_IMPORT,
        ),
    )
    def _customization(self):
        interactive = self.environment[
            ohostedcons.VMEnv.MEM_SIZE_MB
        ] is None
        valid = False
        while not valid:
            if interactive:
                self.environment[
                    ohostedcons.VMEnv.MEM_SIZE_MB
                ] = self.dialog.queryString(
                    name='ovehosted_vmenv_mem',
                    note=_(
                        'Please specify the memory size of the VM in MB '
                        '[Defaults to minimum requirement: @DEFAULT@]: '
                    ),
                    prompt=True,
                    default=ohostedcons.Defaults.DEFAULT_MEM_SIZE_MB,
                )
            try:
                valid = True
                if int(
                    self.environment[ohostedcons.VMEnv.MEM_SIZE_MB]
                ) < ohostedcons.Defaults.DEFAULT_MEM_SIZE_MB:
                    self.logger.warning(
                        _('Minimum requirements for memory size not met')
                    )
                    if (
                        interactive and
                        self.environment[
                            ohostedcons.CoreEnv.REQUIREMENTS_CHECK_ENABLED
                        ] and
                        not self.dialog.queryString(
                            name=ohostedcons.Confirms.MEMORY_PROCEED,
                            note=_(
                                'Continue with specified memory size? '
                                '(@VALUES@)[@DEFAULT]: '
                            ),
                            prompt=True,
                            validValues=(_('Yes'), _('No')),
                            caseSensitive=False,
                            default=_('No')
                        ) == _('Yes').lower()
                    ):
                        valid = False

            except ValueError:
                valid = False
                if not interactive:
                    raise RuntimeError(
                        _('Invalid memory size specified: {size}').format(
                            size=self.environment[
                                ohostedcons.VMEnv.MEM_SIZE_MB
                            ],
                        )
                    )
                else:
                    self.logger.error(
                        _('Invalid memory size specified: {size}').format(
                            size=self.environment[
                                ohostedcons.VMEnv.MEM_SIZE_MB
                            ],
                        )
                    )


# vim: expandtab tabstop=4 shiftwidth=4
