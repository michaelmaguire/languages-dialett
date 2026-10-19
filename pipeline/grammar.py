"""The grammar: etc/grammar/*.md (chapters) and etc/grammar_examples.csv (glossed examples).

Read by lexicon.py (the examples go into cldf/examples.csv with Genre `grammar`, the chapters into
cldf/grammar/ and cldf/media.csv), step4_build_pages.py (Grammar/*.md) and step5_build_pdfs.py
(Grammar/arogno-grammar.pdf).

A chapter is CLDF Markdown (https://github.com/cldf/cldf/blob/master/extensions/markdown.md) with a few
conventions of its own, so that the explanations can be printed in two columns, Italian beside English:

    # Titolo italiano | English title          the chapter title (one per file)
    ## Sezione | Section                       a section
    IT: Testo italiano …                       a paragraph in Italian, then the same in English;
    EN: English text …                         consecutive pairs share one two-column table
    [](ExampleTable#cldf:g-dimm)               on its own line: a glossed example, numbered in the chapter
    [](EntryTable#cldf:ciapa?tenses=presente,imperfetto)
                                               on its own line: verb forms from cldf/paradigms.csv, one verb
                                               in several tenses or several verbs (ids joined by ,) in one
    | … | … |                                  an ordinary table, in dialect (headers may be bilingual)
    <!-- … -->                                 a note for whoever edits the file; not shown

In the text, *word* is a dialect word, [ciapà](EntryTable#cldf:ciapa) links to its verb page, and † marks
a statement that Claude worked out from the forms in the course rather than one the course states.
"""
import csv, html, re
from collections import defaultdict
from urllib.parse import quote

from paths import CLDF, ETC, ROOT

DIR = ETC / "grammar"
EXAMPLES = ETC / "grammar_examples.csv"
LINK = re.compile(r"\[([^\]]*)\]\((EntryTable|ExampleTable)#cldf:([^)?\s]+)(?:\?([^)\s]*))?\)")
BLOCK_LINK = re.compile(r"^\[\]\((EntryTable|ExampleTable)#cldf:([^)?\s]+)(?:\?([^)\s]*))?\)\s*$")
PERSONS = [("1s", "mi"), ("2s", "ti"), ("3s", "le / lü"), ("1p", "nüm"), ("2p", "vialtri"), ("3p", "lur")]
TENSE_LABEL = {"presente": "presente", "imperfetto": "imperfetto", "passato prossimo": "passato prossimo",
               "trapassato prossimo": "trapassato prossimo", "futuro": "futuro",
               "futuro prossimo": "futuro anteriore (corso: «futuro prossimo»)",
               "condizionale presente": "condizionale presente", "condizionale passato": "condizionale passato",
               "congiuntivo presente": "congiuntivo presente", "congiuntivo imperfetto": "congiuntivo imperfetto",
               "imperativo": "imperativo", "imperativo negativo": "imperativo negativo",
               "gerundio": "gerundio", "participio passato": "participio passato"}
GRAMMAR_CONTRIBUTION = {
    "ID": "grammar", "Name": "Grammatica del dialett da Rögn · A grammar of the Rögn dialect",
    "Description": "Explanations in Italian and English (cldf/grammar/*.md), with examples from the course "
                   "documents cited line by line",
    "Contributor": "Michael Maguire; text drafted by Claude (Anthropic)", "Citation": None,
    "Genre": "grammar", "Source": []}


# ------------------------------------------------------------------ reading
def read_examples():
    rows = list(csv.DictReader(EXAMPLES.open(encoding="utf-8"))) if EXAMPLES.exists() else []
    return {r["ID"]: r for r in rows}


def _bilingual(text):
    it, _, en = text.partition(" | ")
    return it.strip(), (en or it).strip()


