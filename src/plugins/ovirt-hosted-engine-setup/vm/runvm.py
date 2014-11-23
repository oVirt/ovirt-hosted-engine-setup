#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2013-2014 Red Hat, Inc.
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


import gettext

from otopi import util
from otopi import plugin
from otopi import constants as otopicons


from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import mixins


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(mixins.VmOperations, plugin.PluginBase):
    """
    VM configuration plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.VMEnv.VM_PASSWD,
            self._generateTempVncPassword()
        )
        self.environment[otopicons.CoreEnv.LOG_FILTER_KEYS].append(
            ohostedcons.VMEnv.VM_PASSWD
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.VM_PASSWD_VALIDITY_SECS,
            ohostedcons.Defaults.DEFAULT_VM_PASSWD_VALIDITY_SECS
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.CONSOLE_TYPE,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        # Can't use python api here, it will call sys.exit
        self.command.detect('vdsClient')
        self.command.detect('remote-viewer')

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        condition=lambda self: not self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_VM,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_VM,
        ),
    )
    def _customization(self):
        validConsole = False
        interactive = self.environment[
            ohostedcons.VMEnv.CONSOLE_TYPE
        ] is None
        answermap = {
            'vnc': 'vnc',
            'spice': 'qxl'
        }
        while not validConsole:
            if self.environment[
                ohostedcons.VMEnv.CONSOLE_TYPE
            ] is None:
                answer = self.dialog.queryString(
                    name='OVEHOSTED_VM_CONSOLE_TYPE',
                    note=_(
                        'Please specify the console type '
                        'you would like to use to connect '
                        'to the VM (@VALUES@) [@DEFAULT@]: '
                    ),
                    prompt=True,
                    caseSensitive=False,
                    validValues=list(answermap.keys()),
                    default='vnc',
                )

                if answer in answermap.keys():
                    self.environment[
                        ohostedcons.VMEnv.CONSOLE_TYPE
                    ] = answermap[answer]
            if self.environment[
                ohostedcons.VMEnv.CONSOLE_TYPE
            ] in answermap.values():
                validConsole = True
            elif interactive:
                self.logger.error(
                    'Unsuppored console type provided.'
                )
            else:
                raise RuntimeError(
                    _('Unsuppored console type provided.')
                )

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        name=ohostedcons.Stages.VM_RUNNING,
        priority=plugin.Stages.PRIORITY_LOW,
        condition=lambda self: (
            self.environment[ohostedcons.VMEnv.BOOT] != 'disk' and
            not self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]
        ),
    )
    def _boot_from_install_media(self):
        # Need to be done after firewall closeup for allowing the user to
        # connect from remote.
        os_installed = False
        while not os_installed:
            self._create_vm()
            response = None
            while response is None:
                response = self.dialog.queryString(
                    name='OVEHOSTED_INSTALLING_OS',
                    note=_(
                        'The VM has been started.  Install the OS and shut '
                        'down or reboot it.  To continue please make a '
                        'selection:\n\n'
                        '(1) Continue setup - VM installation is complete\n'
                        '(2) Reboot the VM and restart installation\n'
                        '(3) Abort setup\n'
                        '(4) Destroy VM and abort setup\n'
                        '\n(@VALUES@)[@DEFAULT@]: '
                    ),
                    prompt=True,
                    validValues=(_('1'), _('2'), _('3'), _('4')),
                    default=_('1'),
                    caseSensitive=False)
                if response == _('1').lower():
                    self.dialog.note(
                        _('Waiting for VM to shut down...\n')
                    )
                    if not self._wait_vm_destroyed():
                        self._destroy_vm()
                    os_installed = True
                elif response == _('2').lower():
                    self._destroy_vm()
                elif response == _('3').lower():
                    raise RuntimeError(_('OS installation aborted by user'))
                elif response == _('4').lower():
                    self._destroy_vm()
                    raise RuntimeError(
                        _('VM destroyed and setup aborted by user')
                    )
                else:
                    self.logger.error(
                        'Invalid option \'{0}\''.format(response)
                    )
                    response = None

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        after=(
            ohostedcons.Stages.OS_INSTALLED,
        ),
        name=ohostedcons.Stages.INSTALLED_VM_RUNNING,
        condition=lambda self: not self.environment[
            ohostedcons.CoreEnv.IS_ADDITIONAL_HOST
        ],
    )
    def _boot_from_hd(self):
        self._create_vm()


# vim: expandtab tabstop=4 shiftwidth=4
