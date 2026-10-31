"""Shared helpers for the tests of the generated material (Dictionary/, Verbs/, Expressions/, Grammar/, PDFs).

Run after a build, from the repository root:  pipeline/.venv/bin/python -m pytest -q tests
(build_all.sh runs them at the end). Each test checks one rule the owner agreed for the output and
reports every failure it finds, naming the entry, not just the first one. A known exception goes in the
test's own KNOWN list with the reason, so only new failures break the build.

Rule (owner, 2026-10-29): whenever a problem is checked for in a session, the check becomes a test here.
"""
import csv
import functools
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import step4_build_pages as build

DICT = ROOT / "Dictionary"
VERBS = ROOT / "Verbs"
EXPR = ROOT / "Expressions"
DATA = ROOT / "pipeline" / "data"
ETC = ROOT / "etc"
CLDF = ROOT / "cldf"
PRIVATE = ROOT / "raw" / "extracted"
PDFS = ["Dictionary/arogno-dictionary.pdf", "Expressions/arogno-expressions.pdf",
        "Verbs/arogno-verbs.pdf", "Grammar/arogno-grammar.pdf"]
# the A5 books, bound inside a separate cover (owner, 2026-10-31)
PDFS_A5 = [n.replace(".pdf", "_a5.pdf") for n in PDFS]


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def table_rows(path):
    """The body rows of every Markdown table in a page: (section heading, header cells, cells).
    Cells holding several senses keep them separated by <br>."""
    out, section, header = [], "", None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            section, header = line.lstrip("# ").strip(), None
        elif line.startswith("|"):
            cells = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
            if header is None:
                header = cells
            elif not all(set(c) <= set("-: ") for c in cells):
                out.append((section, header, cells))
        else:
            header = None
    return out


def lookup_rows(page):
    """The rows of a dictionary look-up page as dicts keyed by column name, senses split into lists."""
    rows = []
    for section, header, cells in table_rows(DICT / page):
        if header[0] not in ("Dialett", "Italiano", "English"):
            continue
        r = {h: c for h, c in zip(header, cells)}
        r["_head"], r["_section"] = cells[0], section
        r["_senses"] = {h: c.split("<br>") for h, c in r.items() if not h.startswith("_")}
        rows.append(r)
    return rows


def headword(cell):
    """The bare look-up word of a head cell: 'viagg *n. m., pl. viagg*' -> viagg, 'nonna †' -> nonna."""
    return build.key(re.sub(r"\s*\*.*$", "", cell).replace("†", "").replace("⚠", "").strip())


@functools.cache
def pdf_pages(name):
    """The text of each page of a PDF (pdftotext, one string per page)."""
    path = ROOT / name
    if not path.exists():
        pytest.skip(f"{name} not built")
    text = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, check=True).stdout
    return text.split("\f")


def report(failures, what, limit=40):
    """Fail with every failure listed (up to limit), so one run shows the whole problem."""
    if failures:
        shown = "\n  ".join(map(str, failures[:limit]))
        more = f"\n  … and {len(failures) - limit} more" if len(failures) > limit else ""
        pytest.fail(f"{len(failures)} {what}:\n  {shown}{more}", pytrace=False)
