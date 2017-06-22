extensions := doc html pdf

all: $(foreach ext,$(extensions),article.$(ext))

$(foreach ext,$(extensions),article.$(ext)) : C2600.png main.png

clean:
	rm -f $(foreach ext,$(extensions),article.$(ext))
	rm -f *.pmd
	rm -f *.png

define do_pandoc
	pandoc \
	$(3) \
	--standalone \
	--smart \
	-o $(2) \
	$(1)
endef

%.doc : %.pmd
	$(call do_pandoc, $<, $@)

%.html : %.pmd
	$(call do_pandoc, $<, $@)

%.pdf : %.pmd
	$(call do_pandoc, $<, $@, \
		--latex-engine=xelatex \
		-V mainfont="Times New Roman"\
		-V monofont="Ubuntu Mono" \
	) || true

%.pmd : %.md
	python md-preprocessor.py -o $@ $< > /dev/null

%.png : %.svg
	convert -density 150 $< $@

