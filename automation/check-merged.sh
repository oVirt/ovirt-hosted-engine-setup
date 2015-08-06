#!/bin/bash -e
autoreconf -ivf
./configure
make distcheck
