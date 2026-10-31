"""The four PDFs."""
import re

import pytest

from conftest import PDFS, PDFS_A5, pdf_pages, report

SECTIONS = ["Dialett → Italiano · English", "Italiano → Dialett · English", "English → Dialett · Italiano"]


@pytest.mark.parametrize("name", PDFS + PDFS_A5)
def test_cover_has_edition(name):
    """Every cover shows the edition YYYYMMDDhhmm (decided 2026-10-14); in an A5 book, its title page."""
    assert re.search(r"Edizi[oó]n\s+\d{12}\b", pdf_pages(name)[0]), f"{name}: no edition stamp on the cover"


@pytest.mark.parametrize("name", PDFS + PDFS_A5)
def test_no_placeholders_left(name):
    """No {{…}} placeholder is left unfilled (page numbers, edition, counts)."""
    bad = [f"page {i}: {m}" for i, p in enumerate(pdf_pages(name), 1) for m in re.findall(r"\{\{[^}]*\}\}", p)]
    report(bad, f"unfilled placeholders in {name}")


DICTIONARIES = ["Dictionary/arogno-dictionary.pdf", "Dictionary/arogno-dictionary_a5.pdf"]


def section_pages(name):
    """Page number where each section of the dictionary PDF starts (its title on the page after the contents)."""
    pages = pdf_pages(name)
    out = {}
    for title in SECTIONS:
        hits = [i for i, p in enumerate(pages, 1) if any(line.strip() == title for line in p.splitlines())]
        out[title] = hits[-1] if hits else None
    return out


@pytest.mark.parametrize("name", DICTIONARIES)
def test_dictionary_sections_start_on_odd_pages(name):
    """Each language section starts on a right-hand (odd) page: the sections are filed separately in a
    binder (owner, 2026-10-19), and a book's sections open on the right too."""
    bad = [f"{t}: page {n}" for t, n in section_pages(name).items() if n is None or n % 2 == 0]
    report(bad, "dictionary sections not starting on an odd page")


@pytest.mark.parametrize("name", DICTIONARIES)
def test_dictionary_contents_page_numbers(name):
    """The contents page gives the page each section really starts on."""
    pages = pdf_pages(name)
    contents = next((p for p in pages[:4] if "Contents" in p), "")
    bad = []
    for title, n in section_pages(name).items():
        m = re.search(re.escape(title) + r"\s+(\d+)", contents)
        if not m or int(m.group(1)) != n:
            bad.append(f"{title}: contents say {m and m.group(1)}, starts on {n}")
    report(bad, "wrong page numbers on the contents page")


def test_dictionary_cover_quote():
    """The cover saying has its translation and no attribution (owner, 2026-10-29)."""
    cover = " ".join(pdf_pages("Dictionary/arogno-dictionary.pdf")[0].split())
    assert "Parla cumè ta mangiat." in cover and "Say it plainly" in cover and "nona" not in cover


def web_links(name):
    """The links of a PDF that lead to a page online (PDF link annotations with a URI)."""
    import pypdf
    from conftest import ROOT
    out = []
    for page in pypdf.PdfReader(ROOT / name).pages:
        for a in page.get("/Annots") or []:
            act = a.get_object().get("/A")
            uri = act.get_object().get("/URI") if act else None
            if uri:
                out.append(str(uri))
    return out


@pytest.mark.parametrize("name", ["Dictionary/arogno-dictionary.pdf", "Grammar/arogno-grammar.pdf"])
def test_verb_links_lead_to_verb_pages(name):
    """Read on screen, a verb in the dictionary and grammar PDFs links to its page on GitHub (owner,
    2026-10-30), and every such link leads to a page that exists."""
    from urllib.parse import unquote
    from conftest import VERBS
    links = [u for u in web_links(name) if "/blob/main/Verbs/" in u]
    assert len(links) > 20, f"{name}: only {len(links)} links to verb pages"
    bad = sorted({u for u in links if not (VERBS / unquote(u.rsplit("/", 1)[1])).exists()})
    report(bad, f"links in {name} to verb pages that do not exist")


