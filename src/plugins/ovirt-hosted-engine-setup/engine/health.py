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
engine health status handler plugin.
"""


import gettext


from otopi import util
from otopi import plugin


from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import check_liveliness
from ovirt_hosted_engine_setup import mixins


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(mixins.VmOperations, plugin.PluginBase):
    """
    engine health status handler plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        after=(
            ohostedcons.Stages.INSTALLED_VM_RUNNING,
        ),
        name=ohostedcons.Stages.ENGINE_ALIVE,
        condition=lambda self: (
            not self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]
        ),
    )
    def _closeup(self):
        poll = True
        fqdn = self.environment[
            ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
        ]
        live_checker = check_liveliness.LivelinessChecker()
        self.dialog.note(
            _('Please install and setup the engine in the VM.')
        )
        self.dialog.note(
            _(
                'You may also be interested in '
                'installing ovirt-guest-agent-common package '
                'in the VM.'
            )
        )
        while poll:
            response = self.dialog.queryString(
                name='OVEHOSTED_ENGINE_UP',
                note=_(
                    'To continue make a selection from the options below:\n'
                    '(1) Continue setup - engine installation is complete\n'
                    '(2) Power off and restart the VM\n'
                    '(3) Abort setup\n\n(@VALUES@)[@DEFAULT@]: '
                ),
                prompt=True,
                validValues=(_('1'), _('2'), _('3')),
                default=_('1'),
                caseSensitive=False)
            if response == _('1').lower():
                if live_checker.isEngineUp(fqdn):
                    poll = False
                else:
                    self.dialog.note(
                        _('Engine health status page is not yet reachable.\n')
                    )
            elif response == _('2').lower():
                self._destroy_vm()
                self._create_vm()
            elif response == _('3').lower():
                raise RuntimeError('Engine polling aborted by user')
            else:
                self.logger.error(
                    'Invalid option \'{0}\''.format(response)
                )


# vim: expandtab tabstop=4 shiftwidth=4
