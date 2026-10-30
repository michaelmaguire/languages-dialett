"""The verb pages (Verbs/*.md)."""
import re

import pytest

from conftest import VERBS, report, table_rows

PAGES = sorted(p for p in VERBS.glob("*.md") if p.name != "README.md")
SECTIONS = ["Infinitive", "Indicativo", "Condizionale", "Congiuntivo", "Imperativo"]
PERSONS = ["mi", "ti", "le / lü", "nüm", "vialtri", "lur"]
IMPERATIVE = ["ti", "nüm", "vialtri"]


def test_there_are_verb_pages():
    assert len(PAGES) > 100, f"only {len(PAGES)} verb pages"


def test_same_sections_in_order():
    """Every verb page has the same sections, in the same order (decided 2026-10-14)."""
    bad = []
    for p in PAGES:
        found = re.findall(r"^## (.+)$", p.read_text(), flags=re.M)
        if found != SECTIONS:
            bad.append(f"{p.name}: {found}")
    report(bad, "verb pages with other sections")


def test_infinitive_table():
    """The Infinitive table gives Dialett, Italiano and English, the English as 'to …'."""
    bad = []
    for p in PAGES:
        # 'Dialett †' when the infinitive itself is inferred
        rows = [cells for section, header, cells in table_rows(p)
                if header[0].startswith("Dialett") and header[1:3] == ["Italiano", "English"]]
        if not rows:
            bad.append(f"{p.name}: no infinitive table")
            continue
        di, it, en = rows[0][:3]
        if not (di.strip("* ") and it and en):
            bad.append(f"{p.name}: empty cell in {rows[0][:3]}")
        elif not en.startswith("to ") or en.startswith("to to "):
            bad.append(f"{p.name}: English {en!r}")
    report(bad, "verb pages with a wrong infinitive table")


def tense_tables(p):
    """(section, header, rows) of each conjugation table: the tables whose first column is the person."""
    tables, cur = [], None
    for section, header, cells in table_rows(p):
        if header[0] != "":
            continue
        if cur is None or cur[1] is not header:
            cur = (section, header, [])
            tables.append(cur)
        cur[2].append(cells)
    return tables


def test_every_person_in_every_table():
    """Each tense table lists the six persons in order (the imperative: ti, nüm, vialtri), with a form
    in every cell."""
    bad = []
    for p in PAGES:
        for section, header, rows in tense_tables(p):
            want = IMPERATIVE if section == "Imperativo" else PERSONS
            got = [r[0].strip("*") for r in rows]
            if got != want:
                bad.append(f"{p.name} {header[1:]}: persons {got}")
            for r in rows:
                for tense, form in zip(header[1:], r[1:]):
                    if not form.strip():
                        bad.append(f"{p.name}: {tense}, {r[0].strip('*')} is empty")
    report(bad, "tense tables with a missing person or form")


def test_inferred_column_marked_in_heading_only():
    """A fully inferred column carries † in its heading and not on each form (decided 2026-10-14)."""
    bad = []
    for p in PAGES:
        for section, header, rows in tense_tables(p):
            for i, tense in enumerate(header[1:], 1):
                if "†" in tense and any("†" in r[i] for r in rows):
                    bad.append(f"{p.name}: {tense}")
    report(bad, "columns marked † in the heading and on forms")


def test_index_lists_every_page():
    """Verbs/README.md links every verb page, and every link there leads to a page."""
    text = (VERBS / "README.md").read_text()
    links = set(re.findall(r"\]\(([^)/]+\.md)\)", text))
    pages = {p.name for p in PAGES}
    bad = [f"not in the index: {n}" for n in sorted(pages - links)] + \
          [f"no such page: {n}" for n in sorted(links - pages - {"README.md"})]
    report(bad, "mismatches between the verb index and the pages")


@pytest.mark.parametrize("page", PAGES[:1] or [None])
def test_no_doubled_to(page):
    """No 'to to' on any verb page (2026-10-28)."""
    bad = [f"{p.name}: {line[:80]}" for p in PAGES for line in p.read_text().splitlines()
           if re.search(r"\bto to\b", line)]
    report(bad, "lines with 'to to'")


def test_pdf_and_pages_show_the_same_verbs_and_forms():
    """The PDF sheets and the pages are rendered from one model (pipeline/verbs_model.py, owner 2026-10-30):
    the same verbs in the same order (the index's), and every tense table with the same forms and the same
    † on each form."""
    import html
    from conftest import ROOT
    page = ROOT / "pipeline" / "cache" / "print_verbs.html"
    if not page.exists():
        pytest.skip("the verbs PDF has not been printed")
    text = html.unescape(page.read_text(encoding="utf-8"))
    sheets = re.split(r'<section id="v-\d+"[^>]*>', text)[1:]
    order = re.findall(r"^\| \[[^]]+\]\(([^)]+\.md)\)", (VERBS / "README.md").read_text(), flags=re.M)
    bad = [] if len(sheets) == len(order) else [f"{len(sheets)} sheets in the PDF, {len(order)} verbs in the index"]
    for name, sheet in zip(order, sheets):
        pdf = [re.sub(r"<sup>†</sup>", " †", c) for c in re.findall(r"<td>(.*?)</td>", sheet)]
        md = [c for _, _, rows in tense_tables(VERBS / name) for row in rows for c in row[1:]]
        if pdf != md:
            i = next((i for i, (x, y) in enumerate(zip(pdf, md)) if x != y), min(len(pdf), len(md)))
            bad.append(f"{name}: form {i}: PDF {pdf[i:i + 1]}, page {md[i:i + 1]}")
    report(bad, "verbs that differ between the PDF and the pages")