def test_links_do_not_show_on_paper():
    """A PDF link is never printed; its text must also look like the text around it: same colour, no
    underline (owner, 2026-10-30: the links must not show on paper)."""
    from conftest import ROOT
    css = (ROOT / "pipeline" / "step5_build_pdfs.py").read_text()
    assert re.search(r"a\.web \{ color: inherit; text-decoration: none; \}", css), "a.web is not styled as plain text"
    for name in ("print_dictionary.html", "print_grammar.html"):
        page = (ROOT / "pipeline" / "cache" / name).read_text()
        # the attributions pages' links are plain text by .credits a
        page = re.sub(r'<div class="credits".*?</div>\s*(?=<section|<div class="part|\{\{recto)', "", page, flags=re.S)
        assert re.search(r"\.credits a \{ color: inherit; text-decoration: none; \}", css)
        assert not re.search(r'<a (?![^>]*class="(web|head|toc)")[^>]*href="http', page), f"{name}: a web link without class web"


def margins(name):
    """(page number, left, right) margins in mm of every page with text, from the words' positions."""
    import subprocess
    from conftest import ROOT
    box = subprocess.run(["pdftotext", "-bbox", str(ROOT / name), "-"], capture_output=True, text=True, check=True).stdout
    out = []
    for n, page in enumerate(re.split(r"<page ", box)[1:], 1):
        width = float(re.match(r'width="([\d.]+)"', page).group(1))
        xs = [(float(a), float(b)) for a, b in re.findall(r'xMin="([\d.]+)" yMin="[\d.]+" xMax="([\d.]+)"', page)]
        if xs:
            mm = 25.4 / 72
            out.append((n, min(a for a, _ in xs) * mm, (width - max(b for _, b in xs)) * mm))
    return out


@pytest.mark.parametrize("name", PDFS)
def test_wider_margin_on_the_binding_side(name):
    """Printed double-sided and punched for a binder (owner, 2026-10-30): the binding side (left of an odd,
    right-hand page; right of an even one) keeps at least 19 mm clear, past the holes of a 2-hole punch
    (centred 12 mm from the edge). The cover, a full-page design, is left out."""
    bad = []
    for n, left, right in margins(name):
        if n == 1:
            continue
        binding = left if n % 2 else right
        if binding < 19:
            bad.append(f"page {n}: {binding:.1f} mm on the binding side ({'left' if n % 2 else 'right'})")
    report(bad, f"pages of {name} with text too close to the binding")


BOOK_PAGES = {"dictionary": "print_dictionary.html", "expressions": "print_expressions.html",
              "verbs": "print_verbs.html", "grammar": "print_grammar.html"}


def attribution_parts():
    """(books, opening words) of every bullet and ## section of ATTRIBUTIONS.md: the books named by the
    <!-- books: … --> line before it (all four when there is none; an item in a tagged section takes the
    section's books)."""
    from conftest import ROOT
    out, pending, section = [], None, set(BOOK_PAGES)
    for line in (ROOT / "ATTRIBUTIONS.md").read_text().splitlines():
        m = re.match(r"<!--\s*books:\s*(.*?)\s*-->$", line.strip())
        if m:
            pending = {b.strip() for b in m.group(1).split(",")}
            continue
        if line.startswith("## "):
            section = pending or set(BOOK_PAGES)
            out.append((section, line[3:]))
        elif line.startswith("- "):
            words = re.sub(r"[*`]|\[([^\]]*)\]\([^)]*\)", r"\1", line[2:]).split()[:6]
            out.append((pending or section, " ".join(words)))
        pending = None if not line.startswith("<!--") else pending
    return out


def test_each_pdf_prints_only_its_own_attributions():
    """Each PDF prints the parts of ATTRIBUTIONS.md that concern it (owner, 2026-10-30: the dictionary had
    the grammar's notes): a tagged section or item only in the books it names, the rest in all four."""
    import html
    from conftest import ROOT
    text = {}
    for book, f in BOOK_PAGES.items():
        page = ROOT / "pipeline" / "cache" / f
        if not page.exists():
            pytest.skip(f"{f} not printed")
        credits = re.search(r'<div class="credits" id="attributions">(.*?)</div>', page.read_text(), flags=re.S)
        text[book] = " ".join(re.sub(r"<[^>]+>", "", html.unescape(credits.group(1))).split()) if credits else ""
    parts = attribution_parts()
    assert len(parts) > 10
    bad = []
    for books, words in parts:
        for book in BOOK_PAGES:
            shown = words in text[book]
            if shown != (book in books):
                bad.append(f"{words!r}: {'printed' if shown else 'missing'} in {book}")
    report(bad, "attributions printed in the wrong PDFs")


