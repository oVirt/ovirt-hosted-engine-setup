#!/bin/bash -ex

autopoint
autoreconf -ivf
if [[ "$(rpm --eval "%dist")" == ".el8" ]]; then
./configure
else
# On CentOS Stream 9 ansible will be handled differently due to ansible 2.11
./configure --disable-ansible-syntax-check
fi
make test

# make distcheck skipped due to bug afflicting automake.
# fc29: https://bugzilla.redhat.com/1716384
# fc30: https://bugzilla.redhat.com/1757854
# el8:  https://bugzilla.redhat.com/1759942

./automation/build-artifacts.sh
PREFIX=$(mktemp -d /tmp/he-prefix.XXXXXX)
export PREFIX
make install prefix="${PREFIX}"

mkdir -p exported-artifacts/tests

HE_ANSIBLE_LOG_PATH=exported-artifacts/tests/filter-test-$(date -u +%Y%m%d%H%M%S).log
export HE_ANSIBLE_LOG_PATH
export ANSIBLE_STDOUT_CALLBACK=2_ovirt_logger
export ANSIBLE_CALLBACK_PLUGINS=src/ansible

ANSIBLE_LOG=exported-artifacts/tests/filter-test-ansible-output-$(date -u +%Y%m%d%H%M%S).log

dnf install -y ansible
ansible-playbook --inventory=localhost, -vvvvvv tests/ansible/playbooks/test_filtering.yml > "${ANSIBLE_LOG}" 2>&1
if grep 'secret_data' "$HE_ANSIBLE_LOG_PATH"; then
	echo Found non-filtered secrets in the log ^^^
	exit 1
fi
