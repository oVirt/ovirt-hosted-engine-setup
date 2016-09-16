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


import gettext
import os
import re
import tempfile

from otopi import base
from otopi import util


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


class InsufficientSpaceError(Exception):
    """Raised when check_available_space fails"""


@util.export
class DomainChecker(base.Base):
    """
    Domains utility.
    """

    _RE_VALID_PATH = re.compile(
        flags=re.VERBOSE,
        pattern=r"""
            ^
            /
            [\w_\-\s]+
            (
                /
                [\w_\-\s]+
            )*
            /?
            $
        """
    )

    def __init__(self):
        super(DomainChecker, self).__init__()

    def get_base_path(self, path):
        """
        Iterate up in the tree structure until we get an existing path
        """
        if os.path.exists(path.rstrip(os.path.sep)):
            return path
        else:
            return self.get_base_path(
                os.path.dirname(path)
            )

    def check_valid_path(self, path):
        """
        Check if the specified path has to be a valid path
        """
        self.logger.debug("validate '%s' as a valid mount point", path)
        if self._RE_VALID_PATH.match(path) is None:
            raise ValueError(
                _('{path} is not a valid path').format(path=path)
            )

    def check_base_writable(self, path):
        """
        Ensure that the path is writable
        """
        try:
            base_path = self.get_base_path(path)
            self.logger.debug(
                'Attempting to write temp file to {path}'.format(
                    path=base_path
                )
            )
            tempfile.TemporaryFile(dir=os.path.dirname(base_path)).close()
        except EnvironmentError:
            self.logger.debug('exception', exc_info=True)
            raise RuntimeError(
                _('Error: mount point {path} is not writable').format(
                    path=path
                )
            )

    def check_available_space(self, path, minimum):
        """
        Ensure it is large enough for containing an image
        """
        base_path = self.get_base_path(path)
        self.logger.debug(
            'Checking available space on {path}'.format(path=base_path)
        )
        stat = os.statvfs(base_path)
        available_space_mb = (stat.f_bsize * stat.f_bavail) // pow(2, 20)
        self.logger.debug(
            'Available space on {path} is {space}Mb'.format(
                path=base_path,
                space=available_space_mb
            )
        )
        if available_space_mb < minimum:
            raise InsufficientSpaceError(
                _(
                    'Error: mount point {path} contains only {available}Mb of '
                    'available space while a minimum of {minimum}Mb is '
                    'required'
                ).format(
                    path=base_path,
                    available=available_space_mb,
                    minimum=minimum
                )
            )


# vim: expandtab tabstop=4 shiftwidth=4