def parse(path):
    """One chapter: {"id", "file", "title": (it, en), "blocks": [...]}. Blocks are
    ("h2", it, en), ("pairs", [(it, en), ...]), ("examples", [id, ...]), ("verbs", [entry ids], [tenses]),
    ("table", [lines])."""
    lines = path.read_text(encoding="utf-8").splitlines()
    num = re.match(r"(\d+)", path.stem)
    chapter = {"id": path.stem, "file": path.name, "title": ("", ""), "blocks": [],
               "num": int(num.group(1)) if num else None}     # 00-introduzione: no number
    blocks = chapter["blocks"]
    i = 0

    def last(kind):
        return blocks[-1] if blocks and blocks[-1][0] == kind else None

    def gather(start, stop):
        """Text of a paragraph: the line after its marker plus continuation lines."""
        out, j = [lines[start][3:].strip()], start + 1
        while j < len(lines) and lines[j].strip() and not stop(lines[j]):
            out.append(lines[j].strip())
            j += 1
        return " ".join(out), j

    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith("<!--"):
            while "-->" not in lines[i]:
                i += 1
            i += 1
            continue
        if not s:
            i += 1
            continue
        if s.startswith("# "):
            chapter["title"] = _bilingual(s[2:])
            i += 1
        elif s.startswith("## "):
            blocks.append(("h2", *_bilingual(s[3:])))
            i += 1
        elif s.startswith("IT:"):
            it, i = gather(i, lambda l: l.startswith(("EN:", "IT:", "#", "[](", "|")))
            if i >= len(lines) or not lines[i].startswith("EN:"):
                raise SystemExit(f"{path.name}: an IT: paragraph without its EN: ({it[:40]}…)")
            en, i = gather(i, lambda l: l.startswith(("EN:", "IT:", "#", "[](", "|")))
            (last("pairs") or blocks.append(("pairs", [])) or blocks[-1])[1].append((it, en))
        elif BLOCK_LINK.match(s):
            table, ids, query = BLOCK_LINK.match(s).groups()
            if table == "ExampleTable":
                (last("examples") or blocks.append(("examples", [])) or blocks[-1])[1].append(ids)
            else:
                tenses = [t.replace("_", " ") for t in re.sub(r"^tenses=", "", query or "presente").split(",")]
                blocks.append(("verbs", ids.split(","), tenses))
            i += 1
        elif s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            blocks.append(("table", rows))
        else:
            raise SystemExit(f"{path.name}, line {i + 1}: not IT:/EN:, a heading, a link line or a table: {s[:60]}")
    return chapter


def chapters(folder=DIR):
    """The chapters in etc/grammar/ (for step 3), or in the copy cldf/grammar/ (for steps 4 and 5, which
    read cldf/ only)."""
    return [parse(p) for p in sorted(folder.glob("*.md"))] if folder.is_dir() else []


def references(chs):
    """(example ids, entry ids) the chapters use, to check them against the data."""
    ex, en = set(), set()
    for ch in chs:
        for b in ch["blocks"]:
            if b[0] == "examples":
                ex.update(b[1])
            elif b[0] == "verbs":
                en.update(b[1])
            texts = [x for pair in b[1] for x in pair] if b[0] == "pairs" else \
                    list(b[1:]) if b[0] == "h2" else b[1] if b[0] == "table" else []
            for t in texts:
                for label, table, ident, _ in LINK.findall(t):
                    (ex if table == "ExampleTable" else en).update(ident.split(","))
    return ex, en


# ------------------------------------------------------------------ into CLDF (called by lexicon.make)
def norm(s):
    s = s.lower().replace("’", "'").replace("‘", "'").replace("`", "'")
    return re.sub(r"[^\w']+", " ", s).strip()


