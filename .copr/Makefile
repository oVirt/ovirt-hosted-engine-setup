.PHONY: installdeps git_cfg_safe srpm

installdeps:
	dnf -y install git autoconf automake make gettext-devel gcc

git_cfg_safe:
	# Workaround for CVE-2022-24765 fix:
	#
	#	fatal: unsafe repository ('/path' is owned by someone else)
	#
	# Since copr build process first clones the repo, and then uses mock to run the build
	#
	git config --global --add safe.directory "$(shell pwd)"

srpm: installdeps git_cfg_safe
	$(eval SUFFIX=$(shell sh -c " echo '.$$(date -u +%Y%m%d%H%M%S).git$$(git rev-parse --short HEAD)'"))
	# changing the spec file as passing -D won't preserve the suffix when rebuilding in mock
	sed "s:%{?release_suffix}:${SUFFIX}:" -i *.spec.in
	mkdir -p tmp.repos/SOURCES
	autopoint
	autoreconf -ivf
	./configure
	make dist
	rpmbuild \
		-D "_topdir tmp.repos" \
		-ts ./*.tar.gz
	cp tmp.repos/SRPMS/*.src.rpm $(outdir)
