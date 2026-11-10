"""Step 6: the data for the phone app (michaelmaguire/languages-dialett-app, owner 2026-11-07), as one JSON
file made from the four book models that step 4 saves (dictionary, expressions, verbs, grammar). Like the
Markdown pages and the PDFs, the app is only a renderer: what an entry shows is decided in the models, and
this step only reshapes them for a small screen and for search.

    .venv/bin/python step6_build_app_data.py                 # -> pipeline/cache/app_data.json
    .venv/bin/python step6_build_app_data.py --out FILE      # e.g. into the app's resources

What changes from the models:
- the dictionary is the Dialett look-up only; its "(= …)" pointer rows for alternate spellings are dropped,
  since the app searches every spelling inside an entry anyway. Verbs link to their page by ID (the page's
  file name without .md).
- verb tables: one list of tenses per verb (the PDF's split of the indicative into two tables of three is
  for A4), each form with its person label and whether it is inferred (†).
- grammar text keeps *italics* and **bold**; links to other pages become their label, since those pages
  (TO-CHECK.md, Verbs/README.md) are not in the app. Markdown tables become header and rows of cells.
- expressions: as in the model, by topic, sayings then phrases.
- verbs with a particle have no page of their own: each is in its base verb's "also", as on the pages.
Nothing is added that the pages do not already publish: no lines of texts (see CLAUDE.md, the privacy rule).
"""
import argparse
import json
import re
import sys
import time

import dictionary_model
import expressions_model
import grammar_model
import verbs_model
from paths import CACHE

PATH = CACHE / "app_data.json"
# the schema of the file; the app refuses a file whose major version it does not know
VERSION = 1

POINTER = re.compile(r"\s\(= [^)]*\)$")
LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")


def page_id(file):
    return file.removesuffix(".md")


def dictionary(book):
    out = []
    for e in dictionary_model.entries(book, "dialect"):
        if POINTER.search(e["head"]):
            continue
        out.append({
            "head": e["head"], "flag": e["flag"], "notes": e["notes"],
            "senses": [{"dialect": s["dialect"], "label": s["label"], "pos": s["pos"],
                        "italian": s["italian"], "english": s["english"], "region": s["region"],
                        "note": s["note"], "source": s["source"], "check": s["check"],
                        "newWord": s["new_word"], "verb": page_id(s["verb_page"])} for s in e["senses"]]})
    return out


def forms(column):
    return [{"label": c["label"], "text": c["text"], "inferred": c["inferred"]} for c in column["cells"]]


def verbs(book):
    out = []
    for v in book["verbs"]:
        tenses = []
        for section in v["sections"]:
            for t in section["tenses"]:
                # a section title ("Indicativo") is on its first table only; carry it to every tense
                tenses.append({"mood": section["title"] or (tenses[-1]["mood"] if tenses else ""),
                               "name": t["name"], "forms": forms(t)})
        out.append({
            "id": page_id(v["file"]), "dialect": v["dialect"], "italian": v["italian"], "english": v["english"],
            "infinitiveInferred": v["infinitive_inferred"], "verbClass": v["verb_class"],
            "gerund": forms(v["gerund"]), "participle": v["participle"]["with_feminine"] or
            " / ".join(c["text"] for c in v["participle"]["cells"]),
            "participleInferred": any(c["inferred"] for c in v["participle"]["cells"]),
            "note": v["note"], "noteEnglish": v["note_en"], "found": v["found"], "sources": v["sources"],
            # verbs with a particle (na giò, tacà sü), listed on their base verb's page (owner, 2026-11-10)
            "also": [{"dialect": a["dialect"], "italian": a["italian"], "english": a["english"]} for a in v.get("also", [])],
            "tenses": tenses})
    return out


def expressions(book):
    return [{"id": t["id"], "dialect": t["name_dialect"], "italian": t["name"], "english": t["name_english"],
             "sections": [{"genre": s["genre"], "italian": s["title_it"], "english": s["title_en"],
                           "entries": [{"dialect": x["dialect"], "italian": x["italian"], "english": x["english"],
                                        "region": x["region"], "check": x["check"], "sources": x["sources"]}
                                       for x in s["entries"]]}
                          for s in t["sections"]]}
            for t in book["topics"]]


def text(s):
    return LINK.sub(r"\1", s)


def block(b):
    kind = b["kind"]
    if kind == "h2":
        return {"type": "heading", "italian": text(b["it"]), "english": text(b["en"])}
    if kind == "pairs":
        return {"type": "paragraphs", "pairs": [{"italian": text(it), "english": text(en)} for it, en in b["pairs"]]}
    if kind == "example":
        return {"type": "example", "number": b["n"], "dialect": b["text"], "words": b["words"], "gloss": b["gloss"],
                "italian": b["italian"], "english": b["english"], "source": b["source"], "comment": b["comment"]}
    if kind == "table":
        return {"type": "table", "header": [text(c) for c in b["head"]], "rows": [[text(c) for c in r] for r in b["body"]]}
    if kind == "verbs":
        # several verbs in one tense (a column per verb, the tense as caption), or one verb in several tenses
        # (a column per tense, the verb as caption): one shape for both, each verb linked to its page
        verb = lambda v: {"title": v["dialect"], "subtitle": v["name"], "verb": page_id(v["file"])}
        if b["multi"]:
            caption = {"title": b["tense"], "subtitle": "", "verb": ""}
            columns = [verb(v) for v in b["verbs"]]
        else:
            caption = verb(b["verb"])
            columns = [{"title": h, "subtitle": "", "verb": ""} for h in b["header"]]
        return {"type": "verbs", "caption": caption, "columns": columns,
                "rows": [{"label": r["label"], "forms": [{"text": c["form"], "inferred": c["inferred"]} for c in r["cells"]]}
                         for r in b["rows"]]}
    raise ValueError(f"grammar block of unknown kind {kind!r}")


def grammar(book):
    return [{"id": c["id"], "number": c["number"], "italian": c["title_it"], "english": c["title_en"],
             "blocks": [block(b) for b in c["blocks"]]} for c in book["chapters"]]


def build():
    books = {"dictionary": dictionary_model.load(), "expressions": expressions_model.load(),
             "verbs": verbs_model.load(), "grammar": grammar_model.load()}
    missing = [name for name, book in books.items() if book is None]
    if missing:
        sys.exit(f"no model for {', '.join(missing)}: run step4_build_pages.py first")
    return {"version": VERSION, "edition": time.strftime("%Y%m%d%H%M"),
            "dictionary": dictionary(books["dictionary"]), "verbs": verbs(books["verbs"]),
            "expressions": expressions(books["expressions"]), "grammar": grammar(books["grammar"])}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=str(PATH), help=f"where to write the JSON (default {PATH})")
    out = ap.parse_args().out
    data = build()
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"App data: {len(data['dictionary'])} words, {len(data['verbs'])} verbs, "
          f"{sum(len(s['entries']) for t in data['expressions'] for s in t['sections'])} expressions, "
          f"{len(data['grammar'])} grammar chapters -> {out}")


if __name__ == "__main__":
    main()
