#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2017 Red Hat, Inc.
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


"""vm.conf Utils"""


import base64
import re

from ovirt_hosted_engine_setup.ovf import ovfenvelope


def _splitDriveSpecItems(item):
    """
    Code copied from vdsm/client/vdsClient.py for compatibility reasons
    BC is BC.
    """
    key, value = item.split(":", 1)
    if key in ("domain", "pool", "image", "volume"):
        key = "%sID" % key
    return key, value


def _parseNestedSpec(spec):
    """
    Code copied from vdsm/client/vdsClient.py for compatibility reasons
    """
    d = dict()

    if spec[0] != '{':
        raise Exception("_parseNestedSpec called with "
                        "non nested spec: '%s'" % spec)

    spec = spec[1:]
    while True:
        if not spec or '}' not in spec:
            raise Exception("nested spec not terminated "
                            "with '}' in '%s'" % spec)
        if spec[0] == '}':
            return d, spec[1:]

        # Split into first name + the rest
        if ':' not in spec:
            raise Exception("missing name value separator "
                            "':' in '%s'" % spec)
        name, spec = spec.split(":", 1)

        # Determine the value
        if spec[0] == '{':
            val, spec = _parseNestedSpec(spec)
            d[name] = val
        else:
            # The value ends either with a ',' meaning it is followed by
            # another name:value pair, or with a '}' ending the spec
            i = 0
            while spec[i] != ',' and spec[i] != '}':
                i = i + 1
            val = spec[:i]
            spec = spec[i:]
            d[name] = val

        # If there is a comma behind the value remove it before continuing
        if spec and spec[0] == ',':
            spec = spec[1:]


def _parseDriveSpec(spec):
    """
    Code copied from vdsm/client/vdsClient.py for compatibility reasons
    '{' or ',' means dict. (!)
    """
    if spec[0] == '{':
        val, spec = _parseNestedSpec(spec)
        if spec:
            raise Exception("Trailing garbage after spec: '%s'" % spec)
        return val
    if ',' in spec:
        return dict(_splitDriveSpecItems(item)
                    for item in spec.split(',') if item)
    return spec


def parseVmConfFile(filename):
    """
    Code copied from vdsm/client/vdsClient.py for compatibility reasons
    """
    params = {}
    drives = []
    devices = []
    cpuPinning = {}
    numaTune = {}
    guestNumaNodes = []
    confLines = []
    confFile = open(filename)
    for line in confFile.readlines():
        line = re.sub(r"\s+", '', line)
        line = re.sub(r"\#.*", '', line)
        if line:
            confLines.append(line)
    for line in confLines:
        if '=' in line:
            param, value = line.split("=", 1)
            if param == 'devices':
                devices.append(_parseDriveSpec(value))
            elif param == 'drive':
                drives.append(_parseDriveSpec(value))
            elif param == 'cpuPinning':
                cpuPinning, rStr = _parseNestedSpec(value)
            elif param == 'numaTune':
                numaTune, rStr = _parseNestedSpec(value)
            elif param == 'guestNumaNodes':
                guestNumaNodes.append(_parseDriveSpec(value))
            elif param.startswith('custom_'):
                if 'custom' not in params:
                    params['custom'] = {}
                params['custom'][param[7:]] = value
            else:
                if param in ('cdrom', 'floppy'):
                    value = _parseDriveSpec(value)
                params[param] = value
        else:
            params[line.strip()] = ''
    if cpuPinning:
        params['cpuPinning'] = cpuPinning
    if numaTune:
        params['numaTune'] = numaTune
    if guestNumaNodes:
        params['guestNumaNodes'] = guestNumaNodes
    if drives:
        params['drives'] = drives
    if devices:
        params['devices'] = devices
    # Backward compatibility for vdsClient users
    if 'vt' in params:
        params['kvmEnable'] = params['vt']

    if 'imageFile' in params:
        params['hda'] = params['imageFile']

    drives = ['hdd', 'hdc', 'hdb']
    if 'moreImages' in params:
        for image in params['moreImages'].split(','):
            params[drives.pop()] = image

    # Decode xml string
    if 'xmlBase64' in params:
        xml = base64.standard_b64decode(params['xmlBase64']).decode()
        del params['xmlBase64']
        params['xml'] = xml

        if params.get('launchPaused', False):
            engine_xml_tree = ovfenvelope.etree_.fromstring(
                xml.encode('utf-8')
            )
            metadata = engine_xml_tree.xpath("//metadata")[0]
            ns = metadata.nsmap['ovirt-vm']
            vm = metadata.find('{%s}vm' % ns)
            # workaround an engine bug: the engine sets launchPaused
            # without its namespace
            lp_nons = vm.find('launchPaused')
            if lp_nons is not None:
                vm.remove(lp_nons)
            lp = vm.find('{%s}launchPaused' % ns)
            if lp is not None:
                lp.text = 'true'
            else:
                lp = ovfenvelope.etree_.Element('{%s}launchPaused' % ns)
                lp.text = 'true'
                vm.append(lp)
            params['xml'] = ovfenvelope.etree_.tostring(
                engine_xml_tree,
                xml_declaration=True,
                encoding='UTF-8',
            ).decode()

    return params


# vim: expandtab tabstop=4 shiftwidth=4
