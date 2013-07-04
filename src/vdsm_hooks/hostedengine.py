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

    def main(self):
        if self.enabled:
            self.read_config()
            if self.is_hosted_engine_vm():
                self.set_destroy_on_events()
            self.save()


if __name__ == "__main__":
    HostedEngineHook().main()


# vim: expandtab tabstop=4 shiftwidth=4
