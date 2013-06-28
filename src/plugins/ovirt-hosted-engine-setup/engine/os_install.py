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
vm os install status handler plugin.
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
    vm os install status handler plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    def _reconfigure(self):
        self.environment[ohostedcons.VMEnv.SUBST]['@BOOT@'] = 'c'
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

    def _shutdown(self):
        self.execute(
            (
                self.command.get('vdsClient'),
                '-s',
                'localhost',
                'shutdown',
                self.environment[ohostedcons.VMEnv.VM_UUID],
                '0',
                _('Reboot'),
            ),
            raiseOnError=True
        )
        self.execute(
            (
                self.command.get('vdsClient'),
                '-s',
                'localhost',
                'destroy',
                self.environment[ohostedcons.VMEnv.VM_UUID],
            ),
            raiseOnError=True
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        # Can't use python api here, it will call sys.exit
        self.command.detect('vdsClient')

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        after=[
            ohostedcons.Stages.VM_RUNNING,
        ],
        name=ohostedcons.Stages.OS_INSTALLED,
    )
    def _misc(self):
        self.dialog.queryString(
            name='ovehosted_engine_up',
            note=_(
                'Please install the OS in the vm,'
                'hit enter when finished for restarting the VM from HD.'
            ),
            prompt=True,
            default='y'  # Allow enter without any value
        )
        self._shutdown()
        self._reconfigure()


# vim: expandtab tabstop=4 shiftwidth=4
