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


DICTIONARIES = ["Dictionary/arogno-dictionary.pdf", "Dictionary/arogno-dictionary_a5_book.pdf"]


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


def margins(name, vertical=False, bleed=0):
    """(page number, left, right) margins in mm of every page with text, from the words' positions;
    with vertical, (page number, top, bottom). bleed: mm round the trimmed page, left out."""
    import subprocess
    from conftest import ROOT
    box = subprocess.run(["pdftotext", "-bbox", str(ROOT / name), "-"], capture_output=True, text=True, check=True).stdout
    out = []
    for n, page in enumerate(re.split(r"<page ", box)[1:], 1):
        width = float(re.search(r'width="([\d.]+)"', page).group(1))
        if vertical:
            width = float(re.search(r'height="([\d.]+)"', page).group(1))
        pattern = (r'yMin="([\d.]+)" xMax="[\d.]+" yMax="([\d.]+)"' if vertical
                   else r'xMin="([\d.]+)" yMin="[\d.]+" xMax="([\d.]+)"')
        xs = [(float(a), float(b)) for a, b in re.findall(pattern, page)]
        if xs:
            mm = 25.4 / 72
            out.append((n, min(a for a, _ in xs) * mm - bleed, (width - max(b for _, b in xs)) * mm - bleed))
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
def test_a5_book_file(name):
    """The A5 book's inside pages as the print shop wants them (owner, 2026-10-31; checked against Expresta
    and onlinedruck.ch): PDF/X-3 with the FOGRA52 (uncoated) print condition, every page A5 when trimmed with
    2.5 mm of bleed on every side (153 x 215 mm), every font embedded, and no links."""
    import subprocess
    import pypdf
    from conftest import ROOT
    if not (ROOT / name).exists():
        pytest.skip(f"{name} not built")
    reader = pypdf.PdfReader(ROOT / name)
    assert reader.metadata.get("/GTS_PDFXVersion") == "PDF/X-3:2002", f"{name}: not marked PDF/X-3"
    intent = reader.trailer["/Root"]["/OutputIntents"][0].get_object()
    assert intent["/OutputConditionIdentifier"] == "FOGRA52", f"{name}: output intent {intent}"
    mm = 25.4 / 72
    bad = []
    for n, p in enumerate(reader.pages, 1):
        media = [round(float(v) * mm, 1) for v in p.mediabox]
        trim = [round(float(v) * mm, 1) for v in p.trimbox]
        if media != [0, 0, 153, 215] or trim != [2.5, 2.5, 150.5, 212.5]:
            bad.append(f"page {n}: MediaBox {media}, TrimBox {trim} mm")
        if "/Annots" in p:
            bad.append(f"page {n}: has links")
    fonts = subprocess.run(["pdffonts", str(ROOT / name)], capture_output=True, text=True, check=True).stdout
    bad += [f"font not embedded: {line}" for line in fonts.splitlines()[2:] if line.split()[-5] != "yes"]
    report(bad, f"{name} not as the print shop wants it")


@pytest.mark.parametrize("name", PDFS_A5)
def test_a5_book_black_and_white(name):
    """The inside pages are printed in black and white only (owner, 2026-10-31: cheaper; only the cover is
    in colour): Ghostscript's ink coverage shows no cyan, magenta or yellow on any page."""
    import subprocess
    from conftest import ROOT
    if not (ROOT / name).exists():
        pytest.skip(f"{name} not built")
    out = subprocess.run(["gs", "-q", "-o", "-", "-sDEVICE=inkcov", str(ROOT / name)],
                         capture_output=True, text=True, check=True).stdout
    bad = [f"page {n}: {line.strip()}" for n, line in enumerate(out.splitlines(), 1)
           if any(float(v) > 0 for v in line.split()[:3])]
    report(bad, f"pages of {name} printed with colour ink")


@pytest.mark.parametrize("name", PDFS_A5)
def test_a5_margins(name):
    """A5 books (owner, 2026-10-31): bound, not punched, so at least 14.5 mm on the binding side (left of an
    odd page, right of an even one) and 7.5 mm on the outer side of the trimmed page; Expresta trims up to
    2.5 mm. The top and bottom keep 5 mm, onlinedruck.ch's safety distance (checked 2026-10-31: page
    numbers were at 4.8 mm)."""
    bad = []
    for n, left, right in margins(name, bleed=2.5):
        binding, outer = (left, right) if n % 2 else (right, left)
        if binding < 14.5 or outer < 7.5:
            bad.append(f"page {n}: binding {binding:.1f} mm, outer {outer:.1f} mm")
    for n, top, bottom in margins(name, vertical=True, bleed=2.5):
        if top < 5 or bottom < 5:
            bad.append(f"page {n}: top {top:.1f} mm, bottom {bottom:.1f} mm")
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


@pytest.mark.parametrize("name", PDFS_A5)
def test_a5_page_count_multiple_of_4(name):
    """A bound book is made of folded sheets of four pages, so an A5 book's page count is a multiple of 4
    (Expresta, 2026-10-31: "The number of content pages must be a multiple of number 4"; blank pages are
    added at the end). Three of the four were odd when first checked."""
    import pypdf
    from conftest import ROOT
    if not (ROOT / name).exists():
        pytest.skip(f"{name} not built")
    n = len(pypdf.PdfReader(ROOT / name).pages)
    assert n % 4 == 0, f"{name}: {n} pages, not a multiple of 4"


