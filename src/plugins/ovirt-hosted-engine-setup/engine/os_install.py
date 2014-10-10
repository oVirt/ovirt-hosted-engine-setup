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
reconfigure vm after os install plugin.
"""


import gettext

from otopi import util
from otopi import plugin
from otopi import transaction
from otopi import filetransaction
from otopi import constants as otopicons


from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import util as ohostedutil


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    reconfigure vm after os install plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        after=(
            ohostedcons.Stages.VM_RUNNING,
        ),
        name=ohostedcons.Stages.OS_INSTALLED,
        condition=lambda self: not self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
    )
    def _closeup(self):
        # TODO: now mixins._create_vm dinamically generates
        # VM config from env variables.
        # It would be better to do it from the template
        self.environment[ohostedcons.VMEnv.BOOT] = 'disk'
        self.environment[ohostedcons.VMEnv.SUBST][
            '@BOOT_DISK@'
        ] = ',bootOrder:1'
        self.environment[ohostedcons.VMEnv.SUBST]['@BOOT_PXE@'] = ''
        self.environment[ohostedcons.VMEnv.SUBST]['@BOOT_CDROM@'] = ''
        content = ohostedutil.processTemplate(
            template=ohostedcons.FileLocations.ENGINE_VM_TEMPLATE,
            subst=self.environment[ohostedcons.VMEnv.SUBST],
        )
        with transaction.Transaction() as localtransaction:
            localtransaction.append(
                filetransaction.FileTransaction(
                    name=ohostedcons.FileLocations.ENGINE_VM_CONF,
                    content=content,
                    modifiedList=self.environment[
                        otopicons.CoreEnv.MODIFIED_FILES
                    ],
                ),
            )


# vim: expandtab tabstop=4 shiftwidth=4
