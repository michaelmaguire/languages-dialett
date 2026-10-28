#!/usr/bin/env python3
"""Step 5: print-ready PDFs of the verb charts, the dictionary and the expressions, from the CLDF dataset.

Reads  ../cldf (through lexicon.for_pages), data/dictionary.csv (written by step 4),
       templates/cover_verbs.html, cover_dictionary.html and cover_expressions.html (title pages; {{verbs}},
       {{inferred}}, {{words}}, {{flagged}}, {{sayings}}, {{phrases}}, {{topics}} and {{edition}}
       are filled in at build time), ../ATTRIBUTIONS.md (printed straight after each cover)
Writes ../Verbs/arogno-verbs.pdf         cover, contents, attributions, one verb per A4 sheet
       ../Dictionary/arogno-dictionary.pdf  cover, contents, attributions, the three look-up directions
       ../Expressions/arogno-expressions.pdf  cover, contents, attributions, expressions by topic
       ../Grammar/arogno-grammar.pdf          cover, contents, attributions, the grammar's chapters
Uses Chrome or Chromium in headless mode to print; skipped with a message if neither is installed.
Each PDF is printed twice: the contents page holds {{page:ID}} placeholders, and the page numbers come
from where the first print put the elements those IDs link to (read back with pypdf).
"""
import datetime, html, re, shutil, subprocess, sys
from pathlib import Path

import step4_build_pages as build
import feminine

from paths import PIPELINE as HERE, TEMPLATES
OUT = build.ROOT / "Verbs" / "arogno-verbs.pdf"
PAGE = HERE / "cache" / "print_verbs.html"
DAGGER = "†"

