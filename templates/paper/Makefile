all: main supp 

supp: supplementary.tex
        latexmk -c;lualatex supplementary;biber supplementary;  lualatex supplementary


main: main.tex
        lualatex main.tex;biber main;lualatex main.tex;lualatex main.tex

small: main.pdf supplementary.pdf 
        gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/prepress -dNOPAUSE -dQUIET -dBATCH -sOutputFile=main_small.pdf main.pdf;gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/prepress -dNOPAUSE -dQUIET -dBATCH -sOutputFile=supplementary_small.pdf supplementary.pdf;

# Below generates differences to an older version (useful for reviews)
diff: diff.tex  
        lualatex diff.tex;biber diff;lualatex diff.tex;lualatex diff.tex