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


import contextlib
import gettext
import urllib2


from otopi import util
from otopi import plugin


from ovirt_hosted_engine_setup import constants as ohostedcons


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    engine health status handler plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    def _isEngineUp(self):
        self.logger.debug('Checking for Engine health status')
        health_url = 'http://{fqdn}/OvirtEngineWeb/HealthStatus'.format(
            fqdn=self.environment[
                ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
            ],
        )
        isUp = False
        try:
            with contextlib.closing(urllib2.urlopen(health_url)) as urlObj:
                content = urlObj.read()
                if content:
                    self.logger.info(
                        _('Engine is up with status: {status}').format(
                            status=content,
                        )
                    )
                    isUp = True
        except urllib2.URLError:
            self.logger.error(_('Engine is still unreachable'))
        return isUp

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        after=[
            ohostedcons.Stages.INSTALLED_VM_RUNNING,
        ],
        name=ohostedcons.Stages.ENGINE_ALIVE,
    )
    def _misc(self):
        poll = True
        while poll:
            self.dialog.queryString(
                name='ovehosted_engine_up',
                note=_(
                    'Please install the engine in the vm,'
                    'hit enter when finished.'
                ),
                prompt=True,
                default='y'  # Allow enter without any value
            )
            if self._isEngineUp():
                poll = False
            elif self.dialog.queryString(
                name='ovehosted_engine_check_again',
                note=_(
                    'Engine health status page is not yet reachable.\n'
                    'Please ensure that the engine is correctly configured, '
                    'up and running.\n '
                    'Do you want to check again or abort? (@VALUES@) :'
                ),
                prompt=True,
                validValues=[_('Check'), _('Abort')],
                caseSensitive=False,
                default=_('Check')
            ) != _('Check').lower():
                #TODO: decide if we have to let the user do something
                #without abort, just exiting without any more automated
                #steps
                raise RuntimeError('Engine polling aborted by user')


# vim: expandtab tabstop=4 shiftwidth=4
