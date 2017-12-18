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
	bootstrap_local_vm.yml \
	create_storage_domain.yml \
	create_target_vm.yml \
	iscsi_discover.yml \
	iscsi_getdevices.yml \
	fc_getdevices.yml \
	clean_environment.yml \
	get_network_interfaces.yml \
	$(NULL)

SUBDIRS = \
	callback_plugins \
	library \
	templates \
	$(NULL)
