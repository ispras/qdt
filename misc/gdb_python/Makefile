# Default target.
all:

# User can redefine macros & rules in settings.mak above its inclusion.

__progs=$(foreach  p,$(progs),$(p).exe)

__PROG_FILES=$(foreach f,$(1) $($(1)),$(f).o)

__progs_files=$(foreach p,$(progs),$(call __PROG_FILES,$p))

clean:
	rm -f $(__progs) $(__progs_files)

%.exe:
	$(CC) $(CFLAGS) $(filter-out Makefile settings.mak,$^) -o $@

include settings.mak

$(foreach f,$(__progs_files) $(__progs),$(eval $(f):settings.mak Makefile))
$(foreach p,$(progs), $(eval $(p).exe: $(call __PROG_FILES,$p) ))
all: $(__progs)
