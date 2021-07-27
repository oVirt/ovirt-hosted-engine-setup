dnl
dnl ovirt-hosted-engine-setup -- ovirt with a manager in a VM
dnl Copyright (C) 2013-2018 Red Hat, Inc.
dnl
dnl This library is free software; you can redistribute it and/or
dnl modify it under the terms of the GNU Lesser General Public
dnl License as published by the Free Software Foundation; either
dnl version 2.1 of the License, or (at your option) any later version.
dnl
dnl This library is distributed in the hope that it will be useful,
dnl but WITHOUT ANY WARRANTY; without even the implied warranty of
dnl MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
dnl Lesser General Public License for more details.
dnl
dnl You should have received a copy of the GNU Lesser General Public
dnl License along with this library; if not, write to the Free Software
dnl Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
dnl
AC_PREREQ(2.60)

define([VERSION_MAJOR], [2])
define([VERSION_MINOR], [5])
define([VERSION_FIX], [3])
define([VERSION_NUMBER], VERSION_MAJOR[.]VERSION_MINOR[.]VERSION_FIX)
define([VERSION_RELEASE], [1])
define([VERSION_SUFFIX], [])

AC_INIT(
    [ovirt-hosted-engine-setup],
    [VERSION_NUMBER],
    [devel@ovirt.org],
    [],
    [http://www.ovirt.org]
)
PACKAGE_RPM_VERSION="VERSION_NUMBER"
PACKAGE_RPM_RELEASE="VERSION_RELEASE"
AC_SUBST([PACKAGE_RPM_VERSION])
AC_SUBST([PACKAGE_RPM_RELEASE])

AC_CONFIG_AUX_DIR([.])
AC_CONFIG_SRCDIR([src/ovirt_hosted_engine_setup/__init__.py])
AC_CONFIG_MACRO_DIR([m4])
AM_INIT_AUTOMAKE([1.9 tar-pax])

dnl Fallback definition for gettext.m4 older than 0.19.6.
m4_ifndef([AM_GNU_GETTEXT_REQUIRE_VERSION], [m4_define([AM_GNU_GETTEXT_REQUIRE_VERSION])], [])
dnl Prefer the latest infrastructure, given it is newer than 0.18.2.
AM_GNU_GETTEXT_REQUIRE_VERSION([0.18.2])

dnl This will be ignored if the installed autopoint supports
dnl AM_GNU_GETTEXT_REQUIRE_VERSION.
AM_GNU_GETTEXT_VERSION([0.18.2])
AM_PO_SUBDIRS

AC_ARG_ENABLE(
	[python-syntax-check],
	[AS_HELP_STRING([--disable-python-syntax-check], [disable python syntax check @<:@default=enabled@:>@])],
	,
	[enable_python_syntax_check="yes"]
)

AC_ARG_ENABLE(
	[ansible-syntax-check],
	[AS_HELP_STRING([--disable-ansible-syntax-check], [disable ansible syntax check @<:@default=enabled@:>@])],
	,
	[enable_ansible_syntax_check="yes"]
)

AC_PROG_INSTALL
AC_PROG_SED
AC_PROG_MAKE_SET
AC_PROG_MKDIR_P
AC_PROG_LN_S
AX_LN_SR

AC_ARG_VAR([PYFLAKES], [path to pyflakes utility])
AC_CHECK_PROGS([PYFLAKES], [pyflakes])
AC_ARG_VAR([PEP8], [path to pep8 utility])
AC_CHECK_PROGS([PEP8], [pep8])
AC_ARG_VAR([PYTEST], [path to py.test utility])
AC_CHECK_PROGS([PYTEST], [py.test py.test-3])
AC_ARG_VAR([ISORT], [path to isort utility])
AC_CHECK_PROGS([ISORT], [isort])
AC_ARG_VAR([RPMBUILD], [path to rpmbuild utility])
AC_CHECK_PROGS([RPMBUILD], [rpmbuild])
AC_ARG_VAR([ANSIBLE_LINT], [path to ansible-lint utility])
AC_CHECK_PROGS([ANSIBLE_LINT], [ansible-lint])
AM_PATH_PYTHON([2.6],, [AC_MSG_ERROR([Cannot find python])])

otopiplugindir="\$(datadir)/otopi/plugins"
ovirthostedengineplugindir="\$(pkgdatadir)/plugins"
ovirthostedenginelibrarydir="\$(pkgdatadir)/library"
ovirthostedenginetemplatedir="\$(pkgdatadir)/templates"
ovirthostedenginescriptsdir="\$(pkgdatadir)/scripts"
ovirthostedengineansibledir="\$(pkgdatadir)/ansible"
ovirthostedenginelibdir="\$(pythondir)/ovirt_hosted_engine_setup"
vdsmhooksdir="\$(libexecdir)/vdsm/hooks"
APPLIANCE_RPM_PREFIX="ovirt-engine"
APPLIANCE40_RPM_PREFIX="ovirt-engine"
AC_SUBST([otopiplugindir])
AC_SUBST([ovirthostedengineplugindir])
AC_SUBST([ovirthostedenginelibrarydir])
AC_SUBST([ovirthostedenginetemplatedir])
AC_SUBST([ovirthostedenginescriptsdir])
AC_SUBST([ovirthostedengineansibledir])
AC_SUBST([ovirthostedenginelibdir])
AC_SUBST([vdsmhooksdir])
AC_SUBST([APPLIANCE_RPM_PREFIX])
AC_SUBST([APPLIANCE40_RPM_PREFIX])
AM_CONDITIONAL([PYTHON_SYNTAX_CHECK], [test "${enable_python_syntax_check}" = "yes"])
AM_CONDITIONAL([ANSIBLE_SYNTAX_CHECK], [test "${enable_ansible_syntax_check}" = "yes"])

AC_CONFIG_FILES([
	Makefile
	ovirt-hosted-engine-setup.spec
	build/Makefile
	man/Makefile
	po/Makefile.in
	src/Makefile
	src/bin/Makefile
	src/ovirt_hosted_engine_setup/Makefile
	src/ovirt_hosted_engine_setup/ovf/Makefile
	src/plugins/Makefile
	src/plugins/gr-he-common/Makefile
	src/plugins/gr-he-common/core/Makefile
	src/plugins/gr-he-common/engine/Makefile
	src/plugins/gr-he-common/network/Makefile
	src/plugins/gr-he-common/sanlock/Makefile
	src/plugins/gr-he-common/vm/Makefile
	src/plugins/gr-he-ansiblesetup/Makefile
	src/plugins/gr-he-ansiblesetup/core/Makefile
	src/vdsm_hooks/Makefile
	src/vdsm_hooks/hostedengine.py
	src/ansible/Makefile
	src/ansible/callback_plugins/Makefile
	templates/Makefile
	tests/Makefile
])
AC_CONFIG_FILES([po/Makefile], [AM_POSTPROCESS_PO_MAKEFILE])
AC_OUTPUT
