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

include $(top_srcdir)/build/ansible.inc

MAINTAINERCLEANFILES = \
	$(srcdir)/Makefile.in \
	$(NULL)

ansibledir=$(ovirthostedengineansibledir)
dist_ansible_DATA = \
	auth_revoke.yml \
	auth_sso.yml \
	bootstrap_local_vm.yml \
	clean_localvm_dir.yml \
	create_storage_domain.yml \
	create_target_vm.yml \
	fc_getdevices.yml \
	final_clean.yml \
	get_network_interfaces.yml \
	initial_clean.yml \
	iscsi_discover.yml \
	iscsi_getdevices.yml \
	$(NULL)

nodist_ansible_DATA = \
	install_appliance.yml \
	$(NULL)

SUBDIRS = \
	callback_plugins \
	hooks \
	library \
	module_utils \
	templates \
	$(NULL)

CLEANFILES = \
	install_appliance.yml \
	$(NULL)

EXTRA_DIST = \
	install_appliance.yml.in \
	$(NULL)

install_appliance.yml: install_appliance.yml.in
	$(SED) \
	-e 's|@APPLIANCE_RPM_PREFIX[@]|$(APPLIANCE_RPM_PREFIX)|g' \
	-e 's|@APPLIANCE40_RPM_PREFIX[@]|$(APPLIANCE40_RPM_PREFIX)|g' \
	< $< > $@

all-local: \
	ansible-syntax-check \
	$(NULL)
