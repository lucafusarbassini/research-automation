# Journal-Specific Templates

This directory is intended for journal-specific LaTeX class files, style files, and bibliography styles. The main template in `../main.tex` uses a generic `article` class that can be adapted to any journal by swapping in the appropriate files.

## How to Use

1. **Download** the official LaTeX template from your target journal.
2. **Place** the class (`.cls`), style (`.sty`), and bibliography style (`.bst`) files in a subdirectory here named after the journal.
3. **Modify** `main.tex` to load the journal class instead of `article`.

For example, to target *Nature*:

```
journals/
  nature/
    nature.cls
    naturemag.bst
```

Then change the first line of `main.tex`:

```latex
% Replace:
\documentclass[11pt,a4paper,onecolumn]{article}
% With:
\documentclass{nature}
```

## Common Journals and Template Sources

| Journal | Template URL | Notes |
|---------|-------------|-------|
| **Nature** | https://www.nature.com/nature/for-authors/formatting-guide | `nature.cls`, single-column, ~3000 words |
| **Science** | https://www.science.org/content/page/instructions-preparing-initial-manuscript | Uses `scifile.sty` |
| **PNAS** | https://www.pnas.org/author-center/submitting-your-manuscript | `pnas.cls`, two-column |
| **Bioinformatics** | https://academic.oup.com/bioinformatics/pages/instructions-for-authors | OUP `bioinfo.cls`, two-column |
| **PLOS ONE** | https://journals.plos.org/plosone/s/latex | `plos2015.sty`, single-column |
| **IEEE** | https://www.ieee.org/conferences/publishing/templates.html | `IEEEtran.cls`, two-column |
| **ACM** | https://www.acm.org/publications/proceedings-template | `acmart.cls`, flexible layout |
| **JMLR** | https://www.jmlr.org/format/format.html | `jmlr.cls`, single-column |
| **NeurIPS** | https://neurips.cc/Conferences/2025/PaperInformation/StyleFiles | `neurips_2025.sty` |
| **ICML** | https://icml.cc/Conferences/2025/StyleAuthorInstructions | `icml2025.sty` |
| **Springer** | https://www.springer.com/gp/livingreviews/latex-templates | `svjour3.cls` |
| **Elsevier** | https://www.elsevier.com/researcher/author/policies-and-guidelines/latex-instructions | `elsarticle.cls` |

## Tips

- **Do not commit** large binary files (e.g., journal logos) to version control. Add them to `.gitignore`.
- Many journals provide **Overleaf templates** that can be downloaded as a zip and extracted here.
- When switching journals, you may also need to update the bibliography style in `preamble.tex` (change `\bibliographystyle{plainnat}` to the journal-specific `.bst`).
- Some journal classes redefine commands from common packages. If you encounter conflicts, selectively comment out lines in `preamble.tex`.