def cldf_rows(rows, bib, cite, bib_entry, lesson_meta, cldf_dir):
    """Add the grammar's examples to rows["examples.csv"] (Genre grammar, Contribution grammar, in the order
    they appear in the chapters), its chapters to rows["media.csv"], and copy the chapters to cldf/grammar/.
    Returns warnings: examples whose text is not on the line they cite, ids the chapters use that do not
    exist, examples no chapter uses."""
    chs = chapters()
    data = read_examples()
    warnings = []
    used_ex, used_en = references(chs)
    entry_ids = {e["ID"] for e in rows["entries.csv"]}
    for i in sorted(used_ex - data.keys()):
        warnings.append(f"grammar: example {i} is used in a chapter but not in etc/grammar_examples.csv")
    for i in sorted(used_en - entry_ids):
        warnings.append(f"grammar: entry {i} is used in a chapter but is not in cldf/entries.csv")
    for i in sorted(i for i in data if not re.fullmatch(r"[a-zA-Z0-9_-]+", i)):
        raise SystemExit(f"etc/grammar_examples.csv: ID {i!r} may only have letters a-z, digits, - and _")
    for i in sorted(data.keys() - used_ex):
        warnings.append(f"grammar: example {i} is in etc/grammar_examples.csv but no chapter uses it")
    order = [i for ch in chs for b in ch["blocks"] if b[0] == "examples" for i in b[1]]
    have = {b.id for b in bib}
    text_dir = ROOT / "pipeline" / "cache" / "lesson_text"
    for n, i in enumerate(dict.fromkeys(order), 1):
        r = data.get(i)
        if not r:
            continue
        words, gloss = r["Analyzed_Word"].split(), r["Gloss"].split()
        if len(words) != len(gloss):
            warnings.append(f"grammar: example {i} has {len(words)} words but {len(gloss)} glosses")
        src = text_dir / (r["Source"] + ".txt")
        if src.exists():
            lines = src.read_text(encoding="utf-8").split("\n")
            line = lines[int(r["Line"]) - 1] if r["Line"].isdigit() and int(r["Line"]) <= len(lines) else ""
            if norm(r["Primary_Text"]) not in norm(line):
                warnings.append(f"grammar: example {i}: {r['Primary_Text']!r} is not on {r['Source']} line {r['Line']}")
        ref = cite(r["Source"], r["Line"])
        key = ref.split("[")[0]
        if key not in have:
            bib.append(bib_entry(r["Source"], lesson_meta))
            have.add(key)
        rows["examples.csv"].append({
            "ID": i, "Language_ID": "rogn", "Primary_Text": r["Primary_Text"],
            "Analyzed_Word": words, "Gloss": gloss,
            "Translated_Text": r["Italian"], "Meta_Language_ID": "ita",
            "Translated_Text_English": r["English"] or None, "Status": "accepted", "Unsure_About": None,
            "Comment": r.get("Comment") or None, "Source": [ref],
            "Contribution_ID": "grammar", "Position": n, "Genre": "grammar", "Topic_ID": None})
    if chs:
        rows["contributions.csv"].append(dict(GRAMMAR_CONTRIBUTION))
    rows["media.csv"] = [{"ID": ch["id"], "Name": f"{ch['title'][0]} · {ch['title'][1]}",
                          "Description": "Grammar chapter (CLDF Markdown), Italian and English side by side",
                          "Media_Type": "text/markdown", "Download_URL": f"grammar/{ch['file']}", "Path_In_Zip": None}
                         for ch in chs]
    out = cldf_dir / "grammar"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.md"):
        old.unlink()
    for ch in chs:
        (out / ch["file"]).write_text((DIR / ch["file"]).read_text(encoding="utf-8"), encoding="utf-8")
    return warnings


# ------------------------------------------------------------------ shared by pages and PDF
def load_data(tables):
    """Everything rendering needs, from cldf/ (via lexicon) and the page-format verb tables.
    tables: lexicon.for_pages()[1], whose values carry their entry_id."""
    import lexicon
    _, rows = lexicon.load()
    examples = {x["ID"]: x for x in rows["examples.csv"] if x.get("Genre") == "grammar"}
    by_entry = {t.get("entry_id"): (name, t) for name, t in tables.items() if t.get("entry_id")}
    entries = {e["ID"]: e for e in rows["entries.csv"]}
    # each example's document and line, from its citation (key[l.N]) and the file named in sources.bib
    bib_file = {}
    for chunk in (CLDF / "sources.bib").read_text().split("@misc{")[1:]:
        m = re.search(r"note = \{(?:raw/)?(.+?)\}", chunk)
        bib_file[chunk.split(",", 1)[0].strip()] = m.group(1) if m else ""
    files = {}
    for i, x in examples.items():
        m = re.match(r"([^\[]+)(?:\[l\.(\d+)\])?", (x["Source"] or [""])[0])
        files[i] = {"Source": bib_file.get(m.group(1), m.group(1)), "Line": m.group(2) or ""}
    return {"examples": examples, "verbs": by_entry, "entries": entries, "files": files}


