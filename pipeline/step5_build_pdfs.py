#!/usr/bin/env python3
"""Step 5: print-ready PDFs of the verb charts, the dictionary and the expressions, from the CLDF dataset.

Reads  cache/dictionary_model.json, expressions_model.json, verbs_model.json and grammar_model.json (saved
       by step 4) with templates/dictionary.html.j2, expressions.html.j2, verbs.html.j2 and grammar.html.j2,
       templates/cover_verbs.html, cover_dictionary.html and cover_expressions.html (title pages; {{verbs}},
       {{inferred}}, {{words}}, {{flagged}}, {{sayings}}, {{phrases}}, {{topics}} and {{edition}}
       are filled in at build time), ../ATTRIBUTIONS.md (printed straight after each cover)
Writes ../Verbs/arogno-verbs.pdf         cover, contents, attributions, one verb per A4 sheet
       ../Dictionary/arogno-dictionary.pdf  cover, contents, attributions, the three look-up directions
       ../Expressions/arogno-expressions.pdf  cover, contents, attributions, expressions by topic
       ../Grammar/arogno-grammar.pdf          cover, contents, attributions, the grammar's chapters
       and next to each an A5 book version, *_a5.pdf, and its colour cover alone, *_a5_cover.pdf
       (see print_book())
Uses Chrome or Chromium in headless mode to print; skipped with a message if neither is installed.
Each PDF is printed twice: the contents page holds {{page:ID}} placeholders, and the page numbers come
from where the first print put the elements those IDs link to (read back with pypdf).
"""
import datetime, html, re, shutil, subprocess, sys

import step4_build_pages as build

from paths import PIPELINE as HERE, TEMPLATES
OUT = build.ROOT / "Verbs" / "arogno-verbs.pdf"
PAGE = HERE / "cache" / "print_verbs.html"

CSS = """
@page { size: A4; margin: 14mm 15mm 12mm 15mm; }
/* printed double-sided and punched for a binder (owner, 2026-10-30): 6 mm more on the binding side (the left
   of a right-hand page, the right of a left-hand one), 6 mm less on the outer side, so the text keeps its width */
@page :right { margin-left: 21mm; margin-right: 9mm; }
@page :left { margin-left: 9mm; margin-right: 21mm; }
* { box-sizing: border-box; }
body { font: 9.6pt/1.25 "DejaVu Serif", Georgia, serif; color: #111; margin: 0; }
section { page-break-after: always; height: 268mm; position: relative; overflow: hidden; }
h1 { font-size: 24pt; margin: 0 0 1mm; font-weight: bold; }
h1 sup, th sup { font-size: 60%; font-weight: normal; }
.sub { font-size: 11.5pt; margin: 0 0 1.5mm; }
.sub i { color: #444; }
.meta { font-size: 9.5pt; color: #333; margin: 0 0 4mm; padding-bottom: 3mm; border-bottom: 1.2pt solid #111; }
.meta b { font-weight: bold; color: #111; }
section.noted td { padding-top: .3mm; padding-bottom: .3mm; }   /* room for the note on a full A4 sheet */
.vnote { font-size: 8pt; color: #333; margin: -2mm 0 3mm; display: grid; grid-template-columns: 1fr 1fr; column-gap: 5mm; }
.nw { white-space: nowrap; }
.vnote span:last-child { font-style: italic; }
h2 { font: bold 9pt "DejaVu Sans", Arial, sans-serif; letter-spacing: .08em; text-transform: uppercase;
     margin: 3mm 0 1mm; color: #111; }
table { border-collapse: collapse; width: 100%; margin: 0 0 2mm; table-layout: fixed; }
th { font: bold 8.5pt "DejaVu Sans", Arial, sans-serif; text-align: left; padding: 1mm 2mm 1mm 0;
     border-bottom: .6pt solid #111; }
td { padding: .55mm 2mm .55mm 0; vertical-align: top; border-bottom: .3pt solid #bbb; overflow-wrap: anywhere; }
td.p, th.p { width: 17mm; color: #555; font-style: italic; }
.foot { position: absolute; bottom: 0; left: 0; right: 0; font-size: 8pt; color: #555;
        display: flex; justify-content: space-between; border-top: .3pt solid #bbb; padding-top: 1.5mm; }
.index h1 { font-size: 20pt; margin-bottom: 2mm; }
.index p { font-size: 9.5pt; margin: 0 0 4mm; }
.cols { column-count: 3; column-gap: 8mm; font-size: 9.5pt; }
.cols a { break-inside: avoid; display: flex; justify-content: space-between; border-bottom: .3pt dotted #999;
          padding: .7mm 0; color: inherit; text-decoration: none; }
.cols span.it { color: #555; font-style: italic; }
"""

