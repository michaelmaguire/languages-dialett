"""The expression pages (Expressions/*.md) and their PDF."""
import html
import re

import pytest

from conftest import EXPR, ROOT, build, report, table_rows

MODEL_PDF = ROOT / "pipeline" / "cache" / "print_expressions.html"


def page_topics():
    """The topic pages in the index's order, with their expressions (dialect, keyed) in page order."""
    index = (EXPR / "README.md").read_text(encoding="utf-8")
    out = []
    for name in re.findall(r"\]\(([^)]+\.md)\)", index):
        path = EXPR / re.sub(r"%20", " ", name)
        if path.name == "README.md" or not path.exists():
            continue
        out.append((path.name, [build.key(c[0].replace(" ⚠", "")) for _, h, c in table_rows(path) if h[0] == "Dialett"]))
    return out


def test_every_topic_page_is_in_the_index():
    linked = {name for name, _ in page_topics()}
    pages = {p.name for p in EXPR.glob("*.md") if p.name != "README.md"}
    report(sorted(pages ^ linked), "topic pages missing from the index, or linked but missing")


def test_pdf_and_pages_list_the_same_expressions_in_the_same_order():
    """The PDF and the topic pages are rendered from one model (pipeline/expressions_model.py, owner
    2026-10-30): same topics, in the same order, each with the same expressions in the same order."""
    if not MODEL_PDF.exists():
        pytest.skip("the expressions PDF has not been printed")
    text = html.unescape(MODEL_PDF.read_text(encoding="utf-8"))
    pdf = [[build.key(x) for x in re.findall(r'<div class="x"><b>(.*?)</b>', t)]
           for t in re.split(r'<div class="part topic" id="t-[^"]+">', text)[1:]]
    pages = page_topics()
    bad = [] if len(pdf) == len(pages) else [f"{len(pdf)} topics in the PDF, {len(pages)} pages"]
    for (name, rows), prows in zip(pages, pdf):
        if rows != prows:
            i = next((i for i, (x, y) in enumerate(zip(rows, prows)) if x != y), min(len(rows), len(prows)))
            bad.append(f"{name}: first difference at row {i}: page {rows[i:i + 1]}, PDF {prows[i:i + 1]}")
    report(bad, "topics that differ between the PDF and the pages")
