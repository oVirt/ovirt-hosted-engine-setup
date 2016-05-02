#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2013-2016 Red Hat, Inc.
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
import math
import time


from otopi import plugin
from otopi import util


from ovirt_hosted_engine_setup import check_liveliness
from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import mixins
from ovirt_hosted_engine_setup import appliance_esetup


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(
    appliance_esetup.ApplianceEngineSetup,
    mixins.VmOperations,
    plugin.PluginBase
):
    """
    engine health status handler plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._socket = None

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.EngineEnv.ENGINE_SETUP_TIMEOUT,
            ohostedcons.Defaults.DEFAULT_ENGINE_SETUP_TIMEOUT
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        after=(
            ohostedcons.Stages.INSTALLED_VM_RUNNING,
            ohostedcons.Stages.UPGRADED_APPLIANCE_RUNNING,
        ),
        name=ohostedcons.Stages.ENGINE_ALIVE,
        condition=lambda self: (
            not self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]
        ),
    )
    def _closeup(self):
        esexecuting = self.environment[
            ohostedcons.CloudInit.EXECUTE_ESETUP
        ]
        fqdn = self.environment[
            ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
        ]
        live_checker = check_liveliness.LivelinessChecker()
        # manual engine setup execution
        if not esexecuting:
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
            while not check_liveliness.manualSetupDispatcher(
                self,
                check_liveliness.MSD_ENGINE_INSTALLED,
                fqdn
            ):
                pass

        # automated engine setup execution on the appliance
        else:
            spath = (
                ohostedcons.Const.OVIRT_HE_CHANNEL_PATH +
                self.environment[
                    ohostedcons.VMEnv.VM_UUID
                ] + '.' +
                ohostedcons.Const.OVIRT_HE_CHANNEL_NAME
            )
            self.logger.debug(
                'Connecting to the appliance on {spath}'.format(spath=spath)
            )
            self._appliance_connect(spath)
            completed = False
            TIMEOUT = 5
            nTimeout5 = int(math.ceil(
                float(
                    self.environment[
                        ohostedcons.EngineEnv.ENGINE_SETUP_TIMEOUT
                    ]
                ) / TIMEOUT
            ))

            self.logger.info(_('Running engine-setup on the appliance'))
            rtimeouts = 0
            while not completed:
                line, timeout = self._appliance_readline_nb(TIMEOUT)
                if line:
                    self.dialog.note('|- ' + line + '\n')
                if timeout:
                    rtimeouts += 1
                else:
                    rtimeouts = 0
                if rtimeouts >= nTimeout5:
                    self.logger.error(
                        'Engine setup got stuck on the appliance'
                    )
                    raise RuntimeError(
                        _(
                            'Engine setup is stalled on the appliance '
                            'since {since} seconds ago.\n'
                            'Please check its log on the appliance.\n'
                        ).format(since=TIMEOUT*nTimeout5)
                    )
                if ohostedcons.Const.E_RESTORE_SUCCESS_STRING in line:
                    self.logger.info(
                        'Engine backup successfully restored'
                    )
                elif ohostedcons.Const.E_RESTORE_FAIL_STRING in line:
                    self.logger.error(
                        'Engine backup restore failed on the appliance'
                    )
                    raise RuntimeError(
                        _(
                            'engine-backup failed restoring the engine backup '
                            'on the appliance\n'
                            'Please check its log on the appliance.\n'
                        ).format(since=TIMEOUT*nTimeout5)
                    )
                elif ohostedcons.Const.E_SETUP_SUCCESS_STRING in line:
                    completed = True
                elif ohostedcons.Const.E_SETUP_FAIL_STRING in line:
                    self.logger.error(
                        'Engine setup failed on the appliance'
                    )
                    raise RuntimeError(
                        _(
                            'Engine setup failed on the appliance\n'
                            'Please check its log on the appliance.\n'
                        ).format(since=TIMEOUT*nTimeout5)
                    )
                # TODO: prefer machine dialog for more robust interaction
            self.logger.debug('Engine-setup successfully completed ')
            self.logger.info(_('Engine-setup successfully completed '))
            self._appliance_disconnect()
            cengineup = 0
            waitEngineUP = True
            while waitEngineUP:
                if live_checker.isEngineUp(fqdn):
                    waitEngineUP = False
                else:
                    cengineup += 1
                    if cengineup >= 20:
                        self.logger.error(_('Engine is still not reachable'))
                        raise RuntimeError(_('Engine is still not reachable'))
                    self.logger.info(
                        _('Engine is still not reachable, waiting...')
                    )
                    time.sleep(15)


# vim: expandtab tabstop=4 shiftwidth=4