esc = html.escape


def find_browser():
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        path = shutil.which(name)
        if path:
            return path
    return None


def main():
    verbs()
    dictionary()
    expressions()
    grammar_pdf()


def verbs():
    """Verbs/arogno-verbs.pdf: one verb per A4 sheet, from the verbs model that step 4 saved (verbs_model.py),
    through templates/verbs.html.j2."""
    import verbs_model
    book = verbs_model.load()
    if not book:
        return
    body = templates().get_template("verbs.html.j2").render(verbs=book["verbs"], credits=credits_pages("verbs"))
    # the title page is its own file so it can be edited without touching this script
    cover = stamp((TEMPLATES / "cover_verbs.html").read_text()).replace("{{verbs}}", str(len(book["verbs"]))) \
                                             .replace("{{inferred}}", f"{book['inferred']:,}")
    head = (f'<!doctype html><meta charset="utf-8"><title>Verbi – dialett da Rögn</title>'
            f"<style>{CSS}{TOC_CSS}</style>")
    front = ("Foreign Language Guides", f"{len(book['verbs'])} Rögn Verbs", "dialett ticinés · fully conjugated")
    print_book(OUT, PAGE, head, cover, body, front,
               f"cover, contents, attributions + {len(book['verbs'])} verb sheets")


CREDITS_CSS = """
.credits { page-break-before: always; page-break-after: always; font: 9pt/1.4 "DejaVu Serif", Georgia, serif; color: #111; }
.credits h1 { font: bold 20pt "DejaVu Sans", Arial, sans-serif; margin: 0 0 3mm; padding-bottom: 2mm;
              border-bottom: 1.2pt solid #111; }
.credits h2 { font: bold 9.5pt "DejaVu Sans", Arial, sans-serif; letter-spacing: .08em; text-transform: uppercase;
              margin: 5mm 0 1.5mm; color: #111; break-after: avoid; }
.credits p { margin: 0 0 2mm; }
.credits ul { margin: 0 0 2mm; padding-left: 5mm; }
.credits li { margin-bottom: .8mm; }
.credits table { border-collapse: collapse; width: 100%; margin: 0 0 3mm; table-layout: auto; }
.credits th { font: bold 8pt "DejaVu Sans", Arial, sans-serif; text-align: left; padding: .8mm 2mm .8mm 0;
              border-bottom: .6pt solid #111; }
.credits td { padding: .7mm 2mm .7mm 0; vertical-align: top; border-bottom: .3pt solid #bbb; }
.credits tr { break-inside: avoid; }
.credits a { color: inherit; text-decoration: none; }
.credits code { font: 8pt "DejaVu Sans Mono", monospace; }
"""


BOOKS = {"dictionary", "expressions", "verbs", "grammar"}
BOOKS_TAG = re.compile(r"^<!--\s*books:\s*([^>]*?)\s*-->$")


