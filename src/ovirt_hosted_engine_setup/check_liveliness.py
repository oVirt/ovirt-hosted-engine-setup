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

"""Check for engine liveliness"""


import contextlib
import gettext
import re
import urllib2


from otopi import base
from otopi import util


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class LivelinessChecker(base.Base):

    DB_UP_RE = re.compile('.*DB Up.*')

    def __init__(self):
        super(LivelinessChecker, self).__init__()

    def isEngineUp(self, fqdn):
        self.logger.debug('Checking for Engine health status')
        health_url = 'http://{fqdn}/OvirtEngineWeb/HealthStatus'.format(
            fqdn=fqdn,
        )
        isUp = False
        try:
            with contextlib.closing(urllib2.urlopen(health_url)) as urlObj:
                content = urlObj.read()
                if content:
                    if self.DB_UP_RE.match(content) is not None:
                        isUp = True
                    self.logger.info(
                        _('Engine replied: {status}').format(
                            status=content,
                        )
                    )
        except urllib2.URLError:
            self.logger.error(_('Engine is still unreachable'))
        return isUp


if __name__ == "__main__":
    import sys

    from ovirt_hosted_engine_setup import constants as ohostedcons

    config = {}
    try:
        with open(
            ohostedcons.FileLocations.OVIRT_HOSTED_ENGINE_SETUP_CONF
        ) as f:
            content = f.read().splitlines()
            for line in content:
                if '=' in line:
                    key, value = line.split('=')
                    config[key] = value
    except IOError:
        sys.stderr.write(_('Error reading the configuration file\n'))
        sys.exit(2)
    if not 'fqdn' in config:
        sys.stderr.write(
            _(
                'Incomplete configuration, missing FQDN '
                'of the hosted engine VM\n'
            )
        )
        sys.exit(2)

    live_checker = LivelinessChecker()
    if not live_checker.isEngineUp(config['fqdn']):
        print _('Hosted Engine is not up!')
        sys.exit(1)
    print _('Hosted Engine is up!')

# vim: expandtab tabstop=4 shiftwidth=4
