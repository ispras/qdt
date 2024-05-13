# useful links:
# https://rmarkdown.rstudio.com/authoring_pandoc_markdown.html
# https://pandoc.org/MANUAL.html

# some req:
# sudo apt install xml-twig-tools

# Default settings

all:

SHELL:=/bin/bash
outs:=
exts:=
REF_DOCX:= ref.docx
MDP_ARGS:=
PANDOC_ARGS:=
sources:= # don't need to add regular sorces like main.md
src_exts:= # don't need to add regular extansions like md, rst, svg

# User settings

# can comment this out if MS Ofice files are NOT generated
MDP_ARGS += --svg2png

outs += features

exts += docx
exts += html

# End of user settings

define do_pandoc
	pandoc \
	$(PANDOC_ARGS) \
	$(3) \
	--standalone \
	-o $(2) \
	$(1)
endef

define do_pandoc_in_dir
	$(eval DIR := $(dir $(1)))
	if [ "$(DIR)" = "" ] ; then \
		$(call do_pandoc, \
		$(1), $(2), $(3)); \
	else \
		cd $(DIR); \
		$(call do_pandoc, \
		$(1:$(DIR)%=%), $(2:$(DIR)%=%), $(3)); \
	fi
endef

define make_docx
	$(call do_pandoc_in_dir, $(1), $(2), --reference-doc=$(REF_DOCX))
endef

src_exts+=md

%.pmd : %.md md-preprocessor.py
	./md-preprocessor.py $(MDP_ARGS) -o $@ $<

%.docx : %.pmd
	$(call make_docx, $<, $@)

src_exts+=rst

%.docx : %.rst
	$(call make_docx, $<, $@)

%.html : %.pmd
	$(call do_pandoc_in_dir, $<, $@)

# reference index
%.mdr : %.md
	./md-preprocessor.py $(MDP_ARGS) --refs $@ $< > /dev/null

src_exts+=svg

%.png : %.svg
	convert -density 300 $< $@

# SVG->PDF
# https://superuser.com/questions/381125/how-do-i-convert-an-svg-to-a-pdf-on-linux

# The method below failes fonts.
#%.pdf : %.svg
#	if ! rsvg-convert -f pdf -o $@ $< ; then \
#	    echo "hint: sudo apt-get install librsvg2-bin"; \
#	    exit 1; \
#	fi

%.pdf : %.svg
	if ! inkscape --export-pdf=$@ $< ; then \
	    echo "hint: sudo apt-get install inkscape"; \
	    exit 1; \
	fi

#=
generated :=
targets :=

targets += $(foreach o,$(outs),$(foreach ext,$(exts),$(o).$(ext)))

generated += $(targets)

pmds := $(foreach o,$(outs),$(if $(wildcard $(o).md),$(o).pmd))

# This line does not only result in removing of preprocessed files during
# `clean` target processing. It also preserves them after `all` target
# processing (without this line, those files are removed by `make` as
# intermediate files). Both effects of this line are desired.
generated += $(pmds)

# unzip docx and pretty print XMLs
ifeq ($(findstring docx,$(exts)),docx)

docxDirs := $(foreach o,$(outs),$(o).docx_files)

# Uncomment this to unzip all DOCXs
#targets += $(docxDirs)
# Or add line
#all: output.docx_files
# to unzip selected "output.docx".
# Or use command `make output.docx_files`

generated += $(docxDirs)

%.docx_files : %.docx
	unzip -o $< -d $@

	for f in "$@/word"/* ; \
	do \
	  if [[ $$f == *.[xX][mM][lL] ]] ; then \
	    mv $$f $${f}.orig ; \
	    cat $${f}.orig | xmllint --format - > $$f ; \
	  fi; \
	done; \

$(foreach o,$(outs),$(o).docx) : $(REF_DOCX)

endif

SUFFIXES += .d

dep_files := $(foreach o,$(outs),$(if $(wildcard $(o).md),$(o).d))

generated += $(dep_files)

ifeq (0, $(words $(findstring $(MAKECMDGOALS), clean)))
    -include $(dep_files)
endif

%.d: %.md Makefile md-preprocessor.py
	./md-preprocessor.py $(MDP_ARGS) -o $(patsubst %.d,%.pmd,$@) -u $@ $<

$(generated) : Makefile

all: $(targets)
#	echo $(targets)

# Use file name "empty.png" to add formatting to description of a "figure"
# which has no a backing file.
%empty.png:
	convert -size 1x1 xc:white $@

clean:
	rm -rf $(generated)

.PHONY: clean

sources+=$(foreach o,$(outs),$(foreach ext,$(src_exts),$(o).$(ext)))
sources+=$(REF_DOCX)
sources+=${MAKEFILE_LIST}

auto: all
	./autobuild.sh $(sources)

.PHONY: auto

