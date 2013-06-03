#!/bin/sh

#Allow to re-execute ovirt-hosted-engine-setup without errors.
#FIXME: remove entities created and not just disconnect them.
#TODO: Use for fixing relevant plugins for rolling back on errors during setup

spUUID=`vdsClient -s localhost getConnectedStoragePoolsList`
sdUUID=`vdsClient -s localhost getStorageDomainsList $spUUID`
vdsClient -s localhost spmStop $spUUID
vdsClient -s localhost disconnectStoragePool $spUUID 1 $sdUUID
brctl show |grep ovirtmgmt
res=$?
if [ $res == 0 ] ; then
    echo 'delete ovirtmgmt bridge? y/n'
    read ans
    if [ "$ans" == "y" ] ; then
        /usr/share/vdsm/delNetwork ovirtmgmt '' '' em1 && service network restart
    fi
fi
