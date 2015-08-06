#!/bin/bash -e
rm -rf exported-artifacts
mkdir exported-artifacts
autoreconf -ivf
./configure
make dist
mv *.tar.gz exported-artifacts
yum-builddep ovirt-hosted-engine-setup.spec
rpmbuild \
    -D "_srcrpmdir $PWD/exported-artifacts"  \
    -D "_rpmdir $PWD/exported-artifacts"  \
    -ta exported-artifacts/*.gz
