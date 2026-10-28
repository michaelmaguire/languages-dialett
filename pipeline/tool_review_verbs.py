#!/usr/bin/env python3
"""A short PDF of chosen verb sheets, e.g. for the teacher to correct by hand: one sheet per verb, exactly
as in Verbs/arogno-verbs.pdf (forms marked † are inferred), nothing else.

    .venv/bin/python tool_review_verbs.py OUT.pdf essere avere andare ...

Verbs are named by their Italian infinitive, in the order wanted. Reads ../cldf (through lexicon.for_pages);
writes only OUT.pdf (not part of the build, nothing in the repository changes).
"""
import sys
from pathlib import Path

import step5_build_pdfs as pdf
from paths import PIPELINE


def main(out, names):
    import lexicon
    _, tables, eng = lexicon.for_pages()
    missing = [n for n in names if n not in tables]
    if missing:
        raise SystemExit(f"no verb page for: {', '.join(missing)} (use the Italian infinitive)")
    sheets = [pdf.verb_sheet(n, tables[n], eng, i) for i, n in enumerate(names, 1)]
    document = (f'<!doctype html><meta charset="utf-8"><title>Verbi da controllare – dialett da Rögn</title>'
                f"<style>{pdf.CSS}</style>{''.join(sheets)}")
    document = pdf.PLACEHOLDER.sub(lambda m: m.group(1)[2:], document)      # one sheet per page: v-3 is page 3
    page = PIPELINE / "cache" / "print_review_verbs.html"
    page.write_text(document)
    if pdf.print_pdf(Path(out).resolve(), page):
        print(f"{Path(out).name}: {len(sheets)} verb sheets -> {Path(out).resolve()}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2:])