def credits_pages(book):
    """ATTRIBUTIONS.md as HTML, so the printed credits always match the page on GitHub, with only what
    concerns this book (owner, 2026-10-30): a line <!-- books: grammar, verbs --> before a ## heading limits
    that section, before a "- " item that item, to the books it names. Untagged text is printed in all four."""
    assert book in BOOKS, book
    path = build.ROOT / "ATTRIBUTIONS.md"
    if not path.exists():
        return ""

    def inline(text):
        text = esc(text)
        text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)             # links into the repo: text only
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)\*(?!\w)", r"<i>\1</i>", text)
        return re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

    out, para, items, rows = [], [], [], []

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
        if items:
            shown = [text for text, keep in items if keep]
            if shown:
                out.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in shown) + "</ul>")
        if rows:
            head, body = rows[0], rows[2:]
            cells = lambda r, tag: "".join(f"<{tag}>{inline(c.strip())}</{tag}>" for c in r.strip().strip("|").split("|"))
            out.append("<table><tr>" + cells(head, "th") + "</tr>"
                       + "".join(f"<tr>{cells(r, 'td')}</tr>" for r in body) + "</table>")
        para.clear(); items.clear(); rows.clear()

    def books(tag):
        named = {b.strip() for b in tag.split(",") if b.strip()}
        unknown = named - BOOKS
        if unknown:
            raise SystemExit(f"ATTRIBUTIONS.md: unknown book in <!-- books: {tag} -->: {', '.join(sorted(unknown))}")
        return named

    pending, skip_section, editors_note = None, False, False
    for line in path.read_text().splitlines():
        tag = BOOKS_TAG.match(line.strip())
        if tag:
            pending = books(tag.group(1))
            continue
        if line.startswith("This page is written by hand"):       # a note for editors of the file, not for print
            editors_note = True
        if editors_note:
            editors_note = bool(line.strip())
            continue
        if line.startswith("#"):
            flush()
            level = len(line) - len(line.lstrip("#"))
            if level <= 2:                                          # a new section: printed unless tagged otherwise
                skip_section = pending is not None and book not in pending
                pending = None
            if not skip_section:
                out.append(f"<h{min(level, 2)}>{inline(line.lstrip('# '))}</h{min(level, 2)}>")
            continue
        if skip_section:
            continue
        if not line.strip():
            flush()
        elif line.startswith("|"):
            if para or items:
                flush()
            rows.append(line)
        elif line.startswith("- "):
            if para or rows:
                flush()
            items.append([line[2:], pending is None or book in pending])
            pending = None
        elif items and line.startswith("  "):
            items[-1][0] += " " + line.strip()
        else:
            para.append(line.strip())
    flush()
    return f'<style>{CREDITS_CSS}</style><div class="credits" id="attributions">{"".join(out)}</div>'


# one edition stamp per run, shared by all the PDFs: year, month, day, hour, minute (e.g. 202610141046)
EDITION = datetime.datetime.now().strftime("%Y%m%d%H%M")


def stamp(cover):
    """Fill {{edition}} in a cover. A cover without the placeholder still gets the edition, in a
    small label at the top right, so every PDF carries one on its first page."""
    if "{{edition}}" in cover:
        return cover.replace("{{edition}}", EDITION)
    line = (f'<div style="position:absolute;right:16mm;top:4mm;font:9pt \'DejaVu Sans\',Arial,'
            f'sans-serif;color:#000;background:#fff;padding:1mm 2mm">Edizión {EDITION}</div>')
    return cover.replace("</section>", line + "</section>", 1)


TOC_CSS = """
a.toc, .toc a { display: flex; justify-content: space-between; color: inherit; text-decoration: none;
                border-bottom: .3pt dotted #999; padding: .8mm 0; font-size: 11pt; }
a.toc span:first-child, .toc a.head span:first-child { font-weight: bold; }
.toc p.letters { margin: 1mm 0 4mm; font-size: 9.5pt; line-height: 1.6; }
.toc p.letters a { display: inline; border: 0; padding: 0; font-size: inherit; white-space: nowrap; }
.toc p.letters b { font-family: "DejaVu Sans", Arial, sans-serif; }
"""
PLACEHOLDER = re.compile(r"\{\{page:([\w-]+)\}\}")


def print_pdf(out, page):
    browser = find_browser()
    if not browser:
        print(f"{out.name}: skipped (needs Chrome or Chromium); the page to print is {page}")
        return False
    subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={out}", page.as_uri()], check=True, capture_output=True, timeout=300)
    return True


RECTO = re.compile(r"\{\{recto:([\w-]+)\}\}")
BLANK_PAGE = '<div style="page-break-before: always; height: 1px"></div>'


