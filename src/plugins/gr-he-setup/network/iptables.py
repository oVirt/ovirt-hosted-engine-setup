#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2014-2015 Red Hat, Inc.
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
iptables plugin.
"""


import gettext
import platform

from otopi import constants
from otopi import plugin
from otopi import util


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    iptables plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._distribution = platform.linux_distribution(
            full_distribution_name=0
        )[0]
        self._enabled = False

    @plugin.event(
        stage=plugin.Stages.STAGE_VALIDATION,
        condition=(
            lambda self: self.environment[constants.NetEnv.IPTABLES_ENABLE]
        ),
    )
    def _validate(self):
        if self._distribution not in ('redhat', 'fedora', 'centos'):
            self.logger.warning(
                _('Unsupported distribution for iptables plugin')
            )
        else:
            self._enabled = True

    @plugin.event(
        stage=plugin.Stages.STAGE_EARLY_MISC,
        condition=lambda self: self._enabled,
    )
    def _early_misc(self):
        # We would like to avoid conflict and we need to stop firewalld
        # before restarting libvirt: BZ#1057139
        if self.services.exists('firewalld'):
            self.services.startup('firewalld', False)
            self.services.state('firewalld', False)


# vim: expandtab tabstop=4 shiftwidth=4
