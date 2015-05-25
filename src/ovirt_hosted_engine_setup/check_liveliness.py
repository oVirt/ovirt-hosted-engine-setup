#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2013-2015 Red Hat, Inc.
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

"""Check for engine liveliness"""


import contextlib
import gettext
import re
import urllib2


from otopi import base
from otopi import util


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


def manualSetupDispatcher(base, os_installed=False, engine_fqdn=None):
    '''
    :param base: Reference to caller.
    :param os_installed: specifies state of installation.
    :param engine_fqdn: When provided specifies engine hostname.
    :return: True if manual setup is ready.
    '''
    response = ''
    if not os_installed:
        response = base.dialog.queryString(
            name='OVEHOSTED_INSTALLING_OS',
            note=_(
                '\n\nThe VM has been started.\n'
                'To continue please install OS and shutdown or reboot the '
                'VM.\n\n'
                'Make a selection from the options below:\n'
                '(1) Continue setup - OS installation is complete\n'
                '(2) Power off and restart the VM\n'
                '(3) Abort setup\n'
                '(4) Destroy VM and abort setup\n'
                '\n(@VALUES@)[@DEFAULT@]: '
            ),
            prompt=True,
            validValues=(_('1'), _('2'), _('3'), _('4')),
            default=_('1'),
            caseSensitive=False
        )
    else:
        response = base.dialog.queryString(
            name='OVEHOSTED_ENGINE_UP',
            note=_(
                '\n\nThe VM has been rebooted.\n'
                'To continue please install oVirt-Engine in the VM \n(Follow '
                'http://www.ovirt.org/Quick_Start_Guide for more info)\n\n'
                'Make a selection from the options below:\n'
                '(1) Continue setup - oVirt-Engine installation is ready and '
                'ovirt-engine service is up\n'
                '(2) Power off and restart the VM\n'
                '(3) Abort setup\n'
                '(4) Destroy VM and abort setup\n'
                '\n(@VALUES@)[@DEFAULT@]: '
            ),
            prompt=True,
            validValues=(_('1'), _('2'), _('3'), _('4')),
            default=_('1'),
            caseSensitive=False
        )
    if response == _('1').lower():
        if not os_installed:
            base.dialog.note(_(
                '\nPlease reboot or shutdown the VM. \n\n'
                'Verifying shutdown...\n'
            ))
            if not base._wait_vm_destroyed():
                base._destroy_vm()
            return True
        elif engine_fqdn is not None:
            base.dialog.note(_(
                '\nChecking for oVirt-Engine status at {fqdn}...\n'
            ).format(
                fqdn=engine_fqdn,
            ))
            live_checker = LivelinessChecker()
            if live_checker.isEngineUp(engine_fqdn):
                return True
            else:
                base.dialog.note(_(
                    'oVirt-Engine health status page is not yet reachable.\n'
                ))
        else:
            base.dialog.note(_(
                'Invalid state - Os is installed but fqdn is not provided.\n'
            ))
    elif response == _('2').lower():
        base._destroy_vm()
        base._create_vm()
    elif response == _('3').lower():
        raise RuntimeError('Setup aborted by user')
    elif response == _('4').lower():
        base._destroy_vm()
        raise RuntimeError(
            _('VM destroyed and setup aborted by user')
        )
    else:
        base.logger.error(
            'Invalid option \'{0}\''.format(response)
        )
    return False


@util.export
class LivelinessChecker(base.Base):

    DB_UP_RE = re.compile('.*DB Up.*')
    TIMEOUT = 20

    def __init__(self):
        super(LivelinessChecker, self).__init__()

    def isEngineUp(self, fqdn):
        self.logger.debug('Checking for Engine health status')
        health_url = 'http://{fqdn}/ovirt-engine/services/health'.format(
            fqdn=fqdn,
        )
        isUp = False
        try:
            with contextlib.closing(
                urllib2.urlopen(
                    url=health_url,
                    timeout=self.TIMEOUT,
                )
            ) as urlObj:
                content = urlObj.read()
                if content:
                    if self.DB_UP_RE.match(content) is not None:
                        isUp = True
                    self.logger.info(
                        _('Engine replied: {status}').format(
                            status=content,
                        )
                    )
        except urllib2.URLError:
            self.logger.error(_('Engine is still unreachable'))
        return isUp


if __name__ == "__main__":
    import sys

    from ovirt_hosted_engine_setup import constants as ohostedcons
    config_re = re.compile('^(?P<key>[^=]+)=(?P<value>.*)$')
    config = {}
    try:
        with open(
            ohostedcons.FileLocations.OVIRT_HOSTED_ENGINE_SETUP_CONF
        ) as f:
            content = f.read().splitlines()
            for line in content:
                match = config_re.match(line)
                if match:
                    key = match.group('key')
                    value = match.group('value')
                    config[key] = value
    except IOError:
        sys.stderr.write(_('Error reading the configuration file\n'))
        sys.exit(2)
    if 'fqdn' not in config:
        sys.stderr.write(
            _(
                'Incomplete configuration, missing FQDN '
                'of the hosted engine VM\n'
            )
        )
        sys.exit(2)

    live_checker = LivelinessChecker()
    if not live_checker.isEngineUp(config['fqdn']):
        print _('Hosted Engine is not up!')
        sys.exit(1)
    print _('Hosted Engine is up!')


# vim: expandtab tabstop=4 shiftwidth=4
