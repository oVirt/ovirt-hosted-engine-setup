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
cpu check plugin.
"""


import sys
import gettext


from otopi import util
from otopi import plugin


from ovirt_host_deploy import hardware


from ovirt_hosted_engine_setup import constants as ohostedcons


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
cpu check plugin.
    """
    CPU_FAMILIES = (
        {'model': 'model_Westmere', 'name': 'Intel Westmere Family'},
        {'model': 'model_Nehalem', 'name': 'Intel Nehalem Family'},
        {'model': 'model_Penryn', 'name': 'Intel Penryn Family'},
        {'model': 'model_Conroe', 'name': 'Intel Conroe Family'},
        {'model': 'model_Opteron_G3', 'name': 'AMD Opteron G3'},
        {'model': 'model_Opteron_G2', 'name': 'AMD Opteron G2'},
        {'model': 'model_Opteron_G1', 'name': 'AMD Opteron G1'},
    )

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    def _getCompatibleCpuModels(self):
        self.logger.debug('Attempting to load the caps vdsm module')
        savedPath = sys.path
        ret = None
        try:
            sys.path.append(ohostedcons.FileLocations.VDS_CLIENT_DIR)
            caps = util.loadModule(
                path=ohostedcons.FileLocations.VDS_CLIENT_DIR,
                name='caps',
            )
            ret = (
                caps.CpuInfo().model(),
                caps._getCompatibleCpuModels(),
            )
        finally:
            sys.path = savedPath
        return ret

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment[ohostedcons.VDSMEnv.VDSM_CPU] = None

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
        priority=plugin.Stages.PRIORITY_HIGH,
    )
    def _setup(self):
        virtualization = hardware.Virtualization()
        result = virtualization.detect()
        if result == virtualization.DETECT_RESULT_UNSUPPORTED:
            raise RuntimeError(
                _('Hardware does not support virtualization')
            )
        elif result == virtualization.DETECT_RESULT_SUPPORTED:
            self.logger.info(_('Hardware supports virtualization'))
        else:
            self.logger.warning(
                _('Cannot detect if hardware supports virtualization')
            )

    @plugin.event(
        stage=plugin.Stages.STAGE_VALIDATION,
    )
    def _validation(self):
        cpu, compatible = self._getCompatibleCpuModels()
        self.logger.debug(
            'Compatible CPU models are: %s',
            compatible,
        )

        supported = (
            set([entry['model'] for entry in self.CPU_FAMILIES]) &
            set(compatible)
        )
        # We want the best cpu between compatible.
        # The preference is defined by the order of
        # CPU_FAMILIES
        # We need to save the corresponding CPU name for cluster
        # creation.
        for entry in self.CPU_FAMILIES:
            if entry['model'] in supported:
                self.environment[
                    ohostedcons.VDSMEnv.VDSM_CPU
                ] = entry['name']
                break


# vim: expandtab tabstop=4 shiftwidth=4
