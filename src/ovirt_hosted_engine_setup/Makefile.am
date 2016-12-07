#
# ovirt-hosted-engine-setup -- ovirt with a manager in a VM
# Copyright (C) 2012-2013 Red Hat, Inc.
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

SUBDIRS = \
	ovf \
	$(NULL)

MAINTAINERCLEANFILES = \
	$(srcdir)/Makefile.in \
	$(NULL)

CLEANFILES = \
	config.py \
	$(NULL)

EXTRA_DIST = \
	config.py.in \
	$(NULL)

dist_ovirthostedenginelib_PYTHON = \
	__init__.py \
	check_liveliness.py \
	connect_storage_server.py \
	constants.py \
	domains.py \
	engineapi.py \
	util.py \
	reinitialize_lockspace.py \
	set_maintenance.py \
	tasks.py \
	vm_status.py \
	mixins.py \
	appliance_esetup.py \
	vds_info.py \
	ohttpshandler.py \
	pkissh.py \
	$(NULL)

nodist_ovirthostedenginelib_PYTHON = \
	config.py \
	$(NULL)

config.py: config.py.in
	$(SED) \
	-e 's|@sysconfdir[@]|$(sysconfdir)|g' \
	-e 's|@datadir[@]|$(datadir)|g' \
	-e 's|@docdir[@]|$(docdir)|g' \
	-e 's|@prefix[@]|$(prefix)|g' \
	-e 's|@localstatedir[@]|$(localstatedir)|g' \
	-e 's|@APPLIANCE_RPM_PREFIX[@]|$(APPLIANCE_RPM_PREFIX)|g' \
	-e 's|@PACKAGE_NAME[@]|$(PACKAGE_NAME)|g' \
	-e 's|@PACKAGE_VERSION[@]|$(PACKAGE_VERSION)|g' < $< > $@

clean-local: \
	python-clean \
	$(NULL)

all-local: \
	$(DISTFILES) \
	python-syntax-check \
	$(NULL)
