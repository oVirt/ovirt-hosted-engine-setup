#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2014-2016 Red Hat, Inc.
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


from vdsm.network.netinfo.cache import CachingNetInfo


def capabilities(conn):
    """Returns a dictionary with the host capabilities"""
    result = conn.getVdsCapabilities()
    code, message = result['status']['code'], result['status']['message']
    if code != 0 or 'software_version' not in result:
        raise RuntimeError(
            'Failed to get vds capabilities. Error code: '
            '"%s" message: "%s"' % (code, message)
        )
    return result


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
    """
    Returns a dictionary that describes the network of the device.
    :param  caps: the output of vds_info.capabilities
    :param  device: the name of the network device
    :return (configuration, status): configuration is the whole dict to be
            passed to setupNetwork to configure the bridge as needed.
            Status is the current network status (for instance it includes
            the IP address also if the interfaces got its address by DHCP)
    """
    info = CachingNetInfo(caps)
    configuration = {}
    status = {}
    if device in info.vlans:
        port_info = info.vlans[device]
        configuration['vlan'] = port_info['vlanid']
        iface = port_info['iface']
        if iface in info.bondings:
            configuration['bonding'] = iface
        else:
            configuration['nic'] = iface
    elif device in info.bondings:
        configuration['bonding'] = device
        port_info = info.bondings[device]
    elif device in info.nics:
        configuration['nic'] = device
        port_info = info.nics[device]
    else:
        raise RuntimeError(
            'The selected device %s is not a supported bridge '
            'port' % device
        )

    if 'BOOTPROTO' in port_info['cfg']:
        configuration['bootproto'] = port_info['cfg']['BOOTPROTO']
    if configuration.get('bootproto') == 'dhcp':
        configuration['blockingdhcp'] = True
    else:
        configuration['ipaddr'] = port_info['addr']
        configuration['netmask'] = port_info['netmask']
        gateway = port_info.get('gateway')
        if gateway is not None:
            configuration['gateway'] = gateway
        elif 'GATEWAY' in port_info['cfg']:
            configuration['gateway'] = port_info['cfg']['GATEWAY']
    configuration['defaultRoute'] = _evaluateDefaultRoute(
        configuration,
        port_info['cfg']
    )
    if 'addr' in port_info:
        status['ipaddr'] = port_info['addr']
    if 'netmask' in port_info:
        status['netmask'] = port_info['netmask']
    if 'gateway' in port_info:
        status['gateway'] = port_info['gateway']
    return configuration, status


# vim: expandtab tabstop=4 shiftwidth=4
