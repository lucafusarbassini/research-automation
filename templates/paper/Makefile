MAIN = main
LATEX = pdflatex
BIBTEX = biber

.PHONY: all clean watch

all: $(MAIN).pdf

$(MAIN).pdf: $(MAIN).tex references.bib
	$(LATEX) $(MAIN)
	$(BIBTEX) $(MAIN)
	$(LATEX) $(MAIN)
	$(LATEX) $(MAIN)

clean:
	rm -f *.aux *.bbl *.bcf *.blg *.log *.out *.run.xml *.toc

watch:
	while true; do \
		inotifywait -e modify $(MAIN).tex references.bib figures/*.pdf; \
		make all; \
	done
