"""The grammar pages (Grammar/*.md) and their PDF."""
import html
import re

import pytest

from conftest import ROOT, report

GRAMMAR = ROOT / "Grammar"
PDF_HTML = ROOT / "pipeline" / "cache" / "print_grammar.html"


def page_chapters():
    """(chapter id, headings, examples as (number, text)) of each page, in the index's order."""
    index = (GRAMMAR / "README.md").read_text(encoding="utf-8")
    out = []
    for cid in re.findall(r"\| \[[^]]+\]\(([^)]+)\.md\)", index):
        text = (GRAMMAR / f"{cid}.md").read_text(encoding="utf-8")
        heads = [h.split(" · ")[0] for h in re.findall(r"^## (.+)$", text, flags=re.M)]
        examples = [(int(n), t) for n, t in re.findall(r"^\*\*\((\d+)\)\*\* \*(.+)\*$", text, flags=re.M)]
        out.append((cid, heads, examples, text))
    return out


def pdf_chapters():
    if not PDF_HTML.exists():
        pytest.skip("the grammar PDF has not been printed")
    text = html.unescape(PDF_HTML.read_text(encoding="utf-8"))
    out = []
    for cid, body in re.findall(r'<div class="part chapter" id="ch-([^"]+)">(.*?)(?=<div class="part chapter"|$)', text, flags=re.S):
        heads = [re.sub("<[^>]+>", "", h) for h in re.findall(r"<h2>(.*?) <span", body)]
        examples = [(int(n), t) for n, t in re.findall(r'<span class="n">\((\d+)\)</span><div><div class="pt">(.*?)</div>', body)]
        forms = [re.sub(r"<sup>†</sup>", " †", c) for t in re.findall(r'<table class="vt">(.*?)</table>', body)
                 for c in re.findall(r"<td>(.*?)</td>", t)]
        out.append((cid, heads, examples, forms))
    return out


def test_every_chapter_has_examples_numbered_in_order():
    bad = [f"{cid}: {[n for n, _ in ex]}" for cid, _, ex, _ in page_chapters() if [n for n, _ in ex] != list(range(1, len(ex) + 1))]
    report(bad, "chapters whose examples are not numbered 1, 2, 3 …")


def test_pdf_and_pages_have_the_same_chapters_examples_and_forms():
    """The PDF and the pages are rendered from one model (pipeline/grammar_model.py, owner 2026-10-30): the
    same chapters in the same order, the same section headings, the same numbered examples, and every verb
    form of the PDF's tables, with its †, on the page in the same order."""
    pages, pdf = page_chapters(), pdf_chapters()
    bad = [] if [c[0] for c in pages] == [c[0] for c in pdf] else \
        [f"chapters: pages {[c[0] for c in pages]}, PDF {[c[0] for c in pdf]}"]
    for (cid, heads, examples, text), (_, pheads, pexamples, forms) in zip(pages, pdf):
        plain = lambda s: re.sub(r"[*`]", "", s)
        if [plain(h) for h in heads] != pheads:
            bad.append(f"{cid}: headings differ: {heads[:3]} / {pheads[:3]}")
        if examples != pexamples:
            bad.append(f"{cid}: examples differ")
        pos = 0
        for f in forms:                                   # each form found after the previous one
            i = text.find(f"| {f} |", pos)
            if i < 0:
                bad.append(f"{cid}: form {f!r} of the PDF not on the page (in order)")
                break
            pos = i + 1
    report(bad, "differences between the grammar PDF and its pages")