def print_with_contents(out, page, document, message):
    """Print document; {{page:ID}} becomes the number of the page holding the element with that id.
    The first print uses a stand-in; then the real numbers are read from the PDF's link targets.
    {{recto:ID}}, put just before an element that starts a new page (and is linked from the contents),
    makes it start on an odd, right-hand page: a blank page is inserted before it when it would fall on an
    even one, so that the sections can be filed separately in a binder (owner, 2026-10-19). Chrome ignores
    the CSS for this (page-break-before: right), so the page is measured and the print repeated."""
    import pypdf
    ids = set(PLACEHOLDER.findall(document))
    rectos = list(dict.fromkeys(RECTO.findall(document)))
    numbers = dict.fromkeys(ids, "000")
    padded = set()
    for _ in range(3 + 2 * len(rectos)):      # normally two prints: the second confirms the numbers
        text = RECTO.sub(lambda m, padded=padded: BLANK_PAGE if m.group(1) in padded else "", document)
        page.write_text(PLACEHOLDER.sub(lambda m, numbers=numbers: numbers[m.group(1)], text))
        if not print_pdf(out, page):
            return False
        reader = pypdf.PdfReader(out)
        found = {name.lstrip("/"): reader.get_destination_page_number(d) + 1
                 for name, d in reader.named_destinations.items()}
        # fix the first section that starts on an even page; the later ones move with it, so one at a time
        even = [r for r in rectos if found.get(r, 1) % 2 == 0]
        if even:
            padded ^= {even[0]}
            continue
        new = {i: str(found.get(i, "?")) for i in ids}
        if new == numbers:
            break
        numbers = new
    unplaced = [r for r in rectos if r not in found]
    if unplaced:
        print(f"{out.name}: cannot check the page of {', '.join(unplaced)} (not linked from the contents?)")
    missing = sorted(i for i in ids if numbers[i] == "?")
    if missing:
        print(f"{out.name}: no page found for {', '.join(missing[:5])}")
    print(f"{message}, {len(reader.pages)} pages -> {out}")
    return True


# The A5 books (owner, 2026-10-31), to be printed and glue-bound by Expresta (expresta.eu) inside a separate
# cover: each book is laid out at A4 exactly as the binder version and the finished PDF is scaled down to
# A5 (148/210 = x 0.705), so the pages look the same, only smaller. Bound rather than punched, so the margins
# change: 15 mm on the binding side and 8 mm on the outer side once scaled (Expresta keeps 2.5 mm from the
# trim clear; their own template has 18 and 10). The cover is replaced by a title page and its back
# (templates/title_page.html), so the contents still start on page 2 or later and the parity is unchanged.
A5 = (148, 210)                                  # mm
A5_SCALE = A5[0] / 210
BOOK_INNER, BOOK_OUTER = 15, 8                   # mm on the A5 page
BOOK_CSS = f"""
@page :right {{ margin-left: {BOOK_INNER / A5_SCALE:.2f}mm; margin-right: {BOOK_OUTER / A5_SCALE:.2f}mm; }}
@page :left {{ margin-left: {BOOK_OUTER / A5_SCALE:.2f}mm; margin-right: {BOOK_INNER / A5_SCALE:.2f}mm; }}
"""


def print_book(out, page, head, cover, body, front, message):
    """Print one book twice: out (A4, for the binder, behind its cover) and out_a5.pdf (the A5 book, behind
    a title page). front = (series, title, subtitle) for the title page. The colour cover, page 1 of the
    A4 PDF, also goes alone into out_a5_cover.pdf, scaled to A5 (owner, 2026-10-31)."""
    if print_with_contents(out, page, head + cover + body, f"{out.name}: {message}"):
        scale_to_a5(out.with_name(out.stem + "_a5_cover.pdf"), source=out, pages=1)
    a5 = out.with_name(out.stem + "_a5.pdf")
    series, title, subtitle = front
    title_page = (stamp((TEMPLATES / "title_page.html").read_text()).replace("{{series}}", series)
                  .replace("{{title}}", title).replace("{{subtitle}}", subtitle))
    if print_with_contents(a5, page.with_name(page.stem + "_a5.html"),
                           head + f"<style>{BOOK_CSS}</style>" + title_page + body,
                           f"{a5.name}: title page, contents, attributions + the same pages, at A4"):
        scale_to_a5(a5)


