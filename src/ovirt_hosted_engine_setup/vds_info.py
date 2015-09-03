#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2014 Red Hat, Inc.
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
vds utilities
"""


from vdsm import netinfo


def capabilities(conn):
    """Returns a dictionary with the host capabilities"""
    result = conn.getVdsCapabilities()
    code, message = result['status']['code'], result['status']['message']
    if code != 0 or 'info' not in result:
        raise RuntimeError(
            'Failed to get vds capabilities. Error code: '
            '"%s" message: "%s"' % (code, message)
        )
    return result['info']


def _evaluateDefaultRoute(attrs, cfg):
    defroute = None
    cfgdefroute = cfg.get('DEFROUTE')
    if cfgdefroute:
        if cfgdefroute.lower().strip('" ') == 'yes':
            defroute = True
        elif cfgdefroute.lower().strip('" ') == 'no':
            defroute = False

    if (
        defroute or
        (attrs.get('bootproto') == 'dhcp' and defroute is not False) or
        attrs.get('gateway')
    ):
        return True
    return False


def network(caps, device):
    """Returns a dictionary that describes the network of the device"""
    info = netinfo.NetInfo(caps)
    attrs = {}
    if device in info.vlans:
        port_info = info.vlans[device]
        attrs['vlan'] = port_info['vlanid']
        iface = port_info['iface']
        if iface in info.bondings:
            attrs['bonding'] = iface
        else:
            attrs['nic'] = iface
    elif device in info.bondings:
        attrs['bonding'] = device
        port_info = info.bondings[device]
    elif device in info.nics:
        attrs['nic'] = device
        port_info = info.nics[device]
    else:
        raise RuntimeError(
            'The selected device %s is not a supported bridge '
            'port' % device
        )

    if 'BOOTPROTO' in port_info['cfg']:
        attrs['bootproto'] = port_info['cfg']['BOOTPROTO']
    if attrs.get('bootproto') == 'dhcp':
        attrs['blockingdhcp'] = True
    else:
        attrs['ipaddr'] = port_info['addr']
        attrs['netmask'] = port_info['netmask']
        gateway = port_info.get('gateway')
        if gateway is not None:
            attrs['gateway'] = gateway
        elif 'GATEWAY' in port_info['cfg']:
            attrs['gateway'] = port_info['cfg']['GATEWAY']
    attrs['defaultRoute'] = _evaluateDefaultRoute(attrs, port_info['cfg'])
    return attrs


# vim: expandtab tabstop=4 shiftwidth=4