def verb_grid(ids, tenses, d):
    """(header, rows): header cells and rows of (label, [(form, inferred), ...])."""
    verbs = [(i, *d["verbs"][i]) for i in ids if i in d["verbs"]]
    if not verbs:
        return [], []
    if len(verbs) == 1:
        cols = [(t, verbs[0][2]["grid"].get(t, {})) for t in tenses]
        header = [TENSE_LABEL.get(t, t) for t in tenses]
    else:
        t = tenses[0]
        cols = [(i, tab["grid"].get(t, {})) for i, _, tab in verbs]
        header = [i for i, _, _ in verbs]
    persons = [("-", "")] if all(set(c) <= {"-"} for _, c in cols) else \
              [p for p in PERSONS if any(p[0] in c for _, c in cols)]
    rows = []
    for code, label in persons:
        rows.append((label, [c.get(code, ("–", False)) for _, c in cols]))
    return header, rows


def source_title(file):
    return re.sub(r"\.(docx|pdf|txt)$", "", re.sub(r"^\d{4}-\d\d-\d\d-", "", file))


# ------------------------------------------------------------------ Markdown pages (step 4)
def md_inline(text, d, verb_file):
    def link(m):
        label, table, ident, _ = m.groups()
        first = ident.split(",")[0]
        if table == "EntryTable" and first in d["verbs"]:
            name, t = d["verbs"][first]
            return f"[*{label or t['dialect'][0]}*](../Verbs/{quote(verb_file(name, t))})"
        return f"*{label}*" if label else ""
    return LINK.sub(link, text).replace("|", "\\|")


def md_example(n, x, d, src_link):
    r = d["files"].get(x["ID"], {})
    out = [f"**({n})** *{x['Primary_Text']}*\n"]
    words, gloss = x["Analyzed_Word"] or [], x["Gloss"] or []
    if words:
        out.append("| " + " | ".join(f"*{w}*" for w in words) + " |")
        out.append("|" + "---|" * len(words))
        out.append("| " + " | ".join(g.replace("|", "\\|") for g in gloss) + " |\n")
    tr = f"‘{x['Translated_Text']}’"
    if x.get("Translated_Text_English"):
        tr += f" · ‘{x['Translated_Text_English']}’"
    where = src_link(r.get("Source", ""), depth=1, text=f"{source_title(r.get('Source', ''))}, l. {r.get('Line', '')}") \
        if r.get("Source") else ""
    out.append(f"{tr} — {where}\n" + (f"\n*{x['Comment']}*\n" if x.get("Comment") else ""))
    return "\n".join(out)


def md_chapter(ch, d, verb_file, src_link, nav):
    num = f"{ch['num']}. " if ch.get("num") else ""
    out = [f"# {num}{ch['title'][0]}\n", f"*{ch['title'][1]}*\n", nav + "\n"]
    n = 0
    for b in ch["blocks"]:
        if b[0] == "h2":
            out.append(f"## {b[1]} · *{b[2]}*\n")
        elif b[0] == "pairs":
            out.append("| Italiano | English |\n|---|---|\n" + "\n".join(
                f"| {md_inline(it, d, verb_file)} | {md_inline(en, d, verb_file)} |" for it, en in b[1]) + "\n")
        elif b[0] == "examples":
            for i in b[1]:
                if i in d["examples"]:
                    n += 1
                    out.append(md_example(n, d["examples"][i], d, src_link))
        elif b[0] == "verbs":
            header, rows = verb_grid(b[1], b[2], d)
            if not rows:
                continue
            if len(b[1]) > 1:
                header = [f"[*{d['verbs'][i][1]['dialect'][0]}*](../Verbs/{quote(verb_file(*d['verbs'][i]))})"
                          for i in b[1] if i in d["verbs"]]
                cap = f"*{TENSE_LABEL.get(b[2][0], b[2][0])}*"
            else:
                name, t = d["verbs"][b[1][0]]
                cap = f"[*{t['dialect'][0]}*](../Verbs/{quote(verb_file(name, t))}) ({name})"
            out.append(cap + "\n")
            out.append("|  | " + " | ".join(header) + " |\n|---|" + "---|" * len(header) + "\n" + "\n".join(
                "| " + (f"*{label}*" if label else "") + " | " + " | ".join(
                    f"{f}{' †' if inf else ''}" for f, inf in cells) + " |" for label, cells in rows) + "\n")
        elif b[0] == "table":
            out.append("\n".join(md_inline(r, d, verb_file).replace("\\|", "|") for r in b[1]) + "\n")
    out.append(nav + "\n")
    return "\n".join(out)


