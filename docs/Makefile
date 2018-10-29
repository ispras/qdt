extensions := docx html pdf

all: $(foreach ext,$(extensions),article.$(ext))
all: $(foreach ext,$(extensions),isp-article.$(ext))

$(foreach ext,$(extensions),article.$(ext)) : C2600.png Q35.png main.png
$(foreach ext,$(extensions),isp-article.$(ext)) : C2600.png Q35.png main.png

article.html : PANDOC_ARGS += --css ispras.css

isp-article.html : PANDOC_ARGS += --css ispras.css

PANDOC_PATH := PATH="$$HOME/.local/bin/:$$PATH"
MDP_ARGS := --ispras
REF_DOCX := ref.docx

article.docx : $(REF_DOCX)

isp-article.docx : $(REF_DOCX)

clean:
	rm -f $(foreach ext,$(extensions),article.$(ext))
	rm -f *.pmd
	rm -f *.png
	rm -f $(foreach ext,pdf aux log nav out snm toc dvi vrb,report.$(ext))
	rm -f $(foreach ext,$(extensions),isp-article.$(ext))
	rm -f $(foreach ext,pdf aux log nav out snm toc dvi vrb,isp-open.$(ext))

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

%.docx : %.pmd
	$(call make_docx, $<, $@)

%.html : %.pmd
	$(call do_pandoc, $<, $@)

%.pdf : %.pmd
	$(call do_pandoc, $<, $@, \
		--pdf-engine=xelatex \
		-V geometry:margin=1.5cm \
		-V papersize:a5 \
		-V mainfont="Times New Roman" \
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

%.pdf : %.tex
	pdflatex $< $@ # two step generation
	pdflatex $< $@

# =
all: report.pdf

report.pdf: report.tex \
 AM79C971.jpg \
 C2600.png \
 c2600_pci_c_chunks.png \
 device-model.png \
 device-model-ex.png \
 gdb-feedback.png \
 generation.png \
 heuristics.png \
 legend.png \
 machine-example.png \
 main.png \
 Q35-h.png \
 REMOTE.jpg \
 source-example.png \
 type-reference.png \
 workflow.png \
 workflow-old.png \

#=
all: isp-open.pdf

isp-open.pdf: isp-open.tex \
 AM79C971.jpg \
 C2600.png \
 c2600_pci_c_chunks.png \
 gdb-feedback-en.png \
 device-model-ex-en.png \
 heuristics-en.png \
 legend.png \
 machine-example.png \
 main-en.png \
 Q35-h.png \
 REMOTE.jpg \
 source-example.png \
 type-reference.png \
 workflow-en.png \
 workflow-old-en.png \