def scale_to_a5(path, source=None, pages=None):
    """Shrink every page of an A4 PDF to A5, content, links and all, centred (A4 is a shade taller than A5
    in proportion, so 0.3 mm is left above and below). With source, the first pages of that PDF are
    scaled and saved as path instead."""
    import pypdf
    from pypdf.generic import ArrayObject, FloatObject, RectangleObject
    pt = 72 / 25.4
    w, h = A5[0] * pt, A5[1] * pt
    if source:
        writer = pypdf.PdfWriter()
        writer.append(source, pages=(0, pages))
    else:
        writer = pypdf.PdfWriter(clone_from=path)
    for page in writer.pages:
        k = w / float(page.mediabox.width)
        dy = (h - float(page.mediabox.height) * k) / 2
        page.add_transformation(pypdf.Transformation().scale(k, k).translate(0, dy))
        for a in page.get("/Annots") or []:
            r = a.get_object().get("/Rect")
            if isinstance(r, ArrayObject):
                for i, v in enumerate(r):
                    r[i] = FloatObject(float(v) * k + (dy if i % 2 else 0))
        box = RectangleObject((0, 0, w, h))
        page.mediabox = page.cropbox = page.trimbox = page.bleedbox = page.artbox = box
    writer.write(path)
    print(f"{path.name}: scaled to A5, {len(writer.pages)} pages")


DICT_CSS = """
@page { size: A4; margin: 15mm 14mm 16mm 14mm; @bottom-center { content: counter(page); font: 8pt "DejaVu Sans", Arial, sans-serif; color: #555; } }
/* the binding side, as for the verbs (owner, 2026-10-30): the text keeps its width, shifted 6 mm outwards */
@page :right { margin-left: 20mm; margin-right: 8mm; }
@page :left { margin-left: 8mm; margin-right: 20mm; }
body { font: 9pt/1.32 "DejaVu Serif", Georgia, serif; color: #111; margin: 0; }
.part { page-break-before: always; }
.toc { page-break-before: always; }
.toc h1 { font: bold 20pt "DejaVu Sans", Arial, sans-serif; margin: 0 0 4mm; padding-bottom: 2mm; border-bottom: 1.2pt solid #111; }
.part h1 { font: bold 20pt "DejaVu Sans", Arial, sans-serif; margin: 0 0 1mm; column-span: all; }
.part > p { font-size: 9pt; color: #444; margin: 0 0 5mm; padding-bottom: 3mm; border-bottom: 1.2pt solid #111; }
.entries { column-count: 2; column-gap: 9mm; column-rule: .3pt solid #bbb; }
h2 { font: bold 15pt "DejaVu Sans", Arial, sans-serif; margin: 3mm 0 1.5mm; break-after: avoid; color: #0b2a5b; }
.e { margin: 0 0 1.1mm; padding-left: 4mm; text-indent: -4mm; break-inside: avoid; }
.e b { font-weight: bold; }
.e i { color: #333; }
.e .r { font: 7pt "DejaVu Sans", Arial, sans-serif; color: #666; text-transform: uppercase; letter-spacing: .04em; }
.e .n { color: #555; font-size: 8pt; }
.e .g { font-style: normal; font-size: 8pt; color: #666; }   /* the label: upright and grey, unlike the italic translations */
/* a link to a verb's page online (owner, 2026-10-30): clickable on screen, and looking exactly like the text
   around it, so a printed copy shows no trace of it (a PDF link itself is never printed) */
a.web { color: inherit; text-decoration: none; }
"""


VERBS_URL = f"{build.REPO_URL}/blob/main/Verbs/"


def templates():
    """The Jinja2 templates of the PDFs (templates/*.html.j2). Delimiters [[ ]], [% %] and [# #], so the
    {{page:ID}} and {{recto:ID}} placeholders of the two-pass print (print_with_contents) stay literal."""
    import jinja2
    from urllib.parse import quote
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATES), autoescape=False,
                             variable_start_string="[[", variable_end_string="]]",
                             block_start_string="[%", block_end_string="%]",
                             comment_start_string="[#", comment_end_string="#]")
    # a verb's page online, for the links of a PDF read on screen (styled as plain text: see a.web in DICT_CSS)
    env.filters["page_url"] = lambda file: VERBS_URL + quote(file)
    return env


