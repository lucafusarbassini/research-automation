commit=598f7d19e679b5d826d2

git checkout $commit 
latexpand main.tex > _main_old.tex
git checkout master


latexpand main.tex > _main_new.tex

latexdiff _main_old.tex _main_new.tex > diff.tex

make diff
