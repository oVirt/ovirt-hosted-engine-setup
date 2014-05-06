dnl
dnl ovirt-hosted-engine-setup -- ovirt with a manager in a VM
dnl Copyright (C) 2013-2014 Red Hat, Inc.
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

define([VERSION_MAJOR], [1])
define([VERSION_MINOR], [1])
define([VERSION_FIX], [3])
define([VERSION_NUMBER], VERSION_MAJOR[.]VERSION_MINOR[.]VERSION_FIX)
define([VERSION_SUFFIX], [])

AC_INIT([ovirt-hosted-engine-setup], VERSION_NUMBER[]VERSION_SUFFIX)
PACKAGE_RPM_VERSION="VERSION_NUMBER"
PACKAGE_RPM_RELEASE="1"
PACKAGE_MAVEN_VERSION="VERSION_MAJOR.VERSION_MINOR.0$(echo VERSION_SUFFIX | sed 's/^_/-/')"
AC_SUBST([PACKAGE_RPM_VERSION])
AC_SUBST([PACKAGE_RPM_RELEASE])
AC_SUBST([PACKAGE_MAVEN_VERSION])

AC_CONFIG_AUX_DIR([.])
AC_CONFIG_SRCDIR([src/ovirt_hosted_engine_setup/__init__.py])
AC_CONFIG_MACRO_DIR([m4])
AC_USE_SYSTEM_EXTENSIONS
AM_INIT_AUTOMAKE([1.9 tar-pax])
AM_GNU_GETTEXT_VERSION([0.17])
AM_GNU_GETTEXT([external])

AC_ARG_ENABLE(
	[python-syntax-check],
	[AS_HELP_STRING([--disable-python-syntax-check], [disable python syntax check @<:@default=enabled@:>@])],
	,
	[enable_python_syntax_check="yes"]
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
AC_ARG_VAR([RPMBUILD], [path to rpmbuild utility])
AC_CHECK_PROGS([RPMBUILD], [rpmbuild])
AC_ARG_VAR([OTOPI_BUNDLE], [path to otopi-bundle utility])
AC_PATH_PROGS([OTOPI_BUNDLE], [otopi-bundle],, [/usr/share/otopi])

AM_PATH_PYTHON([2.6],, [AC_MSG_ERROR([Cannot find python])])
AX_PYTHON_MODULE([otopi], [fatal])

test -z "${OTOPI_BUNDLE}" && AC_MSG_ERROR([otopi-bundle required but missing])

otopiplugindir="\$(datadir)/otopi/plugins"
ovirthostedengineplugindir="\$(pkgdatadir)/plugins"
ovirthostedenginetemplatedir="\$(pkgdatadir)/templates"
ovirthostedenginescriptsdir="\$(pkgdatadir)/scripts"
ovirthostedenginelibdir="\$(pythondir)/ovirt_hosted_engine_setup"
vdsmhooksdir="\$(libexecdir)/vdsm/hooks"
AC_SUBST([otopiplugindir])
AC_SUBST([ovirthostedengineplugindir])
AC_SUBST([ovirthostedenginetemplatedir])
AC_SUBST([ovirthostedenginescriptsdir])
AC_SUBST([ovirthostedenginelibdir])
AC_SUBST([vdsmhooksdir])
AM_CONDITIONAL([PYTHON_SYNTAX_CHECK], [test "${enable_python_syntax_check}" = "yes"])

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
	src/plugins/ovirt-hosted-engine-setup/Makefile
	src/plugins/ovirt-hosted-engine-setup/core/Makefile
	src/plugins/ovirt-hosted-engine-setup/ha/Makefile
        src/plugins/ovirt-hosted-engine-setup/network/Makefile
	src/plugins/ovirt-hosted-engine-setup/pki/Makefile
	src/plugins/ovirt-hosted-engine-setup/sanlock/Makefile
	src/plugins/ovirt-hosted-engine-setup/storage/Makefile
	src/plugins/ovirt-hosted-engine-setup/system/Makefile
	src/plugins/ovirt-hosted-engine-setup/vm/Makefile
	src/plugins/ovirt-hosted-engine-setup/libvirt/Makefile
	src/plugins/ovirt-hosted-engine-setup/vdsmd/Makefile
	src/plugins/ovirt-hosted-engine-setup/engine/Makefile
	src/vdsm_hooks/Makefile
	templates/Makefile
	tests/Makefile
])
AC_OUTPUT