def dictionary():
    """Dictionary/arogno-dictionary.pdf: the three look-up directions, two columns to the page, from the
    dictionary model that step 4 saved (dictionary_model.py), through templates/dictionary.html.j2."""
    import dictionary_model
    book = dictionary_model.load()
    if not book:
        return
    cols = {"dialect": ("italian", "english"), "italian": ("dialect", "english"), "english": ("dialect", "italian")}
    for n, part in enumerate(book["parts"], 1):
        part["cols"] = cols[part["head"]]
        # the letters that have an entry to print, each with its anchor for the contents page
        part["printed"] = [dict(s, anchor=f"p{n}-{s['letter'] if s['letter'].isalpha() else 'other'}")
                           for s in part["sections"] if any(not e["no_word"] for e in s["entries"])]
    body = templates().get_template("dictionary.html.j2").render(parts=book["parts"], credits=credits_pages("dictionary"))
    cover = stamp((TEMPLATES / "cover_dictionary.html").read_text()).replace("{{words}}", str(book["words"])) \
        .replace("{{flagged}}", str(book["flagged"]))
    page = HERE / "cache" / "print_dictionary.html"
    head = (f'<!doctype html><meta charset="utf-8"><title>Dizionari – dialett da Rögn</title>'
            f"<style>{DICT_CSS}{TOC_CSS}</style>")
    print_book(build.ROOT / "Dictionary" / "arogno-dictionary.pdf", page, head, cover, body,
               ("Pocket Dictionary", "Rögn<br>Dizionari", "Dialett · Italiano · English"),
               f"cover, contents, attributions + {book['words']} words three ways")


EXPR_CSS = """
.topic h1 { color: #0f5c4d; font-size: 17pt; margin-bottom: 3mm; padding-bottom: 2mm; border-bottom: 1.2pt solid #0f5c4d; }
h3 { font: bold 8.5pt "DejaVu Sans", Arial, sans-serif; letter-spacing: .08em; text-transform: uppercase; color: #555;
     margin: 2.5mm 0 1.5mm; break-after: avoid; column-span: all; }
.x { margin: 0 0 1.3mm; break-inside: avoid; }
.x b { font-weight: bold; }
.x i { color: #333; }
.x .en { color: #555; }
.x .r { font: 7pt "DejaVu Sans", Arial, sans-serif; color: #666; text-transform: uppercase; letter-spacing: .04em; }
"""


def expressions():
    """Expressions/arogno-expressions.pdf: the sayings and phrases by topic, two columns to the page, from the
    expressions model that step 4 saved (expressions_model.py), through templates/expressions.html.j2. The
    lines of texts (genre `text`) are not printed."""
    import expressions_model
    book = expressions_model.load()
    if not book or not book["topics"]:
        return
    body = templates().get_template("expressions.html.j2").render(topics=book["topics"], credits=credits_pages("expressions"))
    cover = stamp((TEMPLATES / "cover_expressions.html").read_text())
    for k, v in (("sayings", book["sayings"]), ("phrases", book["phrases"]), ("topics", len(book["topics"]))):
        cover = cover.replace("{{" + k + "}}", str(v))
    page = HERE / "cache" / "print_expressions.html"
    head = (f'<!doctype html><meta charset="utf-8"><title>Modi da dì – dialett da Rögn</title>'
            f"<style>{DICT_CSS}{TOC_CSS}{EXPR_CSS}</style>")
    print_book(build.ROOT / "Expressions" / "arogno-expressions.pdf", page, head, cover, body,
               ("Phrasebook", "Rögn<br>Modi da dì", "Dialett · Italiano · English"),
               f"cover, contents, attributions + {book['sayings'] + book['phrases']} "
               f"expressions in {len(book['topics'])} topics")