INTRO_MD = (
    "# Grammatica · Grammar\n\n"
    "**[arogno-grammar.pdf](arogno-grammar.pdf)** has the whole grammar for printing.\n\n"
    "A short grammar of the dialect of Rögn (Arogno), written from the course material: the lessons and Guido "
    "Casellini's exercise sheets. Every chapter explains in Italian and English side by side; the examples and "
    "tables are in dialect, each example with the document and line it comes from. † marks a statement worked "
    "out from the forms in the course rather than stated by it, and, in a verb table, a predicted form.\n\n"
    "The text was drafted by Claude (Anthropic) and has not yet been checked by the teacher: see "
    "[TO-CHECK.md](../TO-CHECK.md). The chapters themselves are kept in "
    "[`etc/grammar/`](../etc/grammar/) and the examples in "
    "[`etc/grammar_examples.csv`](../etc/grammar_examples.csv).\n")


def write_pages(tables, verb_file, src_link, write):
    """Grammar/README.md and one page per chapter. Returns the number of chapters."""
    chs = chapters(CLDF / "grammar")
    if not chs:
        return 0
    d = load_data(tables)
    index = []
    for k, ch in enumerate(chs):
        prev = f"[← {chs[k - 1]['title'][0]}]({chs[k - 1]['id']}.md)" if k else ""
        nxt = f"[{chs[k + 1]['title'][0]} →]({chs[k + 1]['id']}.md)" if k + 1 < len(chs) else ""
        nav = " · ".join(x for x in (prev, "[indice · contents](README.md)", nxt) if x)
        write(ROOT / "Grammar" / f"{ch['id']}.md", md_chapter(ch, d, verb_file, src_link, nav))
        exs = sum(len(b[1]) for b in ch["blocks"] if b[0] == "examples")
        index.append(f"| {ch['num'] or ''} | [{ch['title'][0]}]({ch['id']}.md) | {ch['title'][1]} | {exs} |")
    write(ROOT / "Grammar" / "README.md", INTRO_MD + "\n| | Italiano | English | Esempi · examples |\n|---|---|---|---|\n"
          + "\n".join(index) + "\n")
    return len(chs)


# ------------------------------------------------------------------ HTML for the PDF (step 5)
def html_inline(text):
    text = html.escape(text, quote=False)
    text = LINK.sub(lambda m: f"<i>{m.group(1)}</i>" if m.group(1) else "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)               # links to other pages: text only
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)\*(?!\w)", r"<i>\1</i>", text)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", text)


def number(ch):
    return str(ch["num"]) if ch.get("num") else ""


