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


"""Gather output frm engine-setup on the oVirt appliance"""


import gettext
import select
import socket
import time


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


DEFAULT_READLINE_TIMEOUT = 5
MAX_LINE_LENGTH = 1024


class ApplianceEngineSetup(object):

    def _appliance_connect(self, socket_file, retries=5, wait=5):
        """
        Connect to engine-setup running on the appliance.
        Upon failure, reconnection attempts will be made approximately once
        every n seconds until the specified number of retries have been made.
        An exception will be raised if a connection cannot be established.
        """
        if self._appliance_is_connected():
            return
        self.logger.debug(_('Connecting to engine-setup on the appliance'))

        try:
            self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        except socket.error as e:
            self.logger.error(
                'Failed to connect to the appliance: {ex}'.format(ex=e)
            )
            if self._socket:
                self._socket.close()
            self._socket = None
            raise

        for attempt in range(retries):
            try:
                self._socket.connect(socket_file)
                self._socket.setblocking(0)
                break
            except socket.error as e:
                self.logger.debug(
                    'Failed to connect to the appliance: {ex}'.format(ex=e)
                )
                self.logger.debug(
                    'Retrying appliance connection in {wait} seconds'.format(
                        wait=wait
                    )
                )
                time.sleep(wait)
        else:
            error_msg = (
                _(
                    'Failed to connect to appliance, the number of '
                    'errors has exceeded the limit ({retries})'
                ).format(retries=retries)
            )
            self.logger.error(error_msg)
            self._socket.close()
            self._socket = None
            raise RuntimeError(error_msg)

        self.logger.debug('Successfully connected to the appliance')

    def _appliance_readline_nb(self, timeout=DEFAULT_READLINE_TIMEOUT):
        """
        Read a line from the (already-connected) appliance in a not blocking
        way. The response is non-newline-terminated string plus a boolean
        to indicate that a timeout has occurred.
        Max MAX_LINE_LENGTH chars per line.
        """
        line = ''
        len = 0
        if not self._appliance_is_connected():
            raise RuntimeError('The appliance is not connected anymore')
        while True:
            readable, writable, exceptional = select.select(
                [self._socket],
                [],
                [self._socket],
                timeout
            )
            if exceptional:
                self._appliance_disconnect()
                raise RuntimeError('Error reading from the appliance')
            elif readable:
                r = self._socket.recv(1)
                if r == '\n':
                    return line, False
                line += r
                len += 1
                if len >= MAX_LINE_LENGTH:
                    return line, False
            else:
                return line, True

    def _appliance_is_connected(self):
        return self._socket is not None

    def _appliance_disconnect(self):
        self.logger.debug("Closing connection to appliance")
        try:
            if self._socket:
                self._socket.close()
        except socket.error:
            self.logger.debug("Socket error closing connection")
        finally:
            self._socket = None


# vim: expandtab tabstop=4 shiftwidth=4