@pytest.mark.parametrize("name", PDFS_A5)
def test_a5_page_size(name):
    """The books to be glue-bound by Expresta are A5, 148 x 210 mm, on every page (owner, 2026-10-31)."""
    import pypdf
    from conftest import ROOT
    if not (ROOT / name).exists():
        pytest.skip(f"{name} not built")
    mm = 25.4 / 72
    bad = [f"page {n}: {float(p.mediabox.width) * mm:.1f} x {float(p.mediabox.height) * mm:.1f} mm"
           for n, p in enumerate(pypdf.PdfReader(ROOT / name).pages, 1)
           if abs(float(p.mediabox.width) * mm - 148) > .2 or abs(float(p.mediabox.height) * mm - 210) > .2]
    report(bad, f"pages of {name} that are not A5")


@pytest.mark.parametrize("name", PDFS_A5)
def test_a5_margins(name):
    """A5 books (owner, 2026-10-31): bound, not punched, so at least 14.5 mm on the binding side (left of an
    odd page, right of an even one) and 7.5 mm on the outer side; Expresta trims up to 2.5 mm."""
    bad = []
    for n, left, right in margins(name):
        binding, outer = (left, right) if n % 2 else (right, left)
        if binding < 14.5 or outer < 7.5:
            bad.append(f"page {n}: binding {binding:.1f} mm, outer {outer:.1f} mm")
    report(bad, f"pages of {name} with text too close to an edge")


@pytest.mark.parametrize("name", PDFS_A5)
def test_a5_title_page(name):
    """An A5 book is bound inside a separate cover, so it opens with a plain title page repeating the
    title (owner, 2026-10-31), and its back gives the edition and licence; the colour cover is not in it."""
    pages = pdf_pages(name)
    first = " ".join(pages[0].split())
    assert "Guido Casellini" in first and "MAGUIRE’S" in first, f"{name}: page 1 is not the title page"
    assert "CC BY 4.0" in pages[1], f"{name}: page 2 does not give the licence"
    assert "Contents" in pages[2] or "Indice" in pages[2], f"{name}: the contents are not on page 3"


@pytest.mark.parametrize("name", PDFS)
def test_a5_has_the_same_text(name):
    """The A5 book is the binder version laid out with other margins and scaled down (owner, 2026-10-31:
    the same layout, smaller). Since the text area is a little narrower, check that no text was cut off or
    lost: after the cover (A4) and the title page and its back (A5), both hold exactly the same characters
    (spaces, digits and hyphens aside, as line breaks and page numbers move)."""
    from collections import Counter
    a5 = name.replace(".pdf", "_a5.pdf")

    def chars(pages):
        return Counter(c for c in "".join(pages) if not c.isspace() and not c.isdigit() and c != "-")
    a, b = chars(pdf_pages(name)[1:]), chars(pdf_pages(a5)[2:])
    report([f"only in {name}: {dict((a - b).most_common(10))}", f"only in {a5}: {dict((b - a).most_common(10))}"]
           if a != b else [], f"text differs between {name} and {a5}")


@pytest.mark.parametrize("name", PDFS)
def test_a5_cover(name):
    """The colour cover alone, at A5, for the A5 book (owner, 2026-10-31): one page, the A4 PDF's cover."""
    import pypdf
    from conftest import ROOT
    cover = name.replace(".pdf", "_a5_cover.pdf")
    if not (ROOT / cover).exists():
        pytest.skip(f"{cover} not built")
    pages = pypdf.PdfReader(ROOT / cover).pages
    mm = 25.4 / 72
    size = (round(float(pages[0].mediabox.width) * mm), round(float(pages[0].mediabox.height) * mm))
    assert len(pages) == 1 and size == (148, 210), f"{cover}: {len(pages)} pages, {size} mm"
    # same characters (pdftotext orders rotated and overlapping text differently at another size)
    assert sorted("".join(pdf_pages(cover)[0].split())) == sorted("".join(pdf_pages(name)[0].split())), \
        f"{cover} is not the cover"
