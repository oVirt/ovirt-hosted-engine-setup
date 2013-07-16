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

MAINTAINERCLEANFILES = \
	$(srcdir)/Makefile.in \
	$(NULL)

EXTRA_DIST = \
	.source \
	hosted-engine.in \
	$(NULL)

sbin_SCRIPTS = \
	hosted-engine
	$(NULL)

scriptsdir = $(ovirthostedenginescriptsdir)
dist_scripts_DATA = \
	ovirt-hosted-engine-setup.env \
	$(NULL)

dist_scripts_SCRIPTS = \
	ovirt-hosted-engine-setup \
	$(NULL)

CLEANFILES = \
	hosted-engine \
	$(NULL)

hosted-engine: hosted-engine.in
	sed -e 's,[@]datadir[@],$(datadir),g' < $< > $@

install-data-local:
	$(MKDIR_P) $(DESTDIR)/$(sysconfdir)/ovirt-hosted-engine-setup.env.d
	$(MKDIR_P) $(DESTDIR)/$(sysconfdir)/ovirt-hosted-engine

install-exec-local: ovirt-hosted-engine-setup
	$(MKDIR_P) $(DESTDIR)/$(sbindir)
	$(LN_S) $(ovirthostedenginescriptsdir)/ovirt-hosted-engine-setup $(DESTDIR)/$(sbindir)/ovirt-hosted-engine-setup

uninstall-local:
	rm -f $(DESTDIR)/$(sbindir)/ovirt-hosted-engine-setup
