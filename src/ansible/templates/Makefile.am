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

ansibletemplatesdir=$(ovirthostedengineansibledir)/templates
dist_ansibletemplates_DATA = \
	70-hosted-engine-setup.conf.j2 \
	broker.conf.j2 \
	fhanswers.conf.j2 \
	heanswers.conf.j2 \
	ifcfg-eth0-dhcp.j2 \
	ifcfg-eth0-static.j2 \
	ifcfg-eth0-static-ipv6.j2 \
	hosted-engine.conf.j2 \
	meta-data.j2 \
	user-data.j2 \
	network-config-dhcp6.j2 \
	version.j2 \
	vm.conf.j2 \
	$(NULL)