@pytest.mark.parametrize("name", PDFS)
def test_a5_has_the_same_text(name):
    """The A5 book is the binder version laid out with other margins and scaled down (owner, 2026-10-31:
    the same layout, smaller), from the same book model. Since the text area is a little narrower, check
    that no text was cut off or lost: after the cover (A4) and the title page and its back (A5), each holds
    exactly the same characters (spaces, digits and hyphens aside, as line breaks and page numbers move;
    NFKC, as Ghostscript keeps the ligature ﬀ as one character)."""
    import unicodedata
    from collections import Counter
    a5 = name.replace(".pdf", "_a5_book.pdf")

    def chars(pages):
        text = unicodedata.normalize("NFKC", "".join(pages))
        return Counter(c for c in text if not c.isspace() and not c.isdigit() and c != "-")
    a, b = chars(pdf_pages(name)[1:]), chars(pdf_pages(a5)[2:])
    report([f"only in {name}: {dict((a - b).most_common(10))}", f"only in {a5}: {dict((b - a).most_common(10))}"]
           if a != b else [], f"text differs between {name} and {a5}")


COVERS = [(name, shop) for name in PDFS for shop in ("expresta", "onlinedruck")]


@pytest.mark.parametrize("name,shop", COVERS)
def test_a5_book_cover(name, shop):
    """The A5 book's cover for each print shop (owner, 2026-10-31): one sheet with back, spine and front,
    each A5 panel with 2.5 mm of bleed outside, the spine as wide as the shop's rule gives for the book's
    page count, CMYK PDF/X-3 for coated card (FOGRA51, profile embedded), fonts embedded. The marker
    explanations are on the back, not on the front; the edition is on the front."""
    import subprocess
    import pypdf
    import step5_build_pdfs as step5
    from conftest import ROOT
    cover = name.replace(".pdf", f"_a5_book_cover_{shop}.pdf")
    if not (ROOT / cover).exists():
        pytest.skip(f"{cover} not built")
    reader = pypdf.PdfReader(ROOT / cover)
    pages = len(pypdf.PdfReader(ROOT / name.replace(".pdf", "_a5_book.pdf")).pages)
    spine = round(step5.SHOPS[shop](pages), 1)
    mm = 25.4 / 72
    page = reader.pages[0]
    media = [round(float(v) * mm, 1) for v in page.mediabox]
    trim = [round(float(v) * mm, 1) for v in page.trimbox]
    bad = []
    if len(reader.pages) != 1:
        bad.append(f"{len(reader.pages)} pages")
    if media != [0, 0, round(296 + spine + 5, 1), 215] or trim != [2.5, 2.5, round(298.5 + spine, 1), 212.5]:
        bad.append(f"MediaBox {media}, TrimBox {trim} mm, spine should be {spine} mm")
    if reader.metadata.get("/GTS_PDFXVersion") != "PDF/X-3:2002":
        bad.append("not marked PDF/X-3")
    intent = reader.trailer["/Root"]["/OutputIntents"][0].get_object()
    if intent["/OutputConditionIdentifier"] != "FOGRA51" or "/DestOutputProfile" not in intent:
        bad.append(f"output intent {intent}")
    fonts = subprocess.run(["pdffonts", str(ROOT / cover)], capture_output=True, text=True, check=True).stdout
    bad += [f"font not embedded: {line}" for line in fonts.splitlines()[2:] if line.split()[-5] != "yes"]
    # where the words are: back panel left of the spine, front panel right of it
    box = subprocess.run(["pdftotext", "-bbox", str(ROOT / cover), "-"], capture_output=True, text=True, check=True).stdout
    words = [(float(x) * mm, w) for x, w in re.findall(r'xMin="([\d.]+)"[^>]*>([^<]*)<', box)]
    back = " ".join(w for x, w in words if x < 150.5)
    front = " ".join(w for x, w in words if x > 150.5 + spine)
    template = (ROOT / "pipeline" / "templates" / f"cover_{name.split('-')[1].removesuffix('.pdf')}.html").read_text()
    legend = " ".join(re.sub(r"<[^>]+>", "", step5.LEGEND.search(template).group(1)).split()[:6])
    if legend not in back:
        bad.append(f"marker explanations ({legend} …) not on the back")
    if legend in front:
        bad.append("marker explanations still on the front")
    if not re.search(r"Edizi[oó]n \d{12}", front):
        bad.append("no edition on the front")
    report(bad, f"{cover} not as the print shop wants it")


def test_no_flagged_count_on_dictionary_cover():
    """The dictionary cover no longer says how many entries are a bit ⚠ (owner, 2026-10-31: drop the joke)."""
    cover = " ".join(pdf_pages("Dictionary/arogno-dictionary.pdf")[0].split())
    assert "a bit" not in cover, "the dictionary cover still has the ⚠ count"


def test_no_inferred_forms_joke_on_verbs_cover():
    """The verbs cover no longer has the "now with … forms nobody actually taught us" badge (owner,
    2026-10-31: drop the joke)."""
    cover = " ".join(pdf_pages("Verbs/arogno-verbs.pdf")[0].split())
    assert "NOBODY" not in cover.upper(), "the verbs cover still has the badge"
