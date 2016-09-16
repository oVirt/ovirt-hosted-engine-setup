#!/usr/bin/python

import os

import hooking

from ovirt_hosted_engine_setup import constants as ohostedcons


class HostedEngineHook(object):

    def __init__(self):
        super(HostedEngineHook, self).__init__()
        self.config = {}
        self.domxml = hooking.read_domxml()
        self.enabled = os.path.exists(
            ohostedcons.FileLocations.ENGINE_VM_CONF
        )

    def is_hosted_engine_vm(self):
        vm_uuid_element = self.domxml.getElementsByTagName('uuid')[0]
        vm_uuid = vm_uuid_element.childNodes[0].nodeValue
        return self.config.get('vmId', '') == vm_uuid

    def read_config(self):
        with open(ohostedcons.FileLocations.ENGINE_VM_CONF, 'r') as f:
            content = f.read().splitlines()
        for line in content:
            if '=' in line:
                key, value = line.split('=')
                self.config[key] = value

    def save(self):
        hooking.write_domxml(self.domxml)

    def set_destroy_on_events(self):
        domain = self.domxml.getElementsByTagName('domain')[0]
        for event in (
            'on_poweroff',
            'on_reboot',
            'on_crash',
        ):
            event_element = self.domxml.createElement(event)
            event_element.appendChild(self.domxml.createTextNode('destroy'))
            domain.appendChild(event_element)

    def appendAgentDevice(self, path, name):
        """
          <channel type='unix'>
             <target type='virtio' name=name/>
             <source mode='bind' path=path+vm_uuid+'.'+name/>
          </channel>
        """
        vm_uuid_element = self.domxml.getElementsByTagName('uuid')[0]
        vm_uuid = vm_uuid_element.childNodes[0].nodeValue
        devices = self.domxml.getElementsByTagName('devices')[0]

        channel = self.domxml.createElement('channel')
        channel.setAttribute('type', 'unix')

        target = self.domxml.createElement('target')
        target.setAttribute('type', 'virtio')
        target.setAttribute('name', name)

        source = self.domxml.createElement('source')
        source.setAttribute('mode', 'bind')
        source.setAttribute('path', path+vm_uuid+'.'+name)

        channel.appendChild(target)
        channel.appendChild(source)
        devices.appendChild(channel)

    def main(self):
        if self.enabled:
            self.read_config()
            if self.is_hosted_engine_vm():
                self.set_destroy_on_events()
                # TODO: append only on first boot
                self.appendAgentDevice(
                    ohostedcons.Const.OVIRT_HE_CHANNEL_PATH,
                    ohostedcons.Const.OVIRT_HE_CHANNEL_NAME,
                )
            self.save()


if __name__ == "__main__":
    HostedEngineHook().main()


# vim: expandtab tabstop=4 shiftwidth=4
