all:

#########################
# Target specific rules #
#########################

PANDOC_PATH := PATH="$$HOME/.local/bin/:$$PATH"
MDP_ARGS := --ispras
REF_DOCX := ref.docx
extensions := docx html pdf
SVG2PNG_DPI := 300

# article (1-st paper, a technical doc, about QDT)
all : $(foreach ext,$(extensions),article.$(ext))

article-PNGs := \
 C2600.png \
 Q35.png \
 main.png \

$(foreach ext,$(extensions),article.$(ext)): \
 $(article-PNGs)

article.html : PANDOC_ARGS += --css ispras.css
article.docx : $(REF_DOCX)

clean : clean-article
clean-article:
	rm -f $(foreach ext,$(extensions),article.$(ext))
	rm -f $(article-PNGs)

# isp-article (article variant for ISP RAS proceedings)
all : $(foreach ext,$(extensions),isp-article.$(ext))

isp-article-PNGs = \
 $(article-PNGs)

$(foreach ext,$(extensions),isp-article.$(ext)): \
 $(isp-article-PNGs)

isp-article.html : PANDOC_ARGS += --css ispras.css
isp-article.docx : $(REF_DOCX)

clean : clean-isp-article
clean-isp-article:
	rm -f $(foreach ext,$(extensions),isp-article.$(ext))
	rm -f $(isp-article-PNGs)

# report (1-st report slides, on ISP RAS internal seminar, 18.10.2017)
all : report.pdf

report-PNGs = \
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
 source-example.png \
 type-reference.png \
 workflow.png \
 workflow-old.png \

report.pdf : report.tex \
 AM79C971.jpg \
 REMOTE.jpg \
 $(report-PNGs) \

clean : clean-report
clean-report:
	rm -f $(foreach ext,pdf aux log nav out snm toc dvi vrb,report.$(ext))
	rm -f $(report-PNGs)

# isp-open (2-nd report slides, on ISP RAS Open 2017 conference)
all : isp-open.pdf

isp-open-PNGs = \
 C2600.png \
 c2600_pci_c_chunks.png \
 gdb-feedback-en.png \
 device-model-ex-en.png \
 heuristics-en.png \
 legend.png \
 machine-example.png \
 main-en.png \
 Q35-h.png \
 source-example.png \
 type-reference.png \
 workflow-en.png \
 workflow-old-en.png \

isp-open.pdf : isp-open.tex \
 AM79C971.jpg \
 REMOTE.jpg \
 $(isp-open-PNGs) \

clean : clean-isp-open
clean-isp-open:
	rm -f $(foreach ext,pdf aux log nav out snm toc dvi vrb,isp-open.$(ext))
	rm -f $(isp-open-PNGs)

# registers (paper about device register model of QDT, for Ivannikov Memorial
# Workshop 2018)
all : registers.pdf

registers.pdf : registers.tex \
 IEEEtran.cls \

clean : clean-registers
clean-registers:
	rm -f $(foreach ext,pdf aux log nav out snm toc dvi vrb,registers.$(ext))

# report2 (2-nd report slides, on ISP RAS internal seminar, 07.11.2018,
# about software driven debugging of QEmu)
all : report2.pdf

report2-PNGs = \
 lowlevel-debug-primitives.png \
 highlevel-debug-primitives.png \
 debug-hierarchy.png \
 qdt-debug.png \
 git-breakpoints.png \
 non-blocking.png \
 common-debug-tools.png \
 gdb-python.png \
 debug-in-workflow-en.png \
 domain-specific-debug.png \
 suffix-form.png \
 prefix-form.png \
 dwarf-expr-1.png \
 dwarf-expr-2.png \
 qdt-debug-verb.png \
 watcher-example.png \
 qom.png \
 qom-tree-getting.png \
 machine-reversing.png \

report2.pdf : report2.utex \
 $(report2-PNGs) \
 ddd-btree.png \
 ddd-plot.png \
 i440fx.png \
 exynos.png \

clean : clean-report2
clean-report2:
	rm -f $(foreach ext,pdf aux log nav out snm toc dvi vrb,report2.$(ext))
	rm -f $(report2-PNGs)

################
# Common rules #
################

clean:
	rm -f *.pmd

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

%.png : %.svg
	if ! convert -density $(SVG2PNG_DPI) $< $@ ; then \
	  inkscape --without-gui --export-dpi=$(SVG2PNG_DPI) $< --export-png=$@ ; \
	fi

%.png : %.gv
	dot -Tpng -Gdpi=300 $< -o $@

# *.utex is a *.tex but with UTF-8 characters in commands (ex.: \пример{})
%.tex : %.utex
	cat $< | ./utf8cmds.py > $@

%.pdf : %.tex
	pdflatex -interaction=nonstopmode $< $@ # two step generation
	pdflatex -interaction=nonstopmode $< $@

