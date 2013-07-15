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
import re


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

    _RE_SUBJECT = re.compile(
        flags=re.VERBOSE,
        pattern=r"""
            ^
            \s+
            Subject:\s*
            (?P<subject>O=\w+, CN=.*)
            $
        """
    )

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

    def _generateUserMessage(self, console_type):
        if console_type == 'vnc':
            return _(
                'You can now connect to the VM with the following command:\n'
                '\t{remote} vnc://localhost:5900\nUse temporary password '
                '"{password}" to connect to vnc console.'
            ).format(
                remote=self.command.get('remote-viewer'),
                password=self.environment[
                    ohostedcons.VMEnv.VM_PASSWD
                ],
            )
        elif console_type == 'spice':
            subject = ''
            out, rc = self.execute(
                (
                    self.command.get('openssl'),
                    'x509',
                    '-noout',
                    '-text',
                    '-in', ohostedcons.FileLocations.LIBVIRT_SERVER_CERT
                ),
                raiseOnError=True
            )
            for line in out.splitlines():
                matcher = self._RE_SUBJECT.match(line)
                if matcher is not None:
                    subject = matcher.group('param')
                    break

            return _(
                'You can now connect to the VM with the following command:\n'
                '\t{remote} --spice-ca-file={ca_cert} '
                'spice://localhost?tls-port=5900 '
                '"--spice-host-subject=${subject}"\nUse temporary password '
                '"{password}" to connect to spice console.'
            ).format(
                remote=self.command.get('remove-viewer'),
                ca_cert=ohostedcons.FileLocations.LIBVIRT_CA_CERT,
                subject=subject,
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
            self._generateUserMessage(
                self.environment[
                    ohostedcons.VMEnv.CONSOLE_TYPE
                ]
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
        self.command.detect('openssl')

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
    )
    def _customization(self):
        validConsole = False
        interactive = self.environment[
            ohostedcons.VMEnv.CONSOLE_TYPE
        ] is None
        while not validConsole:
            if self.environment[
                ohostedcons.VMEnv.CONSOLE_TYPE
            ] is None:
                self.environment[
                    ohostedcons.VMEnv.CONSOLE_TYPE
                ] = self.dialog.queryString(
                    name='OVEHOSTED_VM_CONSOLE_TYPE',
                    note=_(
                        'Please specify the console type '
                        'you would like to use to connect '
                        'to the VM (@VALUES@) [@DEFAULT@]: '
                    ),
                    prompt=True,
                    caseSensitive=False,
                    validValues=[
                        'vnc',
                        'spice',
                    ],
                    default='vnc',
                )

                if self.environment[
                    ohostedcons.VMEnv.CONSOLE_TYPE
                ] in ('vnc', 'spice'):
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
                    'The system will wait until the installation is completed'
                )
            )
            if not self._wait_vm_destroyed():
                #The VM is down but not destroyed
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
            os_installed = self.dialog.queryString(
                name='ovehosted_os_installed',
                note=_(
                    'Has the OS installation been completed '
                    'successfully? (@VALUES@) :'
                ),
                prompt=True,
                validValues=[_('Yes'), _('No')],
                caseSensitive=False,
                default=_('Yes')
            ) == _('Yes').lower()
            if (
                not os_installed and
                self.dialog.queryString(
                    name='ovehosted_os_install_again',
                    note=_(
                        'Do you want to try again the OS '
                        'installation? (@VALUES@) :'
                    ),
                    prompt=True,
                    validValues=[_('Yes'), _('No')],
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
        after=[
            ohostedcons.Stages.OS_INSTALLED,
        ],
        name=ohostedcons.Stages.INSTALLED_VM_RUNNING,
    )
    def _boot_from_hd(self):
        self._create()


# vim: expandtab tabstop=4 shiftwidth=4
