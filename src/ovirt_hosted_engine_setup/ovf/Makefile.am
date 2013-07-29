MAINTAINERCLEANFILES = \
	$(srcdir)/Makefile.in \
	ovfenvelope.py \
	$(NULL)

#
# Downloaded from
# schemas.dmtf.org/ovf/envelope/1/dsp8023_1.1.0.xsd
# schemas.dmtf.org/ovf/environment/1/dsp8027_1.1.0.xsd
# schemas.dmtf.org/wbem/wscim/1/common.xsdi
# schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData.xsd
# schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData.xsd
#

EXTRA_DIST = \
	CIM_ResourceAllocationSettingData.xsd \
	CIM_VirtualSystemSettingData.xsd \
	common.xsd \
	dsp8023_1.1.0.xsd \
	dsp8027_1.1.0.xsd \
	$(NULL)

ovfdir=$(ovirthostedenginelibdir)/ovf
dist_ovf_PYTHON = \
	__init__.py \
	ovfenvelope.py \
	$(NULL)

# www.rexx.com/~dkuhlman/generateDS.html
ovfenvelope.py: dsp8023_1.1.0.xsd
	generateDS.py -f -o $@ --no-dates $<
	$(SED) -i "s:#!/usr/bin/env python::" $@

all-local: \
	ovfenvelope.py \
	$(NULL)

# Skipping intentionally code checks in this directory since code is auto generated

