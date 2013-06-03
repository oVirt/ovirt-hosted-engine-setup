dnl
dnl otopi -- plugable installer
dnl Copyright (C) 2012-2013 Red Hat, Inc.
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
dnl rhel, fedora does not support ln -r
dnl
AC_DEFUN([AX_LN_SR], [
	AC_MSG_CHECKING([if 'ln -sr' supported])
	ln -sr test conftest 2> /dev/null
	result=$?
	rm -f conftest
	if test "${result}" = 0; then
		AC_MSG_RESULT([yes])
		LN_SR="ln -sr"
		HAVE_LN_SR="1"
	else
		AC_MSG_RESULT([no])
		LN_SR="${ac_abs_confdir}/ln-sr"
		HAVE_LN_SR="0"
		cat > "${ac_abs_confdir}/ln-sr" << __EOF__
#!/bin/sh
src="\[$]1"
dst="\[$]2"
relative="\$(perl -MFile::Spec -e 'print File::Spec->abs2rel("'\${src}'","'\$(dirname "\${dst}")'")' 2> /dev/null)"
if test "\$?" = 0; then
	exec ln -s "\${relative}" "\${dst}"
else
	echo "WARNING: Cannot create relative path"
	exec ln -s "\$(echo "\${src}" | sed "s#^\${DESTDIR}##")" "\${dst}"
fi
__EOF__
		chmod a+x "${ac_abs_confdir}/ln-sr"
	fi
	AC_SUBST([LN_SR])
	AC_SUBST([HAVE_LN_SR])
])
