#!/bin/bash -e

autopoint
autoreconf -ivf
./configure
# make distcheck skipped due to bug afflicting automake.
# fc29: https://bugzilla.redhat.com/1716384
# fc30: https://bugzilla.redhat.com/1757854
# el8:  https://bugzilla.redhat.com/1759942
# make distcheck

./automation/build-artifacts.sh

