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
import time


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

    TICKET_MAX_TRIES = 10
    TICKET_DELAY = 1

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._vdscommand = []

    def _generateTempVncPassword(self):
        self.logger.info(
            _('Generating a temporary VNC password.')
        )
        return '%s%s' % (
            ''.join([random.choice(string.digits) for _i in range(4)]),
            ''.join([random.choice(string.letters) for _i in range(4)]),
        )

    def _generateUserMessage(self, console_type):
        if console_type == 'vnc':
            return _(
                'You can now connect to the VM with the following command:\n'
                '\t{remote} vnc://localhost:5900\nUse temporary password '
                '"{password}" to connect to vnc console.\n'
            ).format(
                remote=self.command.get('remote-viewer'),
                password=self.environment[
                    ohostedcons.VMEnv.VM_PASSWD
                ],
            )
        elif console_type == 'qxl':
            return _(
                'You can now connect to the VM with the following command:\n'
                '\t{remote} --spice-ca-file={ca_cert} '
                'spice://localhost?tls-port=5900 '
                '--spice-host-subject="{subject}"\nUse temporary password '
                '"{password}" to connect to spice console.'
            ).format(
                remote=self.command.get('remote-viewer'),
                ca_cert=ohostedcons.FileLocations.LIBVIRT_CA_CERT,
                subject=self.environment[ohostedcons.VDSMEnv.SPICE_SUBJECT],
                password=self.environment[
                    ohostedcons.VMEnv.VM_PASSWD
                ],
            )

        else:
            raise RuntimeError(
                _(
                    'Unsuppored console type "{console}" requested'.format(
                        console=console_type
                    )
                )
            )

    def _create(self):
        self.logger.info(_('Creating VM'))
        cmd = self._vdscommand + [
            'create',
            ohostedcons.FileLocations.ENGINE_VM_CONF,
        ]
        self.execute(
            cmd,
            raiseOnError=True
        )
        password_set = False
        tries = self.TICKET_MAX_TRIES
        while not password_set and tries > 0:
            tries -= 1
            try:
                cmd = self._vdscommand + [
                    'setVmTicket',
                    self.environment[ohostedcons.VMEnv.VM_UUID],
                    self.environment[ohostedcons.VMEnv.VM_PASSWD],
                    self.environment[
                        ohostedcons.VMEnv.VM_PASSWD_VALIDITY_SECS
                    ],
                ]
                self.execute(
                    cmd,
                    raiseOnError=True
                )
                password_set = True
            except RuntimeError as e:
                self.logger.debug(str(e))
                time.sleep(self.TICKET_DELAY)
        if not password_set:
            raise RuntimeError(
                _(
                    'Cannot set temporary password for console connection.\n'
                    'The VM may not have been created: please check VDSM logs'
                )
            )
        else:
            self.dialog.note(
                self._generateUserMessage(
                    self.environment[
                        ohostedcons.VMEnv.CONSOLE_TYPE
                    ]
                )
            )
            host = 'localhost'
            spice_values = [
                x.strip()
                for x in self.environment[
                    ohostedcons.VDSMEnv.SPICE_SUBJECT
                ].split(',')
                if x
            ]
            for items in spice_values:
                key, val = items.split('=', 1)
                if key == 'CN':
                    host = val
                    break

            self.dialog.note(
                _(
                    'Please note that in order to use remote-viewer you need '
                    'to be able to run graphical applications.\n'
                    'If you cannot run graphical applications you can '
                    'connect to the graphic console from another host or '
                    'connect to the console using the following command:\n'
                    'virsh -c qemu+tls://{host}/system console HostedEngine'
                ).format(
                    host=host
                )
            )
            self.dialog.note(
                _(
                    'If you need to reboot the VM you will need to start it '
                    'manually using the command:\n'
                    'hosted-engine --vm-start\n'
                    'You can then set a temporary password using '
                    'the command:\n'
                    'hosted-engine --add-console-password=<password>'
                )
            )

    def _wait_vm_destroyed(self):
        waiter = tasks.VMDownWaiter(self.environment)
        return waiter.wait()

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
        self._vdscommand = [self.command.get('vdsClient')]
        if self.environment[ohostedcons.VDSMEnv.USE_SSL]:
            self._vdscommand.append('-s')
        self._vdscommand.append('localhost')

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
        #Need to be done after firewall closeup for allowing the user to
        #connect from remote.
        os_installed = False
        while not os_installed:
            self._create()
            self.dialog.note(
                _(
                    'Please install the OS on the VM.\n'
                    'When the installation is completed reboot or shutdown '
                    'the VM: the system will wait until then'
                )
            )
            if not self._wait_vm_destroyed():
                #The VM is down but not destroyed
                cmd = self._vdscommand + [
                    'destroy',
                    self.environment[ohostedcons.VMEnv.VM_UUID],
                ]
                self.execute(
                    cmd,
                    raiseOnError=True
                )
            os_installed = self.dialog.queryString(
                name='OVEHOSTED_OS_INSTALLED',
                note=_(
                    'Has the OS installation been completed '
                    'successfully?\nAnswering no will allow you to reboot '
                    'from the previously selected boot media. '
                    '(@VALUES@)[@DEFAULT@]: '
                ),
                prompt=True,
                validValues=(_('Yes'), _('No')),
                caseSensitive=False,
                default=_('Yes')
            ) == _('Yes').lower()
            if (
                not os_installed and
                self.dialog.queryString(
                    name='OVEHOSTED_OS_INSTALL_AGAIN',
                    note=_(
                        'Do you want to try again the OS '
                        'installation? (@VALUES@)[@DEFAULT@]: '
                    ),
                    prompt=True,
                    validValues=(_('Yes'), _('No')),
                    caseSensitive=False,
                    default=_('Yes')
                ) == _('No').lower()
            ):
                #TODO: decide if we have to let the user do something
                #without abort, just exiting without any more automated
                #steps
                raise RuntimeError('OS installation aborted by user')

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
        self._create()


# vim: expandtab tabstop=4 shiftwidth=4
