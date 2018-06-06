#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2016 Red Hat, Inc.
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

"""Connect to Engine API"""


import gettext

from ovirt_hosted_engine_setup import constants as ohostedcons

import ovirtsdk4 as sdk4


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


def get_engine_api(
    base,
    timeout=None,
    attempts=ohostedcons.Defaults.DEFAULT_ENGINE_API_RETRY_ATTEMPTS,
):
    '''
    :param base: Reference to caller.
    :param timeout: Engine API timeout.
    '''
    valid = False
    engine_api = None
    fqdn = base.environment[
        ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
    ]
    while not valid and attempts > 0:
        attempts = attempts - 1
        try:
            base.logger.info(_('Connecting to Engine'))
            insecure = False
            if base.environment[
                ohostedcons.EngineEnv.INSECURE_SSL
            ]:
                insecure = True
            engine_api = sdk4.Connection(
                url='https://{fqdn}/ovirt-engine/api'.format(
                    fqdn=fqdn,
                ),
                username=base.environment[
                    ohostedcons.EngineEnv.ADMIN_USERNAME
                ],
                password=base.environment[
                    ohostedcons.EngineEnv.ADMIN_PASSWORD
                ],
                ca_file=base.environment[
                    ohostedcons.EngineEnv.TEMPORARY_CERT_FILE
                ],
                insecure=insecure,
                timeout=timeout if timeout else
                ohostedcons.Defaults.DEFAULT_ENGINE_API_TIMEOUT,
            )
            system_service = engine_api.system_service()
            clusters_service = system_service.clusters_service()
            clusters_service.list()
            valid = True
        except sdk4.ConnectionError as e:
            base.logger.debug(
                _(
                    'Cannot connect to Engine API on {fqdn}: \n'
                    'Trying again \n'
                ).format(
                    fqdn=fqdn,
                )
            )
        except sdk4.AuthError:
            if base.environment[
                ohostedcons.EngineEnv.INTERACTIVE_ADMIN_PASSWORD
            ]:
                if base.environment[
                    ohostedcons.EngineEnv.ADMIN_PASSWORD
                ] is not None:
                    base.logger.error(
                        _(
                            'The Engine API didn''t accept '
                            'the administrator password you provided.\n'
                            'Please enter it again to retry.'
                        )
                    )
                base.environment[
                    ohostedcons.EngineEnv.ADMIN_USERNAME
                ] = base.dialog.queryString(
                    name='ENGINE_ADMIN_USERNAME',
                    note=_(
                        'Enter engine admin username [@DEFAULT@]: '
                    ),
                    prompt=True,
                    default=ohostedcons.Defaults.DEFAULT_ADMIN_USERNAME,
                )
                base.environment[
                    ohostedcons.EngineEnv.ADMIN_PASSWORD
                ] = base.dialog.queryString(
                    name='ENGINE_ADMIN_PASSWORD',
                    note=_(
                        'Enter engine admin password: '
                    ),
                    prompt=True,
                    hidden=True,
                )
            else:
                raise RuntimeError(
                    _(
                        'The Engine API didn''t accept '
                        'the administrator password you provided\n'
                    )
                )

        except sdk4.Error as e:
            base.logger.debug(
                _(
                    'Cannot connect to Engine API on {fqdn}:\n'
                    '{details}\n'
                ).format(
                    fqdn=fqdn,
                    details=e,
                )
            )
    if not valid:
        raise RuntimeError(
            _(
                'Cannot connect to Engine API on {fqdn}'
            ).format(
                fqdn=fqdn,
            )
        )
    return engine_api


# vim: expandtab tabstop=4 shiftwidth=4
