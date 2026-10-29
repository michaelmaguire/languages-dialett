"""The expressions as one structure, which both the Markdown pages and the PDF are rendered from (owner,
2026-10-30; as dictionary_model.py for the dictionary). Decided here, once: the topics and their order, the
split into sayings and phrases, the merging of a text found in several documents (one row, every source),
the order (by the dialect, without its article) and what each row shows. step4_build_pages.py writes one
Markdown page per topic; step5_build_pdfs.py fills templates/expressions.html.j2.

    book = build(exprs, topics)    # exprs: the expression rows of lexicon.for_pages(); topics: cldf/topics.csv
    book["topics"][0]              # id, title, file, name_dialect, name, name_english
        ["sections"][0]            # genre (saying | phrase), title_it, title_en
            ["entries"][0]         # dialect, italian, english, region, check, sources

Lines of texts (genre `text`) are in no topic and appear in neither output (owner, 2026-10-14).
Saved by step 4 as pipeline/cache/expressions_model.json (not committed), which step 5 and the tests read.
"""
import json

import step4_build_pages as pages

PATH = pages.HERE / "cache" / "expressions_model.json"
SECTIONS = [("saying", pages.SAYINGS), ("phrase", pages.PHRASES)]


def entry(p):
    return {"dialect": p["dialect"], "italian": p["italian"], "english": p["english"],
            "region": pages.region(p), "check": bool(p["check"]), "sources": p["sources"]}


def topic(t, rows):
    sections = []
    for genre, (title_it, title_en) in SECTIONS:
        part = [p for p in rows if (p["genre"] == "saying") == (genre == "saying")]
        sections.append({"genre": genre, "title_it": title_it, "title_en": title_en,
                         "entries": [entry(p) for p in pages.merge_expressions(part)]})
    return {"id": t["ID"], "title": pages.topic_title(t), "file": pages.topic_file(t),
            "name_dialect": t.get("Name_Dialect") or "", "name": t["Name"], "name_english": t["Name_English"],
            "sections": sections}


def build(exprs, topics):
    by_topic, texts = pages.expression_groups(exprs, topics)    # sorted by the dialect; texts left out
    names = {t["ID"]: t for t in topics}
    book = {"topics": [topic(names[tid], rows) for tid, rows in by_topic.items()],
            # counts for the README and the build summary: pairs before merging, distinct texts per topic
            "pairs": sum(len(v) for v in by_topic.values()),
            "distinct": sum(len(pages.merge_expressions(v)) for v in by_topic.values()),
            "texts": len(texts), "text_lines": sum(len(v) for v in texts.values())}
    for genre in ("saying", "phrase"):
        book[genre + "s"] = sum(len(s["entries"]) for t in book["topics"] for s in t["sections"] if s["genre"] == genre)
    return book


def save(book):
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(book, ensure_ascii=False, indent=1))


def load():
    return json.loads(PATH.read_text()) if PATH.exists() else None
