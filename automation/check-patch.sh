#!/bin/bash -ex

# ensure ansible is installed or it will fail on ansible-lint on CentOS Stream 9
# note that on CentOS Stream 9 we have ansible-core-2.11 and on 8 we have ansible-2.9.
dnf install -y /usr/bin/ansible

# ensure packages are really updated.
dnf distrosync -y

autopoint
autoreconf -ivf
./configure
make test
# make distcheck skipped due to bug afflicting automake.
# fc29: https://bugzilla.redhat.com/1716384
# fc30: https://bugzilla.redhat.com/1757854
# el8:  https://bugzilla.redhat.com/1759942
# make distcheck

./automation/build-artifacts.sh

export PREFIX=$(mktemp -d /tmp/he-prefix.XXXXXX)
make install prefix="${PREFIX}"

mkdir -p exported-artifacts/tests

export HE_ANSIBLE_LOG_PATH=exported-artifacts/tests/filter-test-$(date -u +%Y%m%d%H%M%S).log
export ANSIBLE_STDOUT_CALLBACK=2_ovirt_logger
export ANSIBLE_CALLBACK_PLUGINS=src/ansible

ANSIBLE_LOG=exported-artifacts/tests/filter-test-ansible-output-$(date -u +%Y%m%d%H%M%S).log

ansible-playbook --inventory=localhost, -vvvvvv tests/ansible/playbooks/test_filtering.yml > "${ANSIBLE_LOG}" 2>&1
if grep 'secret_data' $HE_ANSIBLE_LOG_PATH; then
	echo Found non-filtered secrets in the log ^^^
	exit 1
fi
