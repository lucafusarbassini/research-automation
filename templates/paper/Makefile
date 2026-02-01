# =============================================================================
#  Makefile — LaTeX build system for research manuscripts
# =============================================================================
#  Targets:
#    make all        Build the PDF (default)
#    make clean      Remove all generated files
#    make watch      Rebuild automatically on file changes
#    make check      Run spell check (aspell) on all .tex files
#    make wordcount  Count words in the manuscript (texcount)
#    make lint       Check for common LaTeX issues (chktex)
# =============================================================================

MAIN       = main
SOURCES    = $(wildcard *.tex)
BIB        = references.bib
FIGURES    = $(wildcard figures/*.pdf figures/*.png figures/*.eps)

LATEX      = pdflatex
LATEXFLAGS = -interaction=nonstopmode -halt-on-error -file-line-error
BIBTEX     = bibtex

# Use latexmk if available — handles rebuild logic automatically
LATEXMK    = latexmk
LATEXMK_FLAGS = -pdf -pdflatex="$(LATEX) $(LATEXFLAGS)" -bibtex

# =============================================================================
#  Default target
# =============================================================================
.PHONY: all clean watch check wordcount lint

all: $(MAIN).pdf

# --- Build with latexmk (preferred) or fallback to manual cycle ------------
$(MAIN).pdf: $(SOURCES) $(BIB) $(FIGURES)
	@if command -v $(LATEXMK) > /dev/null 2>&1; then \
		echo "==> Building with latexmk"; \
		$(LATEXMK) $(LATEXMK_FLAGS) $(MAIN).tex; \
	else \
		echo "==> Building with pdflatex/bibtex (latexmk not found)"; \
		$(LATEX) $(LATEXFLAGS) $(MAIN); \
		$(BIBTEX) $(MAIN); \
		$(LATEX) $(LATEXFLAGS) $(MAIN); \
		$(LATEX) $(LATEXFLAGS) $(MAIN); \
	fi

# =============================================================================
#  Clean
# =============================================================================
clean:
	@if command -v $(LATEXMK) > /dev/null 2>&1; then \
		$(LATEXMK) -C $(MAIN).tex; \
	fi
	rm -f $(MAIN).pdf
	rm -f *.aux *.bbl *.bcf *.blg *.fdb_latexmk *.fls *.log *.out \
	      *.run.xml *.toc *.lof *.lot *.nav *.snm *.vrb *.synctex.gz \
	      *.dvi *.ps

# =============================================================================
#  Watch — rebuild on changes
# =============================================================================
watch:
	@if command -v $(LATEXMK) > /dev/null 2>&1; then \
		echo "==> Watching with latexmk -pvc (press Ctrl-C to stop)"; \
		$(LATEXMK) -pvc $(LATEXMK_FLAGS) $(MAIN).tex; \
	elif command -v inotifywait > /dev/null 2>&1; then \
		echo "==> Watching with inotifywait (press Ctrl-C to stop)"; \
		while true; do \
			inotifywait -q -e modify $(SOURCES) $(BIB) $(FIGURES) 2>/dev/null; \
			$(MAKE) all; \
		done; \
	elif command -v fswatch > /dev/null 2>&1; then \
		echo "==> Watching with fswatch (press Ctrl-C to stop)"; \
		fswatch -o $(SOURCES) $(BIB) | xargs -n1 -I{} $(MAKE) all; \
	else \
		echo "Error: install latexmk, inotifywait (inotify-tools), or fswatch"; \
		exit 1; \
	fi

# =============================================================================
#  Spell check
# =============================================================================
check:
	@if command -v aspell > /dev/null 2>&1; then \
		echo "==> Spell-checking .tex files with aspell"; \
		for f in $(SOURCES); do \
			echo "--- $$f ---"; \
			aspell --mode=tex --lang=en check $$f; \
		done; \
	else \
		echo "Error: aspell is not installed."; \
		echo "  Ubuntu/Debian: sudo apt install aspell aspell-en"; \
		echo "  macOS:         brew install aspell"; \
		exit 1; \
	fi

# =============================================================================
#  Word count
# =============================================================================
wordcount:
	@if command -v texcount > /dev/null 2>&1; then \
		echo "==> Word count (texcount)"; \
		texcount -inc -total $(MAIN).tex; \
	elif command -v detex > /dev/null 2>&1; then \
		echo "==> Approximate word count (detex | wc -w)"; \
		detex $(MAIN).tex | wc -w; \
	else \
		echo "Error: install texcount or detex for word counting."; \
		echo "  Ubuntu/Debian: sudo apt install texcount"; \
		echo "  macOS:         brew install texcount"; \
		exit 1; \
	fi

# =============================================================================
#  Lint — check for common LaTeX issues
# =============================================================================
lint:
	@if command -v chktex > /dev/null 2>&1; then \
		echo "==> Linting with chktex"; \
		chktex -q $(MAIN).tex; \
	else \
		echo "Error: chktex is not installed."; \
		echo "  Ubuntu/Debian: sudo apt install chktex"; \
		echo "  macOS:         brew install chktex"; \
		exit 1; \
	fi
