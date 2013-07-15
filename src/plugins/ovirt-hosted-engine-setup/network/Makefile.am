#
# ovirt-hosted-engine-setup -- ovirt with a manager in a VM
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

include $(top_srcdir)/build/python.inc

MAINTAINERCLEANFILES = \
	$(srcdir)/Makefile.in \
	$(NULL)

mydir=$(ovirthostedengineplugindir)/ovirt-hosted-engine-setup/network
dist_my_PYTHON = \
	__init__.py \
	bridge.py \
	firewall_manager.py \
	firewall.py \
	$(NULL)

clean-local: \
	python-clean \
	$(NULL)

all-local: \
	python-syntax-check \
	$(NULL)
