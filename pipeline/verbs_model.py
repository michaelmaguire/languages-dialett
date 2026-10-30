"""The verbs as one structure, which both the Markdown pages and the PDF sheets are rendered from (owner,
2026-10-30; as dictionary_model.py and expressions_model.py). Decided here, once: the verbs and their
order, the sections and tables of a page (two three-tense tables of the indicative, so a page prints on A4),
the persons of each table, and which forms and columns are inferred. step4_build_pages.py writes one Markdown
page per verb; step5_build_pdfs.py fills templates/verbs.html.j2.

    book = build(tables, eng)      # tables, eng: the verbs and English of lexicon.for_pages()
    book["verbs"][0]               # name, file, dialect, italian, english, verb_class, gerund, participle, ...
        ["sections"][0]            # title ("" for the second indicative table, under the first's heading)
            ["tenses"][0]          # name, whole (inferred throughout: † once, in the heading)
                ["cells"][0]       # person, label, text, inferred

The forms themselves come from full_grid() in step4_build_pages.py (found forms first, the gaps predicted by
verb_conjugator.py). Saved by step 4 as pipeline/cache/verbs_model.json (not committed).
"""
import json

import feminine
import step4_build_pages as pages

PATH = pages.HERE / "cache" / "verbs_model.json"
IMPERATIVE_PERSONS = [("2s", "ti"), ("1p", "nüm"), ("2p", "vialtri")]
SECTIONS = [("Indicativo", ["presente", "futuro", "futuro prossimo"], pages.PERSONS),
            ("", ["imperfetto", "passato prossimo", "trapassato prossimo"], pages.PERSONS),
            ("Condizionale", pages.CONDITIONAL, pages.PERSONS),
            ("Congiuntivo", pages.SUBJUNCTIVE, pages.PERSONS),
            ("Imperativo", ["imperativo", pages.IMPERATIVE], IMPERATIVE_PERSONS)]


def column(grid, tense, persons=None):
    """A tense's forms; a column inferred throughout is marked once, in its heading (decided 2026-10-14)."""
    cells = grid[tense]
    known = [c for c in cells.values() if c[0] != "–"]
    whole = bool(known) and all(inferred for _, inferred in known)
    persons = persons or [(s, "") for s in cells]
    return {"name": tense, "whole": whole,
            "cells": [{"person": s, "label": label, "text": cells[s][0],
                       # † on the form itself only where the column is not marked as a whole
                       "inferred": bool(cells[s][1] and not whole and cells[s][0] != "–")} for s, label in persons]}


def verb(name, e, eng):
    g = e["grid"]
    pp = column(g, "participio passato")
    raw_pp = pp["cells"][0]["text"]
    cells = [c for row in g.values() for c in row.values()]
    return {"name": name, "file": pages.verb_file(name, e),
            "dialect": " / ".join(e["dialect"]) or name, "dialect_first": e["dialect"][0] if e["dialect"] else name,
            "infinitive_inferred": e["basis"] == "inferred",
            "italian": " / ".join([name] + e["aliases"]), "english": pages.to_verb(eng.get(pages.key(name), "")),
            "verb_class": e["class"], "class_short": e["class"].split(":")[0],
            "gerund": column(g, "gerundio"),
            # rubaa/rubada: the participle with its feminine, and the note on when the feminine is used
            "participle": dict(pp, with_feminine=feminine.with_feminine(raw_pp) if raw_pp != "–" else raw_pp),
            "note": e.get("note") or "", "note_en": e.get("note_en", ""), "sources": e["sources"],
            "found": f"{sum(not c[1] and c[0] != '–' for c in cells)} of {len(cells)}",
            "inferred": sum(c[1] for c in cells),
            "sections": [{"title": title, "tenses": [column(g, t, persons) for t in tenses]}
                         for title, tenses, persons in SECTIONS]}


def build(tables, eng):
    order = sorted(tables, key=lambda n: (not tables[n]["dialect"], pages.plain(" ".join(tables[n]["dialect"]) or n)))
    verbs = [verb(n, tables[n], eng) for n in order]
    files = [v["file"] for v in verbs]
    assert len(files) == len(set(files)), "two verbs share a page name"
    return {"verbs": verbs, "inferred": sum(v["inferred"] for v in verbs)}


def save(book):
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(book, ensure_ascii=False, indent=1))


def load():
    return json.loads(PATH.read_text()) if PATH.exists() else None
