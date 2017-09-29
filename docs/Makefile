extensions := docx html pdf

all: $(foreach ext,$(extensions),article.$(ext)) report.pdf

$(foreach ext,$(extensions),article.$(ext)) : C2600.png Q35.png main.png

clean:
	rm -f $(foreach ext,$(extensions),article.$(ext))
	rm -f *.pmd
	rm -f *.png
	rm -f $(foreach ext,pdf aux log nav out snm toc,report.$(ext))

define do_pandoc
	pandoc \
	$(3) \
	--standalone \
	--smart \
	-o $(2) \
	$(1)
endef

%.docx : %.pmd
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

%.png : %.gv
	dot -Tpng -Gdpi=300 $< -o $@

report.pdf : report.tex main.png workflow.png C2600.png AM79C971.jpg \
REMOTE.jpg generation.png workflow-old.png device-model.png source-example.png \
c2600_pci_c_chunks.png machine-example.png legend.png Q35-h.png heuristics.png
	pdflatex $< $@ # two step generation
	pdflatex $< $@

