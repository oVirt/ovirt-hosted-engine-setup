#!/bin/bash -xe
[[ -d exported-artifacts ]] \
|| mkdir -p exported-artifacts

[[ -d tmp.repos ]] \
|| mkdir -p tmp.repos

SUFFIX=".$(date -u +%Y%m%d%H%M%S).git$(git rev-parse --short HEAD)"

# mock runner is not setting up the system correctly
# https://issues.redhat.com/browse/CPDEVOPS-242
if [[ "$(rpm --eval "%dist")" == ".el8" ]]; then
	readarray -t pkgs < automation/build-artifacts-manual.packages.el8stream
else
	readarray -t pkgs < automation/build-artifacts-manual.packages
fi

dnf install -y "${pkgs[@]}"

autopoint
autoreconf -ivf
./configure --disable-ansible-syntax-check
yum-builddep ovirt-hosted-engine-setup.spec
# Run rpmbuild, assuming the tarball is in the project's directory
rpmbuild \
    -D "_topdir $PWD/tmp.repos" \
    -D "release_suffix ${SUFFIX}" \
    -ta ovirt-hosted-engine-setup-*.tar.gz

mv *.tar.gz exported-artifacts
find \
    "$PWD/tmp.repos" \
    -iname \*.rpm \
    -exec mv {} exported-artifacts/ \;
