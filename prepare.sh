#!/bin/sh
#FIXME remove this file after packaging

mkdir -p /usr/share/ovirt-hosted-engine-setup/templates
mkdir -p /etc/ovirt-hosted-engine-setup
cp vm.conf.in /usr/share/ovirt-hosted-engine-setup/templates/vm.conf.in
cp hosted-engine.conf.in /usr/share/ovirt-hosted-engine-setup/templates/hosted-engine.conf.in
