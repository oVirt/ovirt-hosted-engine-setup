#!/bin/bash -ex

autoreconf -ivf
./configure
make test
make distcheck

./automation/build-artifacts.sh

export PREFIX=$(mktemp -d /tmp/he-prefix.XXXXXX)
make install prefix="${PREFIX}"

mkdir -p exported-artifacts/tests

export HE_ANSIBLE_LOG_PATH=exported-artifacts/tests/filter-test-$(date -u +%Y%m%d%H%M%S).log
export ANSIBLE_STDOUT_CALLBACK=2_ovirt_logger
export ANSIBLE_CALLBACK_PLUGINS=src/ansible
export PYTHONPATH="${PREFIX}/lib/python2.7/site-packages"

ANSIBLE_LOG=exported-artifacts/tests/filter-test-ansible-output-$(date -u +%Y%m%d%H%M%S).log

# TODO remove this test once we build otopi for python3
if python -c 'from otopi import util' > /dev/null 2>&1; then
	ansible-playbook --inventory=localhost, -vvvvvv tests/ansible/playbooks/test_filtering.yml > "${ANSIBLE_LOG}" 2>&1
	if grep 'secret_data' $HE_ANSIBLE_LOG_PATH; then
		echo Found non-filtered secrets in the log ^^^
		exit 1
	fi
fi
