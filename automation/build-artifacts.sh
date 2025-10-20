#!/bin/bash -xe
[[ -d exported-artifacts ]] \
|| mkdir -p exported-artifacts

[[ -d tmp.repos ]] \
|| mkdir -p tmp.repos

SUFFIX=".$(date -u +%Y%m%d%H%M%S).git$(git rev-parse --short HEAD)"

autopoint
autoreconf -ivf
./configure --disable-ansible-syntax-check
make dist

dnf builddep -y ovirt-hosted-engine-setup.spec

rpmbuild \
    -D "_topdir $PWD/tmp.repos" \
    -D "release_suffix ${SUFFIX}" \
    -ta ovirt-hosted-engine-setup-*.tar.gz

mv ./*.tar.gz exported-artifacts
find \
    "$PWD/tmp.repos" \
    -iname \*.rpm \
    -exec mv {} exported-artifacts/ \;
