#!/bin/bash -e
autoreconf -ivf
./configure
make test
make distcheck

./automation/build-artifacts.sh
