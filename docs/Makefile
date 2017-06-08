all: article.doc article.html C2600.png

clean:
	rm -f article.doc
	rm -f article.html
	rm -f *.pmd
	rm -f *.png

%.doc : %.pmd
	pandoc --standalone --smart -o $@ $<

%.html : %.pmd
	pandoc --standalone --smart -o $@ $<

%.pmd : %.md
	python md-preprocessor.py -o $@ $< > /dev/null

%.png : %.svg
	convert -density 150 $< $@

