#!/bin/bash -xe
[[ -d exported-artifacts ]] \
|| mkdir -p exported-artifacts

[[ -d tmp.repos ]] \
|| mkdir -p tmp.repos

# mock runner is not setting up the system correctly
# https://issues.redhat.com/browse/CPDEVOPS-242
if [[ "$(rpm --eval "%dist")" == ".el8" ]]; then
	readarray -t pkgs < automation/build-artifacts.packages.el8stream
else
	readarray -t pkgs < automation/build-artifacts.packages
fi
dnf install -y "${pkgs[@]}"

autopoint
autoreconf -ivf
./configure --disable-ansible-syntax-check
make dist

if [ -x /usr/bin/dnf ] ; then
    dnf builddep ovirt-hosted-engine-setup.spec
else
    yum-builddep ovirt-hosted-engine-setup.spec
fi

rpmbuild \
    -D "_topdir $PWD/tmp.repos" \
    -ta ovirt-hosted-engine-setup-*.tar.gz

mv ./*.tar.gz exported-artifacts
find \
    "$PWD/tmp.repos" \
    -iname \*.rpm \
    -exec mv {} exported-artifacts/ \;
