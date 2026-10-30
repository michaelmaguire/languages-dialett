"""The four PDFs."""
import re

import pytest

from conftest import PDFS, pdf_pages, report

SECTIONS = ["Dialett → Italiano · English", "Italiano → Dialett · English", "English → Dialett · Italiano"]


@pytest.mark.parametrize("name", PDFS)
def test_cover_has_edition(name):
    """Every cover shows the edition YYYYMMDDhhmm (decided 2026-10-14)."""
    assert re.search(r"Edizi[oó]n\s+\d{12}\b", pdf_pages(name)[0]), f"{name}: no edition stamp on the cover"


@pytest.mark.parametrize("name", PDFS)
def test_no_placeholders_left(name):
    """No {{…}} placeholder is left unfilled (page numbers, edition, counts)."""
    bad = [f"page {i}: {m}" for i, p in enumerate(pdf_pages(name), 1) for m in re.findall(r"\{\{[^}]*\}\}", p)]
    report(bad, f"unfilled placeholders in {name}")


def section_pages():
    """Page number where each section of the dictionary PDF starts (its title on the page after the contents)."""
    pages = pdf_pages("Dictionary/arogno-dictionary.pdf")
    out = {}
    for title in SECTIONS:
        hits = [i for i, p in enumerate(pages, 1) if any(line.strip() == title for line in p.splitlines())]
        out[title] = hits[-1] if hits else None
    return out


def test_dictionary_sections_start_on_odd_pages():
    """Each language section starts on a right-hand (odd) page: the sections are filed separately in a
    binder (owner, 2026-10-19)."""
    bad = [f"{t}: page {n}" for t, n in section_pages().items() if n is None or n % 2 == 0]
    report(bad, "dictionary sections not starting on an odd page")


def test_dictionary_contents_page_numbers():
    """The contents page gives the page each section really starts on."""
    pages = pdf_pages("Dictionary/arogno-dictionary.pdf")
    contents = next((p for p in pages[:4] if "Contents" in p), "")
    bad = []
    for title, n in section_pages().items():
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
