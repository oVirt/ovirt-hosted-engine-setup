#!/bin/bash -e

# mock runner is not setting up the system correctly
# https://issues.redhat.com/browse/CPDEVOPS-242
if [[ "$(rpm --eval "%dist")" == ".el8" ]]; then
	readarray -t pkgs < automation/check-merged.packages.el8stream
else
	readarray -t pkgs < automation/check-merged.packages
fi
dnf install -y "${pkgs[@]}"

autopoint
autoreconf -ivf
./configure --disable-ansible-syntax-check
# make distcheck skipped due to bug afflicting automake.
# fc29: https://bugzilla.redhat.com/1716384
# fc30: https://bugzilla.redhat.com/1757854
# el8:  https://bugzilla.redhat.com/1759942
# make distcheck

./automation/build-artifacts.sh

