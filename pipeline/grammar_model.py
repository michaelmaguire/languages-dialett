"""The grammar as one structure, which both the Markdown pages and the PDF are rendered from (owner,
2026-10-30; as dictionary_model.py, expressions_model.py and verbs_model.py). grammar.parse() reads a
chapter into blocks; this resolves every block into what is shown, once: the examples' numbers, text,
glosses, translations and source line; each verb table's caption, header and forms (with † decided); the
dialect tables' cells; and the label of every link to a verb page (the verb's own name when the link has
none). The renderers only format: grammar.md_chapter() writes the Markdown, step5_build_pdfs.py fills
templates/grammar.html.j2.

    book = build(tables, verb_file)    # tables: the verbs of lexicon.for_pages()
    book["chapters"][0]                # id, num, title_it, title_en, prev, next, examples
        ["blocks"][0]                  # kind: h2 | pairs | example | verbs | table

Text is kept as the chapter's own Markdown (*word*, **bold**, `code`), with links resolved to
[label](EntryTable#cldf:ID) and the verb's page in book["verb_files"]. Saved by step 4 as
pipeline/cache/grammar_model.json (not committed).
"""
import json

import grammar
from paths import CLDF, PIPELINE

PATH = PIPELINE / "cache" / "grammar_model.json"


def resolve(text, d):
    """Give every link to a verb its label: [](EntryTable#cldf:ciapa) -> [ciapà](EntryTable#cldf:ciapa)."""
    def link(m):
        label, table, ident, query = m.groups()
        first = ident.split(",")[0]
        if table == "EntryTable" and not label and first in d["verbs"]:
            label = d["verbs"][first][1]["dialect"][0]
        return f"[{label}]({table}#cldf:{ident}" + (f"?{query}" if query else "") + ")"
    return grammar.LINK.sub(link, text)


def example(n, x, d):
    r = d["files"].get(x["ID"], {})
    return {"kind": "example", "n": n, "id": x["ID"], "text": x["Primary_Text"],
            "words": x["Analyzed_Word"] or [], "gloss": x["Gloss"] or [],
            "italian": x["Translated_Text"], "english": x.get("Translated_Text_English") or "",
            "source": r.get("Source", ""), "line": r.get("Line", ""),
            "source_title": grammar.source_title(r.get("Source", "")), "comment": resolve(x.get("Comment") or "", d)}


def verbs_block(ids, tenses, d, verb_file):
    header, rows = grammar.verb_grid(ids, tenses, d)
    if not rows:
        return None
    known = [i for i in ids if i in d["verbs"]]
    link = lambda i: {"dialect": d["verbs"][i][1]["dialect"][0], "name": d["verbs"][i][0],
                      "file": verb_file(*d["verbs"][i])}
    block = {"kind": "verbs", "rows": [{"label": label, "cells": [{"form": f, "inferred": bool(inf)} for f, inf in cells]}
                                       for label, cells in rows]}
    if len(ids) > 1:            # several verbs in one tense: a column per verb, the tense as caption
        block.update(multi=True, verbs=[link(i) for i in known], tense=grammar.TENSE_LABEL.get(tenses[0], tenses[0]))
    else:                       # one verb in several tenses: a column per tense, the verb as caption
        block.update(multi=False, verb=link(ids[0]), header=header)
    return block


def table_block(lines, d):
    lines = [resolve(r, d) for r in lines]
    cells = lambda line: [c.strip() for c in line.strip().strip("|").split("|")]
    return {"kind": "table", "lines": lines, "head": cells(lines[0]), "body": [cells(r) for r in lines[2:]]}


def chapter(ch, d, verb_file):
    blocks, n = [], 0
    for b in ch["blocks"]:
        if b[0] == "h2":
            blocks.append({"kind": "h2", "it": b[1], "en": b[2]})
        elif b[0] == "pairs":
            blocks.append({"kind": "pairs", "pairs": [[resolve(it, d), resolve(en, d)] for it, en in b[1]]})
        elif b[0] == "examples":
            for i in b[1]:
                if i in d["examples"]:          # an unknown ID is reported by the build (lexicon.py)
                    n += 1
                    blocks.append(example(n, d["examples"][i], d))
        elif b[0] == "verbs":
            v = verbs_block(b[1], b[2], d, verb_file)
            if v:
                blocks.append(v)
        elif b[0] == "table":
            blocks.append(table_block(b[1], d))
    return {"id": ch["id"], "num": ch["num"], "number": str(ch["num"]) if ch.get("num") else "",
            "title_it": ch["title"][0], "title_en": ch["title"][1], "examples": n, "blocks": blocks}


def build(tables, verb_file):
    chs = grammar.chapters(CLDF / "grammar")
    if not chs:
        return None
    d = grammar.load_data(tables)
    chapters = [chapter(ch, d, verb_file) for ch in chs]
    for k, c in enumerate(chapters):             # the pages' links to the chapters before and after
        c["prev"] = chapters[k - 1]["id"] if k else None
        c["next"] = chapters[k + 1]["id"] if k + 1 < len(chapters) else None
    # every verb a link can lead to, with its page (Verbs/<file>)
    files = {i: verb_file(name, t) for i, (name, t) in d["verbs"].items()}
    return {"chapters": chapters, "examples": sum(c["examples"] for c in chapters), "verb_files": files}


def save(book):
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(book, ensure_ascii=False, indent=1))


def load():
    return json.loads(PATH.read_text()) if PATH.exists() else None