CSS = """
@page { size: A4; margin: 14mm 15mm 12mm 15mm; }
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

PERSONS = build.PERSONS
IMPERATIVE_PERSONS = [("2s", "ti"), ("1p", "nüm"), ("2p", "vialtri")]
esc = html.escape


def column(grid, tense):
    """(mark for the heading, cells): a column inferred throughout is marked once, in its heading."""
    cells = grid[tense]
    known = [c for c in cells.values() if c[0] != "–"]
    whole = bool(known) and all(inferred for _, inferred in known)
    mark = f"<sup>{DAGGER}</sup>" if whole else ""
    return mark, {s: esc(text) + ("" if whole or not inferred or text == "–" else f"<sup>{DAGGER}</sup>")
                  for s, (text, inferred) in cells.items()}


def tense_table(grid, tenses, persons):
    cols = [column(grid, t) for t in tenses]
    head = "".join(f"<th>{esc(t.capitalize())}{mark}</th>" for t, (mark, _) in zip(tenses, cols))
    rows = "".join(f'<tr><td class="p">{esc(label)}</td>' + "".join(f"<td>{cells[s]}</td>" for _, cells in cols) + "</tr>"
                   for s, label in persons)
    return f'<table><tr><th class="p"></th>{head}</tr>{rows}</table>'


def verb_sheet(name, e, eng, number):
    g = e["grid"]
    di = " / ".join(e["dialect"]) or name
    en = eng.get(build.key(name), "")
    mark = f"<sup>{DAGGER}</sup>" if e["basis"] == "inferred" else ""
    ger_mark, ger = column(g, "gerundio")
    pp_mark, pp = column(g, "participio passato")
    raw_pp = g["participio passato"]["-"][0]
    if raw_pp != "–":                                   # rubaa/rubada, on one line
        pp["-"] = pp["-"].replace(esc(raw_pp), f'<span class="nw">{esc(feminine.with_feminine(raw_pp))}</span>', 1)
    return "".join([
        f'<section id="v-{number}"{' class="noted"' if e.get("note") else ""}><h1>{esc(di)}{mark}</h1>',
        f'<p class="sub"><i>italiano</i> {esc(" / ".join([name] + e["aliases"]))}'
        + (f' &nbsp;·&nbsp; <i>English</i> to {esc(en)}' if en else "") + "</p>",
        f'<p class="meta"><b>Gerundio</b>{ger_mark} {ger["-"]} &nbsp;·&nbsp; <b>Participio passato</b>{pp_mark} {pp["-"]}'
        f' &nbsp;·&nbsp; {esc(e["class"].split(":")[0])}</p>',
        (f'<p class="vnote"><span>{esc(e["note"])}</span><span>{esc(e.get("note_en", ""))}</span></p>'
         if e.get("note") else ""),
        "<h2>Indicativo</h2>",
        tense_table(g, ["presente", "futuro", "futuro prossimo"], PERSONS),
        tense_table(g, ["imperfetto", "passato prossimo", "trapassato prossimo"], PERSONS),
        "<h2>Condizionale</h2>",
        tense_table(g, build.CONDITIONAL, PERSONS),
        "<h2>Congiuntivo</h2>",
        tense_table(g, build.SUBJUNCTIVE, PERSONS),
        "<h2>Imperativo</h2>",
        tense_table(g, ["imperativo", build.IMPERATIVE], IMPERATIVE_PERSONS),
        f'<div class="foot"><span></span><span>{{{{page:v-{number}}}}}</span></div></section>'])


def find_browser():
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        path = shutil.which(name)
        if path:
            return path
    return None


def main():
    import lexicon
    _, tables, eng = lexicon.for_pages()            # the verbs as the CLDF dataset has them
    order = sorted(tables, key=lambda n: build.plain(" ".join(tables[n]["dialect"]) or n))
    inferred = sum(c[1] for e in tables.values() for row in e["grid"].values() for c in row.values())

    index = "".join(f'<a href="#v-{i}"><span><b>{esc(tables[n]["dialect"][0] if tables[n]["dialect"] else n)}</b> '
                    f'<span class="it">{esc(n)}</span></span><span>{{{{page:v-{i}}}}}</span></a>'
                    for i, n in enumerate(order, 1))
    # the title page is its own file so it can be edited without touching this script
    cover = stamp((TEMPLATES / "cover_verbs.html").read_text()).replace("{{verbs}}", str(len(order))) \
                                             .replace("{{inferred}}", f"{inferred:,}")
    contents = (f'<section class="index"><h1>Contents</h1>'
                f'<a class="toc" href="#attributions"><span>Attributions and thanks</span>'
                f'<span>{{{{page:attributions}}}}</span></a>'
                f'<h2>Verbs</h2><p>{len(order)} verbs, one per page, in alphabetical order of the dialect infinitive. '
                f"{DAGGER} marks a form that is inferred from the patterns in the course material rather than "
                f'found in a document; in a column heading it applies to the whole column.</p>'
                f'<div class="cols">{index}</div></section>')
    sheets = [verb_sheet(n, tables[n], eng, i) for i, n in enumerate(order, 1)]
    document = (f'<!doctype html><meta charset="utf-8"><title>Verbi – dialett da Rögn</title>'
                f"<style>{CSS}{TOC_CSS}</style>{cover}{contents}{credits_pages()}{''.join(sheets)}")
    print_with_contents(OUT, PAGE, document,
                        f"arogno-verbs.pdf: cover, contents, attributions + {len(sheets)} verb sheets")
    dictionary()
    expressions()
    grammar_pdf()


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


def credits_pages():
    """ATTRIBUTIONS.md as HTML, so the printed credits always match the page on GitHub."""
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
            out.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>")
        if rows:
            head, body = rows[0], rows[2:]
            cells = lambda r, tag: "".join(f"<{tag}>{inline(c.strip())}</{tag}>" for c in r.strip().strip("|").split("|"))
            out.append("<table><tr>" + cells(head, "th") + "</tr>"
                       + "".join(f"<tr>{cells(r, 'td')}</tr>" for r in body) + "</table>")
        para.clear(); items.clear(); rows.clear()

    for line in path.read_text().splitlines():
        if line.startswith("This page is written by hand"):       # a note for editors of the file, not for print
            continue
        if not line.strip():
            flush()
        elif line.startswith("#"):
            flush()
            level = len(line) - len(line.lstrip("#"))
            out.append(f"<h{min(level, 2)}>{inline(line.lstrip('# '))}</h{min(level, 2)}>")
        elif line.startswith("|"):
            if para or items:
                flush()
            rows.append(line)
        elif line.startswith("- "):
            if para or rows:
                flush()
            items.append(line[2:])
        elif items and line.startswith("  "):
            items[-1] += " " + line.strip()
        elif "printed at the back of the" in line or re.match(r"(two|three|four) PDFs\.", line):
            continue
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
        text = RECTO.sub(lambda m: BLANK_PAGE if m.group(1) in padded else "", document)
        page.write_text(PLACEHOLDER.sub(lambda m: numbers[m.group(1)], text))
        if not print_pdf(out, page):
            return
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


DICT_CSS = """
@page { size: A4; margin: 15mm 14mm 16mm 14mm; @bottom-center { content: counter(page); font: 8pt "DejaVu Sans", Arial, sans-serif; color: #555; } }
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
.e .g { font-style: italic; color: #333; }
"""


def dictionary():
    """Dictionary/arogno-dictionary.pdf: the three look-up directions, two columns to the page."""
    words = build.read(build.DATA / "dictionary.csv")
    if not words:
        return

    for w in words:
        w["canonical"] = "yes" if w["region"] == "Rögn" else "no"
    lookup = build.lookup_words(words)          # from Italian or English, the Rögn word where there is one

    def entries(part, head, second, third, sort_key):
        groups = {}
        # an entry with no word in the look-up language ("[get out of]" for unknown Italian) is left out
        # in the dialect part a word written in several ways appears under each spelling (giô -> giò / giô / giõ)
        source = words + build.cross_references(words) if head == "dialect" else lookup
        for w in sorted((w for w in source if w[head] and not w[head].startswith("[")),
                        key=lambda w: build.plain(sort_key(w))):
            letter = (build.plain(sort_key(w)) or "#")[0].upper()
            groups.setdefault(letter if letter.isalpha() else "#", []).append(w)
        out = []
        for letter in sorted(groups):
            out.append(f'<h2 id="p{part}-{letter if letter.isalpha() else "other"}">{letter}</h2>')
            # one line per headword: the senses of a word (anca: anche, pure…) follow it, separated by ";"
            for rows in build.merge_same_head(groups[letter], head, (second, third), lambda w: w["region"]):
                senses = []
                for w in rows:
                    flag = " ⚠" if w["check"] else ""
                    label = build.word_label(w, "it" if head == "italian" else "en")
                    rest = " · ".join(esc(build.dialect_shown(w) if k == "dialect" else w[k])
                                      + ((f" {label}" if "(" in label else f" ({label})") if k == "dialect" and label else "")
                                      for k in (second, third) if w[k])
                    region = f' <span class="r">{esc(w["region"])}</span>' if w["region"] and w["region"] != "Rögn" else ""
                    note = f' <span class="n">({esc(w["note"])})</span>' if w["note"] and len(w["note"]) < 60 else ""
                    senses.append(f"<i>{rest}</i>{flag}{region}{note}")
                label = build.word_label(rows[0]) if head == "dialect" else ""
                label = f' <span class="g">{esc(label)}</span>' if label else ""
                shown = build.dialect_shown(rows[0]) if head == "dialect" else rows[0][head]
                out.append(f'<div class="e"><b>{esc(shown)}</b>{label} {"; ".join(senses)}</div>')
        return "".join(out), sorted(groups)

    strip_di = lambda w: build.DI_ARTICLE.sub("", build.key(w["dialect"]))
    parts = [("Dialett → Italiano · English", "dialect", "italian", "english", strip_di),
             ("Italiano → Dialett · English", "italian", "dialect", "english", lambda w: build.bare(w["italian"])),
             ("English → Dialett · Italiano", "english", "dialect", "italian",
              lambda w: build.EN_ARTICLE.sub("", w["english"]))]
    body, toc = [], ['<section class="toc"><h1>Contents</h1><a class="head" href="#attributions">'
                     '<span>Attributions and thanks</span><span>{{page:attributions}}</span></a><p class="letters"></p>']
    for n, (title, a, b, c, k) in enumerate(parts, 1):
        html_entries, letters = entries(n, a, b, c, k)
        body.append(f'{{{{recto:part-{n}}}}}<div class="part" id="part-{n}"><h1>{esc(title)}</h1><p></p>'
                    f'<div class="entries">{html_entries}</div></div>')
        anchors = [(l, f"p{n}-{l if l.isalpha() else 'other'}") for l in letters]
        toc.append(f'<a class="head" href="#part-{n}"><span>{esc(title)}</span><span>{{{{page:part-{n}}}}}</span></a>'
                   '<p class="letters">' + " &nbsp; ".join(f'<a href="#{i}"><b>{l}</b> {{{{page:{i}}}}}</a>'
                                                          for l, i in anchors) + "</p>")
    toc.append("</section>")
    cover = stamp((TEMPLATES / "cover_dictionary.html").read_text()).replace("{{words}}", str(len(words))) \
        .replace("{{flagged}}", str(sum(bool(w["check"]) for w in words)))
    page = HERE / "cache" / "print_dictionary.html"
    document = (f'<!doctype html><meta charset="utf-8"><title>Dizionari – dialett da Rögn</title>'
                f"<style>{DICT_CSS}{TOC_CSS}</style>{cover}{''.join(toc)}{credits_pages()}{''.join(body)}")
    print_with_contents(build.ROOT / "Dictionary" / "arogno-dictionary.pdf", page, document,
                        f"arogno-dictionary.pdf: cover, contents, attributions + {len(words)} words three ways")


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
    """Expressions/arogno-expressions.pdf: the sayings and phrases by topic, two columns to the page. The
    lines of texts (genre `text`) are not printed."""
    import lexicon
    uniq, _, _ = lexicon.for_pages()
    topics = lexicon.topics()
    exprs = [p for p in uniq if p["kind"] == "expression"]
    if not exprs:
        return
    by_topic, _ = build.expression_groups(exprs, topics)
    names = {t["ID"]: t for t in topics}

    def entry(p):
        flag = " ⚠" if p["check"] else ""
        region = f' <span class="r">{esc(build.region(p))}</span>' if build.region(p) not in ("Rögn", "") else ""
        english = f' · <span class="en">{esc(p["english"])}</span>' if p["english"] else ""
        return f'<div class="x"><b>{esc(p["dialect"])}</b>{flag} <i>{esc(p["italian"])}</i>{english}{region}</div>'

    body, toc, counts = [], [], {"saying": 0, "phrase": 0}
    # every topic starts on a new page, with its own two columns
    for tid, rows in by_topic.items():
        t = names[tid]
        body.append(f'<div class="part topic" id="t-{tid}"><h1>{esc(build.topic_title(t))}</h1><div class="entries">')
        for genre, (it, en) in (("saying", build.SAYINGS), ("phrase", build.PHRASES)):
            # dialect first and sorted by it, as on the Markdown pages
            part = sorted(build.merge_expressions([p for p in rows if (p["genre"] == "saying") == (genre == "saying")]),
                          key=build.expression_order)
            if part:
                counts[genre] += len(part)
                body.append(f"<h3>{esc(it)} · {esc(en)}</h3>" + "".join(entry(p) for p in part))
        body.append("</div></div>")
        toc.append(f'<a href="#t-{tid}"><span>{esc(t.get("Name_Dialect") or t["Name"])} <span class="it">· {esc(t["Name"])} · {esc(t["Name_English"])}</span>'
                   f'</span><span>{{{{page:t-{tid}}}}}</span></a>')
    first = next(iter(by_topic), "")
    contents = ('<section class="toc"><h1>Contents</h1><a class="head" href="#attributions">'
                '<span>Attributions and thanks</span><span>{{page:attributions}}</span></a>'
                f'<a class="head" href="#t-{first}"><span>Per argomento · By topic</span>'
                f'<span>{{{{page:t-{first}}}}}</span></a>' + "".join(toc)
                + '<p class="letters">One topic to a page: sayings and idioms first, then phrases. Dialect in bold, '
                'Italian in italics, then English.</p></section>')
    cover = stamp((TEMPLATES / "cover_expressions.html").read_text())
    for k, v in (("sayings", counts["saying"]), ("phrases", counts["phrase"]), ("topics", len(by_topic))):
        cover = cover.replace("{{" + k + "}}", str(v))
    page = HERE / "cache" / "print_expressions.html"
    document = (f'<!doctype html><meta charset="utf-8"><title>Modi da dì – dialett da Rögn</title>'
                f"<style>{DICT_CSS}{TOC_CSS}{EXPR_CSS}</style>{cover}{contents}{credits_pages()}{''.join(body)}")
    print_with_contents(build.ROOT / "Expressions" / "arogno-expressions.pdf", page, document,
                        f"arogno-expressions.pdf: cover, contents, attributions + {counts['saying'] + counts['phrase']} "
                        f"expressions in {len(by_topic)} topics")

def grammar_pdf():
    """Grammar/arogno-grammar.pdf: the chapters of etc/grammar/, Italian and English in two columns,
    examples and tables in dialect (see grammar.py)."""
    import grammar, lexicon
    _, tables, _ = lexicon.for_pages()
    parts = grammar.pdf_parts(tables)
    if not parts:
        return
    contents, body, counts = parts
    cover = stamp((TEMPLATES / "cover_grammar.html").read_text())
    for k, v in counts.items():
        cover = cover.replace("{{" + k + "}}", str(v))
    page = HERE / "cache" / "print_grammar.html"
    document = (f'<!doctype html><meta charset="utf-8"><title>Gramatica – dialett da Rögn</title>'
                f"<style>{DICT_CSS}{TOC_CSS}{grammar.GRAMMAR_CSS}</style>{cover}{contents}{credits_pages()}{body}")
    print_with_contents(build.ROOT / "Grammar" / "arogno-grammar.pdf", page, document,
                        f"arogno-grammar.pdf: cover, contents, attributions + {counts['chapters']} chapters, "
                        f"{counts['examples']} examples")


if __name__ == "__main__":
    sys.exit(main())
