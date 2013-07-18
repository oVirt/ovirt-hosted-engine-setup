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
VM cdrom configuration plugin.
"""


import gettext


from otopi import util
from otopi import plugin


from ovirt_hosted_engine_setup import constants as ohostedcons


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    VM cdrom configuration plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    def _check_iso_readable(self, filepath):
        try:
            self.execute(
                (
                    self.command.get('sudo'),
                    '-u',
                    'vdsm',
                    '-g',
                    'kvm',
                    'test',
                    '-r',
                    filepath,
                ),
                raiseOnError=True
            )
            readable = True
        except RuntimeError:
            readable = False
        return readable

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.VMEnv.CDROM,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        self.command.detect('sudo')

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=[
            ohostedcons.Stages.CONFIG_BOOT_DEVICE,
        ],
        condition=lambda self: (
            self.environment[ohostedcons.VMEnv.BOOT] == 'cdrom' and
            not self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]
        )
    )
    def _customization(self):
        interactive = self.environment[
            ohostedcons.VMEnv.CDROM
        ] is None
        valid = False
        while not valid:
            self.environment[
                ohostedcons.VMEnv.CDROM
            ] = self.dialog.queryString(
                name='OVEHOSTED_VMENV_CDROM',
                note=_(
                    'Please specify path to installation media '
                    'you would like to use [@DEFAULT@]: '
                ),
                prompt=True,
                caseSensitive=True,
                default=str(self.environment[
                    ohostedcons.VMEnv.CDROM
                ]),
            )

            valid = self._check_iso_readable(
                self.environment[ohostedcons.VMEnv.CDROM]
            )
            if not valid:
                if interactive:
                    self.logger.error(
                        _(
                            'The specified installation media is not '
                            'readable. Please ensure that {filepath} '
                            'could be read by vdsm user or kvm group '
                            'or specify another installation media.'
                        ).format(
                            filepath=self.environment[
                                ohostedcons.VMEnv.CDROM
                            ]
                        )
                    )
                else:
                    raise RuntimeError(
                        _(
                            'The specified installation media is not '
                            'readable. Please ensure that {filepath} '
                            'could be read by vdsm user or kvm group'
                        ).format(
                            filepath=self.environment[
                                ohostedcons.VMEnv.CDROM
                            ]
                        )
                    )


# vim: expandtab tabstop=4 shiftwidth=4
