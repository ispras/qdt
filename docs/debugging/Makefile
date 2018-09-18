# useful links:
# https://rmarkdown.rstudio.com/authoring_pandoc_markdown.html
# https://pandoc.org/MANUAL.html

# some req:
# sudo apt install xml-twig-tools

all:

PANDOC_PATH := PATH="$$HOME/.local/bin/:$$PATH"
SHELL:=/bin/bash
outs := main
exts := docx
MDP_ARGS := --ispras --caption-number-prefix
REF_DOCX := ref.docx

main.docx \
: PANDOC_ARGS= --toc --metadata="toc-title:Содержание" --toc-depth=2

#=

define do_pandoc
	$(PANDOC_PATH) \
	pandoc \
	$(PANDOC_ARGS) \
	$(3) \
	--standalone \
	-o $(2) \
	$(1)
endef

define make_docx
	$(call do_pandoc, \
	--reference-doc=$(REF_DOCX) \
	$(1), $(2))
endef

%.pmd : %.md md-preprocessor.py
	python md-preprocessor.py $(MDP_ARGS) -o $@ $<

%.docx : %.pmd
	$(call make_docx, $<, $@)

%.docx : %.rst
	$(call make_docx, $<, $@)

%.png : %.svg
	convert -density 300 $< $@

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

generated += $(docxDirs)
targets += $(docxDirs)

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

$(generated) : Makefile

all: $(targets)
#	echo $(targets)

clean:
	rm -rf $(generated)

.PHONY: clean