def html_chapter(ch, d):
    out = [f'<div class="part chapter" id="ch-{ch["id"]}"><h1><span class="num">{number(ch)}</span>'
           f'{html_inline(ch["title"][0])}<span class="en">{html_inline(ch["title"][1])}</span></h1>']
    n = 0
    for b in ch["blocks"]:
        if b[0] == "h2":
            out.append(f'<h2>{html_inline(b[1])} <span class="en">· {html_inline(b[2])}</span></h2>')
        elif b[0] == "pairs":
            out.append('<div class="pairs">' + "".join(
                f'<div class="it">{html_inline(it)}</div><div class="en">{html_inline(en)}</div>' for it, en in b[1])
                + "</div>")
        elif b[0] == "examples":
            for i in b[1]:
                x = d["examples"].get(i)
                if not x:
                    continue
                n += 1
                r = d["files"].get(i, {})
                words, gloss = x["Analyzed_Word"] or [], x["Gloss"] or []
                igt = ('<div class="igt">' + "".join(
                    f'<span class="w"><span>{html.escape(w)}</span><span class="g">{html.escape(g)}</span></span>'
                    for w, g in zip(words, gloss)) + "</div>") if words else ""
                en = f' · <span class="ten">‘{html.escape(x["Translated_Text_English"])}’</span>' \
                    if x.get("Translated_Text_English") else ""
                src = f'{html.escape(source_title(r.get("Source", "")))}, l. {html.escape(r.get("Line", ""))}'
                note = f'<div class="note">{html_inline(x["Comment"])}</div>' if x.get("Comment") else ""
                out.append(f'<div class="ex"><span class="n">({n})</span><div><div class="pt">'
                           f'{html.escape(x["Primary_Text"])}</div>{igt}<div class="tr">‘{html.escape(x["Translated_Text"])}’'
                           f'{en}<span class="src">{src}</span></div>{note}</div></div>')
        elif b[0] == "verbs":
            header, rows = verb_grid(b[1], b[2], d)
            if not rows:
                continue
            if len(b[1]) > 1:
                header = [d["verbs"][i][1]["dialect"][0] for i in b[1] if i in d["verbs"]]
                cap = f'<i>{html.escape(TENSE_LABEL.get(b[2][0], b[2][0]))}</i>'
            else:
                name, t = d["verbs"][b[1][0]]
                cap = f'<b>{html.escape(t["dialect"][0])}</b> <i>({html.escape(name)})</i>'
            out.append(f'<table class="vt"><caption>{cap}</caption><tr><th></th>'
                       + "".join(f"<th>{html.escape(h)}</th>" for h in header) + "</tr>" + "".join(
                           f'<tr><td class="p">{html.escape(label)}</td>' + "".join(
                               f'<td>{html.escape(f)}{"<sup>†</sup>" if inf else ""}</td>' for f, inf in cells)
                           + "</tr>" for label, cells in rows) + "</table>")
        elif b[0] == "table":
            cells = lambda line: [c.strip() for c in line.strip().strip("|").split("|")]
            head, body = cells(b[1][0]), [cells(r) for r in b[1][2:]]
            out.append('<table class="dt"><tr>' + "".join(f"<th>{html_inline(c)}</th>" for c in head) + "</tr>"
                       + "".join("<tr>" + "".join(f"<td>{html_inline(c)}</td>" for c in r) + "</tr>" for r in body)
                       + "</table>")
    out.append("</div>")
    return "".join(out)


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


def pdf_parts(tables):
    """(contents html, body html, counts) for step 5, or None when there is no grammar."""
    chs = chapters(CLDF / "grammar")
    if not chs:
        return None
    d = load_data(tables)
    body = [html_chapter(ch, d) for ch in chs]
    toc = "".join(f'<a href="#ch-{ch["id"]}"><span><b>{number(ch)}</b> {html_inline(ch["title"][0])} '
                  f'<span class="en">· {html_inline(ch["title"][1])}</span></span>'
                  f'<span>{{{{page:ch-{ch["id"]}}}}}</span></a>' for ch in chs)
    n_ex = sum(len(b[1]) for ch in chs for b in ch["blocks"] if b[0] == "examples")
    contents = ('<section class="toc gtoc"><h1>Indice · Contents</h1><a class="head" href="#attributions">'
                '<span>Ringraziamenti · Attributions and thanks</span><span>{{page:attributions}}</span></a>'
                + toc + '<div class="gintro"><p>Ogni capitolo spiega in italiano (a sinistra) e in inglese (a destra); '
                'esempi e tabelle sono in dialetto, ogni esempio con il documento e la riga da cui viene. '
                '† segna ciò che è dedotto dalle forme del corso e non detto dal corso stesso; in una tabella, '
                'una forma dedotta.</p><p>Each chapter explains in Italian (left) and English (right); examples and '
                'tables are in dialect, each example with the document and line it comes from. † marks what is '
                'worked out from the forms in the course rather than stated by it; in a table, a predicted form.'
                '</p></div></section>')
    return contents, "".join(body), {"chapters": len(chs), "examples": n_ex}
