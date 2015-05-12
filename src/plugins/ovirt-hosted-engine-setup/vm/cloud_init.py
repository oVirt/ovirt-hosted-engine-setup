#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2015 Red Hat, Inc.
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
VM cloud-init configuration plugin.
"""


import gettext
import os
import pwd
import shutil
import tempfile

from otopi import constants as otopicons
from otopi import plugin
from otopi import util


from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    VM cloud-init configuration plugin.
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._enable = False
        self._directory_name = None

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.VMEnv.GENERATE_CLOUD_INIT_ISO,
            None
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.CLOUD_INIT_ROOTPWD,
            None
        )
        self.environment[otopicons.CoreEnv.LOG_FILTER_KEYS].append(
            ohostedcons.VMEnv.CLOUD_INIT_ROOTPWD
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.CLOUD_INIT_INSTANCE_HOSTNAME,
            None
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.CLOUD_INIT_EXECUTE_ESETUP,
            None
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.AUTOMATE_VM_SHUTDOWN,
            None
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_SETUP,
    )
    def _setup(self):
        self.command.detect('genisoimage')

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_VM,
            ohostedcons.Stages.CONFIG_BOOT_DEVICE,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_VM,
        ),
        condition=lambda self: (
            self.environment[ohostedcons.VMEnv.BOOT] == 'disk' and
            self.environment[ohostedcons.VMEnv.CDROM] is None and
            not self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]

        ),
        name=ohostedcons.Stages.CONFIG_CLOUD_INIT_OPTIONS,
    )
    def _customization(self):
        interactive = set([
            self.environment[ohostedcons.VMEnv.GENERATE_CLOUD_INIT_ISO],
            self.environment[ohostedcons.VMEnv.CLOUD_INIT_ROOTPWD],
            self.environment[ohostedcons.VMEnv.CLOUD_INIT_INSTANCE_HOSTNAME],
            self.environment[ohostedcons.VMEnv.CLOUD_INIT_EXECUTE_ESETUP],
        ]) == set([None])

        if interactive:
            if self.dialog.queryString(
                name='CLOUD_INIT_USE',
                note=_(
                    'Would you like to use cloud-init to customize the '
                    'appliance on the first boot '
                    '(@VALUES@)[@DEFAULT@]? '
                ),
                prompt=True,
                validValues=(_('Yes'), _('No')),
                caseSensitive=False,
                default=_('Yes')
            ) == _('Yes').lower():
                if self.dialog.queryString(
                    name='CLOUD_INIT_GENERATE',
                    note=_(
                        'Would you like to generate on-fly a cloud-init '
                        'no-cloud ISO image\n'
                        'or do you have an existing one '
                        '(@VALUES@)[@DEFAULT@]? '
                    ),
                    prompt=True,
                    validValues=(_('Generate'), _('Existing')),
                    caseSensitive=False,
                    default=_('Generate')
                ) == _('Generate').lower():
                    self.environment[
                        ohostedcons.VMEnv.GENERATE_CLOUD_INIT_ISO
                    ] = ohostedcons.Const.CLOUD_INIT_GENERATE
                else:
                    self.environment[
                        ohostedcons.VMEnv.GENERATE_CLOUD_INIT_ISO
                    ] = ohostedcons.Const.CLOUD_INIT_EXISTING
            else:
                self.environment[
                    ohostedcons.VMEnv.GENERATE_CLOUD_INIT_ISO
                ] = ohostedcons.Const.CLOUD_INIT_SKIP
            if self.environment[
                ohostedcons.VMEnv.GENERATE_CLOUD_INIT_ISO
            ] == ohostedcons.Const.CLOUD_INIT_GENERATE:
                instancehname = self.dialog.queryString(
                    name='CI_INSTANCE_HOSTNAME',
                    note=_(
                        'Please provide the FQDN you would like to use for '
                        'the engine appliance.\n'
                        'Note: This will be the FQDN of the engine VM '
                        'you are now going to launch,\nit should not '
                        'point to the base host or to any other '
                        'existing machine.\n'
                        'Engine VM FQDN: (leave it empty to skip): '
                    ),
                    prompt=True,
                    default='',
                )
                if instancehname:
                    self.environment[
                        ohostedcons.VMEnv.CLOUD_INIT_INSTANCE_HOSTNAME
                    ] = instancehname
                else:
                    self.environment[
                        ohostedcons.VMEnv.CLOUD_INIT_INSTANCE_HOSTNAME
                    ] = False

                while self.environment[
                    ohostedcons.VMEnv.CLOUD_INIT_ROOTPWD
                ] is None:
                    password = self.dialog.queryString(
                        name='CI_ROOT_PASSWORD',
                        note=_(
                            "Enter root password that "
                            'will be used for the engine appliance '
                            '(leave it empty to skip): '
                        ),
                        prompt=True,
                        hidden=True,
                        default='',
                    )
                    if password:
                        password_check = self.dialog.queryString(
                            name='CI_ROOT_PASSWORD',
                            note=_(
                                "Confirm appliance root password: "
                            ),
                            prompt=True,
                            hidden=True,
                        )
                        if password == password_check:
                            self.environment[
                                ohostedcons.VMEnv.CLOUD_INIT_ROOTPWD
                            ] = password
                        else:
                            self.logger.error(_('Passwords do not match'))
                    else:
                        self.environment[
                            ohostedcons.VMEnv.CLOUD_INIT_ROOTPWD
                        ] = False

                self.environment[
                    ohostedcons.VMEnv.CLOUD_INIT_EXECUTE_ESETUP
                ] = self.dialog.queryString(
                    name='CI_EXECUTE_ESETUP',
                    note=_(
                        'Automatically execute '
                        'engine-setup on the engine appliance on first boot '
                        '(@VALUES@)[@DEFAULT@]? '
                    ),
                    prompt=True,
                    validValues=(_('Yes'), _('No')),
                    caseSensitive=False,
                    default=_('Yes')
                ) == _('Yes').lower()

        if self.environment[
            ohostedcons.VMEnv.CLOUD_INIT_EXECUTE_ESETUP
        ] and self.environment[
            ohostedcons.VMEnv.AUTOMATE_VM_SHUTDOWN
        ] is None:
            self.environment[
                ohostedcons.VMEnv.AUTOMATE_VM_SHUTDOWN
            ] = self.dialog.queryString(
                name='AUTOMATE_VM_SHUTDOWN',
                note=_(
                    'Automatically restart the engine VM '
                    'as a monitored service after engine-setup '
                    '(@VALUES@)[@DEFAULT@]? '
                ),
                prompt=True,
                validValues=(_('Yes'), _('No')),
                caseSensitive=False,
                default=_('Yes')
            ) == _('Yes').lower()

        if (
            self.environment[
                ohostedcons.VMEnv.CLOUD_INIT_ROOTPWD
            ] or
            self.environment[
                ohostedcons.VMEnv.CLOUD_INIT_INSTANCE_HOSTNAME
            ] or
            self.environment[
                ohostedcons.VMEnv.CLOUD_INIT_EXECUTE_ESETUP
            ]
        ):
            self.environment[
                ohostedcons.VMEnv.GENERATE_CLOUD_INIT_ISO
            ] = ohostedcons.Const.CLOUD_INIT_GENERATE
            self._enable = True

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        condition=lambda self: self._enable,
    )
    def _misc(self):
        self._directory_name = tempfile.mkdtemp()
        user_data = (
            '#cloud-config\n'
            '# vim: syntax=yaml\n'
        )
        f_user_data = os.path.join(self._directory_name, 'user-data')
        if self.environment[ohostedcons.VMEnv.CLOUD_INIT_ROOTPWD]:
            # TODO: use salted hashed password
            user_data += (
                'ssh_pwauth: True\n'
                'chpasswd:\n'
                '  list: |\n'
                '    root:{password}\n'
                '  expire: False\n'
            ).format(
                password=self.environment[
                    ohostedcons.VMEnv.CLOUD_INIT_ROOTPWD
                ],
            )

        if self.environment[ohostedcons.VMEnv.CLOUD_INIT_EXECUTE_ESETUP]:
            org = 'Test'
            if '.' in self.environment[
                ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
            ]:
                org = self.environment[
                    ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
                ].split('.', 1)[1]

            user_data += (
                'write_files:\n'
                ' - content: |\n'
                '     [environment:default]\n'
                '     OVESETUP_CONFIG/adminPassword=str:{password}\n'
                '     OVESETUP_CONFIG/fqdn=str:{fqdn}\n'
                '     OVESETUP_PKI/organization=str:{org}\n'
                '   path: {heanswers}\n'
                '   owner: root:root\n'
                '   permissions: \'0640\'\n'
                'runcmd:\n'
                ' - /usr/bin/engine-setup --offline'
                ' --config-append={applianceanswers}'
                ' --config-append={heanswers}'
                ' 1>{port}'
                ' 2>&1\n'
                ' - if [ $? -eq 0 ];'
                ' then echo "{success_string}" >{port};'
                ' else echo "{fail_string}" >{port};'
                ' fi\n'
                ' - rm {heanswers}'
            ).format(
                fqdn=self.environment[
                    ohostedcons.NetworkEnv.OVIRT_HOSTED_ENGINE_FQDN
                ],
                org=org,
                password=self.environment[
                    ohostedcons.EngineEnv.ADMIN_PASSWORD
                ],
                applianceanswers=ohostedcons.Const.CLOUD_INIT_APPLIANCEANSWERS,
                heanswers=ohostedcons.Const.CLOUD_INIT_HEANSWERS,
                port=(
                    ohostedcons.Const.VIRTIO_PORTS_PATH +
                    ohostedcons.Const.OVIRT_HE_CHANNEL_NAME
                ),
                success_string=ohostedcons.Const.E_SETUP_SUCCESS_STRING,
                fail_string=ohostedcons.Const.E_SETUP_FAIL_STRING,
            )

        f = open(f_user_data, 'w')
        f.write(user_data)
        f.close()

        meta_data = ''
        f_meta_data = os.path.join(self._directory_name, 'meta-data')
        if self.environment[ohostedcons.VMEnv.CLOUD_INIT_INSTANCE_HOSTNAME]:
            meta_data = (
                'instance-id: {instance}\n'
                'local-hostname: {hostname}\n'
            ).format(
                instance=self.environment[
                    ohostedcons.VMEnv.VM_UUID
                ],
                hostname=self.environment[
                    ohostedcons.VMEnv.CLOUD_INIT_INSTANCE_HOSTNAME
                ],
            )
        f = open(f_meta_data, 'w')
        f.write(meta_data)
        f.close()

        f_cloud_init_iso = os.path.join(self._directory_name, 'seed.iso')
        rc, stdout, stderr = self.execute(
            (
                self.command.get('genisoimage'),
                '-output',
                f_cloud_init_iso,
                '-volid',
                'cidata',
                '-joliet',
                '-rock',
                '-input-charset',
                'utf-8',
                f_meta_data,
                f_user_data,
            )
        )
        if rc != 0:
            raise RuntimeError(_('Error generating cloud-init ISO image'))
        os.unlink(f_meta_data)
        os.unlink(f_user_data)
        self.environment[ohostedcons.VMEnv.CDROM] = f_cloud_init_iso
        os.chown(
            self._directory_name,
            pwd.getpwnam('qemu').pw_uid,
            pwd.getpwnam('qemu').pw_uid,
        )
        os.chmod(f_cloud_init_iso, 0o600)
        os.chown(
            f_cloud_init_iso,
            pwd.getpwnam('qemu').pw_uid,
            pwd.getpwnam('qemu').pw_uid,
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CLEANUP,
        condition=lambda self: self._enable,
    )
    def _cleanup(self):
        if self._directory_name is not None:
            shutil.rmtree(self._directory_name)
        self.environment[ohostedcons.VMEnv.CDROM] = None


# vim: expandtab tabstop=4 shiftwidth=4
