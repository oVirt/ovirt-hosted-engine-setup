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


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
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
    )
    def _closeup(self):
        poll = True
        fqdn = self.environment[
            ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
        ]
        live_checker = check_liveliness.LivelinessChecker()
        if not self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]:
            self.dialog.note(
                _('Please install the engine in the VM.')
            )
            self.dialog.note(
                _(
                    'You may also be interested in '
                    'installing ovirt-guest-agent-common package '
                    'in the VM.'
                )
            )
            self.dialog.queryString(
                name='OVEHOSTED_ENGINE_UP',
                note=_(
                    'Hit enter when finished.'
                ),
                prompt=True,
                default='y'  # Allow enter without any value
            )
        while poll:
            if live_checker.isEngineUp(fqdn):
                poll = False
            elif self.dialog.queryString(
                name='OVEHOSTED_ENGINE_CHECK_AGAIN',
                note=_(
                    'Engine health status page is not yet reachable.\n'
                    'Please ensure that the engine is correctly configured, '
                    'up and running.\n '
                    'Do you want to check again or abort? '
                    '(@VALUES@)[@DEFAULT@]: '
                ),
                prompt=True,
                validValues=(
                    _('Check'),
                    _('Abort'),
                ),
                caseSensitive=False,
                default=_('Check')
            ) != _('Check').lower():
                #TODO: decide if we have to let the user do something
                #without abort, just exiting without any more automated
                #steps
                raise RuntimeError('Engine polling aborted by user')


# vim: expandtab tabstop=4 shiftwidth=4
