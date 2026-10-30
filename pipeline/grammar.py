"""The grammar: etc/grammar/*.md (chapters) and etc/grammar_examples.csv (glossed examples).

Read by lexicon.py (the examples go into cldf/examples.csv with Genre `grammar`, the chapters into
cldf/grammar/ and cldf/media.csv) and by grammar_model.py, which resolves the parsed chapters into the one
model that step4_build_pages.py (Grammar/*.md, with md_chapter() here) and step5_build_pdfs.py
(Grammar/arogno-grammar.pdf, templates/grammar.html.j2 with html_inline() here) both render.

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
    text_dir = ROOT / "raw" / "extracted" / "lesson_text"   # private: skipped without raw/
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
    return re.sub(r"\.(docx|pdf|txt)$", "", re.sub(r"^\d{4}-\d\d-\d\d-(\d{4}-)?", "", file))   # 2024-10-10-1054-


# ------------------------------------------------------------------ Markdown pages (step 4)
def md_inline(text, files):
    """A chapter's Markdown for a page: links to a verb lead to its page (files: verb ID -> page)."""
    def link(m):
        label, table, ident, _ = m.groups()
        first = ident.split(",")[0]
        if table == "EntryTable" and first in files:
            return f"[*{label}*](../Verbs/{quote(files[first])})"
        return f"*{label}*" if label else ""
    return LINK.sub(link, text).replace("|", "\\|")


def md_example(x, src_link):
    out = [f"**({x['n']})** *{x['text']}*\n"]
    if x["words"]:
        out.append("| " + " | ".join(f"*{w}*" for w in x["words"]) + " |")
        out.append("|" + "---|" * len(x["words"]))
        out.append("| " + " | ".join(g.replace("|", "\\|") for g in x["gloss"]) + " |\n")
    tr = f"‘{x['italian']}’" + (f" · ‘{x['english']}’" if x["english"] else "")
    where = src_link(x["source"], depth=1, text=f"{x['source_title']}, l. {x['line']}") if x["source"] else ""
    out.append(f"{tr} — {where}\n" + (f"\n*{x['comment']}*\n" if x["comment"] else ""))
    return "\n".join(out)


def md_chapter(ch, files, src_link, nav):
    """One chapter's page, from the grammar model (grammar_model.py)."""
    num = f"{ch['num']}. " if ch.get("num") else ""
    out = [f"# {num}{ch['title_it']}\n", f"*{ch['title_en']}*\n", nav + "\n"]
    for b in ch["blocks"]:
        if b["kind"] == "h2":
            out.append(f"## {b['it']} · *{b['en']}*\n")
        elif b["kind"] == "pairs":
            out.append("| Italiano | English |\n|---|---|\n" + "\n".join(
                f"| {md_inline(it, files)} | {md_inline(en, files)} |" for it, en in b["pairs"]) + "\n")
        elif b["kind"] == "example":
            out.append(md_example(b, src_link))
        elif b["kind"] == "verbs":
            page = lambda v: f"[*{v['dialect']}*](../Verbs/{quote(v['file'])})"
            if b["multi"]:
                header, cap = [page(v) for v in b["verbs"]], f"*{b['tense']}*"
            else:
                header, cap = b["header"], f"{page(b['verb'])} ({b['verb']['name']})"
            out.append(cap + "\n")
            out.append("|  | " + " | ".join(header) + " |\n|---|" + "---|" * len(header) + "\n" + "\n".join(
                "| " + (f"*{r['label']}*" if r["label"] else "") + " | " + " | ".join(
                    f"{c['form']}{' †' if c['inferred'] else ''}" for c in r["cells"]) + " |" for r in b["rows"]) + "\n")
        elif b["kind"] == "table":
            out.append("\n".join(md_inline(r, files).replace("\\|", "|") for r in b["lines"]) + "\n")
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


def write_pages(book, src_link, write):
    """Grammar/README.md and one page per chapter, from the grammar model. Returns the number of chapters."""
    if not book:
        return 0
    chs = book["chapters"]
    title = {c["id"]: c["title_it"] for c in chs}
    index = []
    for ch in chs:
        prev = f"[← {title[ch['prev']]}]({ch['prev']}.md)" if ch["prev"] else ""
        nxt = f"[{title[ch['next']]} →]({ch['next']}.md)" if ch["next"] else ""
        nav = " · ".join(x for x in (prev, "[indice · contents](README.md)", nxt) if x)
        write(ROOT / "Grammar" / f"{ch['id']}.md", md_chapter(ch, book["verb_files"], src_link, nav))
        index.append(f"| {ch['num'] or ''} | [{ch['title_it']}]({ch['id']}.md) | {ch['title_en']} | {ch['examples']} |")
    write(ROOT / "Grammar" / "README.md", INTRO_MD + "\n| | Italiano | English | Esempi · examples |\n|---|---|---|---|\n"
          + "\n".join(index) + "\n")
    return len(chs)


# ------------------------------------------------------------------ HTML for the PDF (step 5)
def html_inline(text, files=None, base=""):
    """A chapter's Markdown as HTML for the PDF. A link to a verb becomes a link to its page online
    (base + file; owner, 2026-10-30), styled like the text around it so a printed copy does not show it."""
    files = files or {}

    def link(m):
        label, table, ident, _ = m.groups()
        first = ident.split(",")[0]
        if not label:
            return ""
        if table == "EntryTable" and first in files:
            return f'<a class="web" href="{base}{quote(files[first])}"><i>{label}</i></a>'
        return f"<i>{label}</i>"
    text = html.escape(text, quote=False)
    text = LINK.sub(link, text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)               # links to other pages: text only
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)\*(?!\w)", r"<i>\1</i>", text)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
