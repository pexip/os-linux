ifeq ($(filter i386 amd64 x32 arm64,$(DEB_HOST_ARCH)),)

# Build nothing
include $(top_rulesdir)/Makefile.inc

else

PROGS = \
	hv_kvp_daemon \
	hv_vss_daemon

installdir = /usr/sbin

SCRIPTS = \
	hv_get_dhcp_info.sh \
	hv_get_dns_info.sh

scriptsdir = /usr/libexec/hypervkvpd/

include $(top_rulesdir)/Makefile.inc

install-local-scripts: $(SCRIPTS_REAL)
	@for p in $^; do \
	  echo " install -m755 '$$p' '$(DESTDIR)/$(scriptsdir)'"; \
	  install -D -m755 \
	    -s --strip-program $(top_srcdir)/debian/bin/fix-shebang \
	    "$$p" "$(DESTDIR)/$(scriptsdir)/$$(basename -s .sh $$p)"; \
	done

endif
