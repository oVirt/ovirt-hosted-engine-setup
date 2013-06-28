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
VM configuration plugin.
"""


import string
import random
import gettext


from otopi import util
from otopi import plugin


from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import tasks


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    VM configuration plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    def _generateTempVncPassword(self):
        self.logger.info(
            _('Generating a temporary VNC password.')
        )
        return '%s%s' % (
            ''.join([random.choice(string.digits) for i in range(4)]),
            ''.join([random.choice(string.letters) for i in range(4)]),
        )

    def _create(self):
        waiter = tasks.TaskWaiter(self.environment)
        waiter.wait()
        self.logger.info(_('Creating VM'))
        self.execute(
            (
                self.command.get('vdsClient'),
                '-s',
                'localhost',
                'create',
                ohostedcons.FileLocations.ENGINE_VM_CONF
            ),
            raiseOnError=True
        )
        password_set = False
        while not password_set:
            waiter.wait()
            try:
                self.execute(
                    (
                        self.command.get('vdsClient'),
                        '-s',
                        'localhost',
                        'setVmTicket',
                        self.environment[ohostedcons.VMEnv.VM_UUID],
                        self.environment[ohostedcons.VMEnv.VM_PASSWD],
                        self.environment[
                            ohostedcons.VMEnv.VM_PASSWD_VALIDITY_SECS
                        ],
                    ),
                    raiseOnError=True
                )
                password_set = True
            except RuntimeError as e:
                self.logger.debug(str(e))
        self.dialog.note(
            _(
                'You can now connect to the VM with the following command:\n'
                '\t{remote} vnc://localhost:5900\nUse temporary password '
                '"{password}" to connect to vnc.'
            ).format(
                remote=self.command.get('remote-viewer'),
                password=self.environment[
                    ohostedcons.VMEnv.VM_PASSWD
                ],
            )
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.VMEnv.VM_PASSWD,
            self._generateTempVncPassword()
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.VM_PASSWD_VALIDITY_SECS,
            ohostedcons.Defaults.DEFAULT_VM_PASSWD_VALIDITY_SECS
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        # Can't use python api here, it will call sys.exit
        self.command.detect('vdsClient')
        self.command.detect('remote-viewer')

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        after=[
            ohostedcons.Stages.VM_CONFIGURED,
            ohostedcons.Stages.VM_IMAGE_AVAILABLE,
            ohostedcons.Stages.LIBVIRT_CONFIGURED,
            ohostedcons.Stages.SSHD_START,
        ],
        name=ohostedcons.Stages.VM_RUNNING,
    )
    def _boot_from_install_media(self):
        self._create()

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        after=[
            ohostedcons.Stages.OS_INSTALLED,
        ],
        name=ohostedcons.Stages.INSTALLED_VM_RUNNING,
    )
    def _boot_from_hd(self):
        self._create()


# vim: expandtab tabstop=4 shiftwidth=4
