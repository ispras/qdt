extensions := docx html pdf

all: $(foreach ext,$(extensions),article.$(ext))
all: $(foreach ext,$(extensions),isp-article.$(ext))

$(foreach ext,$(extensions),article.$(ext)) : C2600.png Q35.png main.png
$(foreach ext,$(extensions),isp-article.$(ext)) : C2600.png Q35.png main.png

article.html : PANDOC_ARGS += --css ispras.css

isp-article.html : PANDOC_ARGS += --css ispras.css

clean:
	rm -f $(foreach ext,$(extensions),article.$(ext))
	rm -f *.pmd
	rm -f *.png
	rm -f $(foreach ext,pdf aux log nav out snm toc dvi vrb,report.$(ext))
	rm -f $(foreach ext,$(extensions),isp-article.$(ext))

define do_pandoc
	pandoc \
	$(PANDOC_ARGS) \
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
	python md-preprocessor.py $(MDP_ARGS) -o $@ $< > /dev/null

SVG2PNG_DPI := 300

%.png : %.svg
	if ! convert -density $(SVG2PNG_DPI) $< $@ ; then \
	  inkscape --without-gui --export-dpi=$(SVG2PNG_DPI) $< --export-png=$@ ; \
	fi

%.png : %.gv
	dot -Tpng -Gdpi=300 $< -o $@

# =
all: report.pdf

report.pdf : report.tex main.png workflow.png C2600.png AM79C971.jpg \
REMOTE.jpg generation.png workflow-old.png device-model.png source-example.png \
c2600_pci_c_chunks.png machine-example.png legend.png Q35-h.png heuristics.png
	pdflatex $< $@ # two step generation
	pdflatex $< $@

