#!/bin/sh
# Rebuild everything. Run this after adding files to ../raw or editing anything in ../etc.
set -e
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || python3 -m venv .venv
# install the packages in requirements.txt if any is missing (e.g. one added since the venv was made)
.venv/bin/python -c "import openpyxl, pycldf, cldfbench, pypdf" 2>/dev/null || .venv/bin/pip install -q -r requirements.txt
# Steps 1-2 need the source documents in raw/ (a submodule that may be private). Without them the
# build continues from what steps 1-2 last saved in data/, so decisions in etc/ can still be applied.
if .venv/bin/python -c "import sys, paths; sys.exit(0 if paths.raw_available() else 1)"; then
  .venv/bin/python step1_extract_text.py                      # raw/ -> cache/lesson_text
  .venv/bin/python step2_find_pairs_and_verbs.py | tail -1     # cache -> data/extracted_*.csv
else
  echo "raw/ has no source documents (submodule not checked out): skipping steps 1-2, using pipeline/data/"
fi
.venv/bin/python step3_make_cldf.py                          # data + etc/ -> cldf/ (cldfbench)
.venv/bin/cldf validate ../cldf/Dictionary-metadata.json || { echo "cldf/ is not valid CLDF"; exit 1; }
echo "cldf: valid"
.venv/bin/python step4_build_pages.py                        # cldf/ -> Markdown pages
.venv/bin/python step5_build_pdfs.py                         # cldf/ -> PDFs
{ cat templates/cldf_readme_intro.md; echo; .venv/bin/cldf markdown ../cldf/Dictionary-metadata.json 2>/dev/null; } \
    > ../cldf/README.md
echo "Pages are in $(cd .. && pwd): README.md, Dictionary/, Expressions/, Verbs/, Grammar/"
