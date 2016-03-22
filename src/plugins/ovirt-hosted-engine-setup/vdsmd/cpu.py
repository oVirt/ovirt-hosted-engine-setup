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


"""
cpu check plugin.
"""


import gettext


from otopi import plugin
from otopi import util


from ovirt_host_deploy import hardware


from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    cpu check plugin.
    """

    # CPU list from ovirt-engine: git grep ServerCPUList | grep 3.6
    CPU_FAMILIES = (
        {
            'model': 'model_Broadwell',
            'name': 'Intel Broadwell Family'
        },
        {
            'model': 'model_Broadwell-noTSX',
            'name': 'Intel Broadwell-noTSX Family'
        },
        {
            'model': 'model_Haswell',
            'name': 'Intel Haswell Family'
        },
        {
            'model': 'model_Haswell-noTSX',
            'name': 'Intel Haswell-noTSX Family'
        },
        {
            'model': 'model_SandyBridge',
            'name': 'Intel SandyBridge Family'
        },
        {
            'model': 'model_Westmere',
            'name': 'Intel Westmere Family'
        },
        {
            'model': 'model_Nehalem',
            'name': 'Intel Nehalem Family'
        },
        {
            'model': 'model_Penryn',
            'name': 'Intel Penryn Family'
        },
        {
            'model': 'model_Conroe',
            'name': 'Intel Conroe Family'
        },
        {
            'model': 'model_Opteron_G5',
            'name': 'AMD Opteron G5'
        },
        {
            'model': 'model_Opteron_G4',
            'name': 'AMD Opteron G4'
        },
        {
            'model': 'model_Opteron_G3',
            'name': 'AMD Opteron G3'
        },
        {
            'model': 'model_Opteron_G2',
            'name': 'AMD Opteron G2'
        },
        {
            'model': 'model_Opteron_G1',
            'name': 'AMD Opteron G1'
        },
    )

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    def _getCompatibleCpuModels(self):
        cli = self.environment[ohostedcons.VDSMEnv.VDS_CLI]
        caps = cli.getVdsCapabilities()
        if caps['status']['code'] != 0:
            raise RuntimeError(caps['status']['message'])
        cpuModel = caps['info']['cpuModel']
        cpuCompatibles = [
            x for x in caps['info']['cpuFlags'].split(',')
            if x.startswith('model_')
        ]
        ret = (
            cpuModel,
            cpuCompatibles
        )
        return ret

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.VDSMEnv.VDSM_CPU,
            None
        )
        self.environment.setdefault(
            ohostedcons.VDSMEnv.ENGINE_CPU,
            None
        )

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
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_VM,
            ohostedcons.Stages.CONFIG_OVF_IMPORT,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_VM,
        ),
    )
    def _customization(self):
        cpu, compatible = self._getCompatibleCpuModels()

        if len(compatible) == 0:
            raise RuntimeError(
                _('Hardware virtualization support is not available:\n'
                  'please check BIOS settings and turn on NX support '
                  'if available')
            )
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
        best = ''
        cpu_desc = ''
        for entry in self.CPU_FAMILIES:
            if entry['model'] in supported:
                if best == '':
                    best = entry['model']
                cpu_desc += '\t - {model}: {name}\n'.format(
                    model=entry['model'],
                    name=entry['name'],
                )

        self.dialog.note(
            _(
                'The following CPU types are supported by this host:\n'
                '{types_list}'
            ).format(
                types_list=cpu_desc,
            )
        )
        interactive = False
        if not self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]:
            interactive = self.environment[
                ohostedcons.VDSMEnv.VDSM_CPU
            ] is None
        valid = False
        while not valid:
            if interactive:
                self.environment[
                    ohostedcons.VDSMEnv.VDSM_CPU
                ] = self.dialog.queryString(
                    name='ovehosted_vmenv_cpu_type',
                    note=_(
                        'Please specify the CPU type to be used by the VM '
                        '[@DEFAULT@]: '
                    ),
                    prompt=True,
                    default=best,
                    validValues=supported
                )
            if self.environment[ohostedcons.VDSMEnv.VDSM_CPU] in supported:
                valid = True
            elif not interactive:
                raise RuntimeError(
                    _('Invalid CPU type specified: {cpu_type}').format(
                        cpu_type=self.environment[
                            ohostedcons.VDSMEnv.VDSM_CPU
                        ],
                    )
                )
            else:
                self.logger.error(
                    _('Invalid CPU type specified: {cpu_type}').format(
                        cpu_type=self.environment[
                            ohostedcons.VDSMEnv.VDSM_CPU
                        ],
                    )
                )
        for entry in self.CPU_FAMILIES:
            if (
                entry['model'] == self.environment[
                    ohostedcons.VDSMEnv.VDSM_CPU
                ]
            ):
                self.environment[
                    ohostedcons.VDSMEnv.ENGINE_CPU
                ] = entry['name']
                break


# vim: expandtab tabstop=4 shiftwidth=4