GRAMMAR_CSS = """
.chapter h1 { font: bold 18pt/1.15 "DejaVu Sans", Arial, sans-serif; margin: 0 0 4mm; padding-bottom: 2mm;
              border-bottom: 1.2pt solid #111; }
.chapter h1 .num { display: inline-block; min-width: 11mm; color: #7a1f5c; }
.chapter h1 .en { display: block; font: italic 12pt "DejaVu Serif", Georgia, serif; color: #444; margin: 1mm 0 0 11mm; }
.chapter h2 { font: bold 10.5pt "DejaVu Sans", Arial, sans-serif; margin: 5mm 0 2mm; color: #7a1f5c;
              break-after: avoid; }
.chapter h2 .en { font: italic 10pt "DejaVu Serif", Georgia, serif; color: #555; }
.pairs { display: grid; grid-template-columns: 1fr 1fr; column-gap: 7mm; row-gap: 2mm; margin: 0 0 3mm; }
.pairs .it, .pairs .en { font-size: 9.6pt; line-height: 1.38; break-inside: avoid; }
.pairs .en { color: #1d3d5c; border-left: .4pt solid #bbb; padding-left: 4mm; margin-left: -3.5mm; }
.ex { display: flex; gap: 3mm; margin: 2mm 0 3mm 4mm; break-inside: avoid; }
.ex .n { font: 9pt "DejaVu Sans", Arial, sans-serif; color: #7a1f5c; min-width: 8mm; }
.ex .pt { font-weight: bold; font-size: 10pt; }
.igt { display: flex; flex-wrap: wrap; gap: 0 3mm; margin: .8mm 0; }
.igt .w { display: inline-flex; flex-direction: column; }
.igt .w span:first-child { font-style: italic; }
.igt .g { font: 7.6pt "DejaVu Sans", Arial, sans-serif; color: #444; }
.ex .tr { font-size: 9.2pt; }
.ex .ten { color: #1d3d5c; }
.ex .src { font: 7.6pt "DejaVu Sans", Arial, sans-serif; color: #777; margin-left: 3mm; }
.ex .note { font-size: 8.5pt; color: #555; font-style: italic; margin-top: .5mm; }
table.vt, table.dt { width: auto; min-width: 50%; margin: 2mm 0 4mm 4mm; table-layout: auto; break-inside: avoid; }
table.vt caption { text-align: left; font-size: 9.5pt; padding-bottom: 1mm; }
table.vt td, table.vt th, table.dt td, table.dt th { padding: .5mm 5mm .5mm 0; font-size: 9.2pt; }
table.vt th, table.dt th { font: bold 8.2pt "DejaVu Sans", Arial, sans-serif; }
table.vt td.p { color: #555; font-style: italic; width: 16mm; }
table.vt sup { font-size: 70%; }
.gtoc a { display: flex; justify-content: space-between; color: inherit; text-decoration: none;
          border-bottom: .3pt dotted #999; padding: 1.2mm 0; font-size: 11pt; }
.gtoc a span.en { color: #555; font-style: italic; font-size: 10pt; }
.gintro { font-size: 10pt; line-height: 1.45; margin-top: 6mm; }
"""


def grammar_pdf():
    """Grammar/arogno-grammar.pdf: the chapters, Italian and English in two columns, examples and tables in
    dialect, from the grammar model that step 4 saved (grammar_model.py), through templates/grammar.html.j2."""
    import grammar
    import grammar_model
    book = grammar_model.load()
    if not book:
        return
    env = templates()
    # the chapters' Markdown (*word*, **bold**) as HTML, verb links leading to the verb's page online
    env.filters["inline"] = lambda text: grammar.html_inline(text, book["verb_files"], VERBS_URL)
    body = env.get_template("grammar.html.j2").render(chapters=book["chapters"], credits=credits_pages("grammar"))
    cover = stamp((TEMPLATES / "cover_grammar.html").read_text())
    for k, v in (("chapters", len(book["chapters"])), ("examples", book["examples"])):
        cover = cover.replace("{{" + k + "}}", str(v))
    page = HERE / "cache" / "print_grammar.html"
    head = (f'<!doctype html><meta charset="utf-8"><title>Gramatica – dialett da Rögn</title>'
            f"<style>{DICT_CSS}{TOC_CSS}{GRAMMAR_CSS}</style>")
    print_book(build.ROOT / "Grammar" / "arogno-grammar.pdf", page, head, cover, body,
               ("Grammatica · Grammar", "Rögn<br>Grammatica<br>Grammar", "Italiano · English"),
               f"cover, contents, attributions + {len(book['chapters'])} chapters, {book['examples']} examples")


if __name__ == "__main__":
    sys.exit(main())
