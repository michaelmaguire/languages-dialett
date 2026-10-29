"""The dictionary as one structure, which both the Markdown pages and the PDF are rendered from (owner,
2026-10-29). Every decision about what the dictionary shows is made here, once: which entries each look-up
lists, under which headword, in what order, which senses merge into one headword, and how each form and label
is written (daggers, feminines, parts of speech). The renderers only lay it out: step4_build_pages.py
writes the Markdown, step5_build_pdfs.py fills templates/dictionary.html.j2. Until then each built its own
look-ups, and fixes had to be made twice (the double arrow, the homograph labels of frecc).

    book = build(words)            # words: the dictionary rows of lexicon.for_pages()
    book["parts"][0]               # Dialett → Italiano → English
        ["sections"][0]            # the letter A ("#" last: entries with no word to sort on)
            ["entries"][0]         # one headword: head, words, flag, notes, no_word
                ["senses"][0]      # dialect, label, italian, english, region, note, source, check, new_word

Saved by step 4 as pipeline/cache/dictionary_model.json (not committed: rebuilt on every build), which
step 5 and the tests read.
"""
import json

import step4_build_pages as pages

PATH = pages.HERE / "cache" / "dictionary_model.json"

# head: the column looked up; lang: the language of the labels (n./s., adj./agg.) and learner's notes;
# others: the columns that tell senses apart when merging (merge_same_head)
PARTS = [
    {"head": "dialect", "lang": "en", "others": ["italian", "english"],
     "title": "Dialett → Italiano → English", "pdf_title": "Dialett → Italiano · English", "no_word": "Other"},
    {"head": "italian", "lang": "it", "others": ["dialect", "english"],
     "title": "Italiano → Dialett → English", "pdf_title": "Italiano → Dialett · English", "no_word": "No Italian yet"},
    {"head": "english", "lang": "en", "others": ["dialect", "italian"],
     "title": "English → Dialett → Italiano", "pdf_title": "English → Dialett · Italiano", "no_word": "No English yet"},
]


def sort_key(head):
    """The text a row is sorted on, and its first letter decides its section."""
    if head == "dialect":
        return lambda p: pages.DI_ARTICLE.sub("", pages.key(p["dialect"]))
    if head == "italian":
        return lambda p: "" if p["italian"].startswith("[") else pages.bare(p["italian"])
    return lambda p: pages.EN_ARTICLE.sub("", p["english"])


def order(rows, head):
    """Rows in look-up order. Ties: by spelling (pero before però); in English, the Rögn word first, then
    the dialect alphabetically, and entries with no English last."""
    k = sort_key(head)
    if head == "english":
        return sorted(rows, key=lambda p: (not p["english"], pages.plain(k(p)), p["canonical"] != "yes",
                                           pages.plain(p["dialect"])))
    return sorted(rows, key=lambda p: (pages.plain(k(p)), k(p)))


def rows_for(words, head):
    """The rows a look-up lists: every entry, plus a line for each alternate spelling in the Dialett one
    (cross_references); in Italian and English, each entry under every word of its translation (lookup_rows)."""
    if head == "dialect":
        return words + pages.cross_references(words)
    return pages.lookup_rows(words, head)


def sense(p, part):
    lang = part["lang"]
    return {"dialect": pages.dialect_shown(p), "label": pages.word_label(p, lang), "pos": p.get("pos") or "",
            "italian": p["italian"] + (pages.INFERRED if p.get("supplied") else ""),
            "english": p["english"], "region": pages.region(p), "note": p["note"],
            "entry_note": p.get("entry_note_en" if lang == "en" else "entry_note", ""),
            "source": p["source"], "check": bool(p["check"])}


def entry(group, part):
    """One headword and its senses (several when a word has several meanings or regional forms)."""
    head = part["head"]
    senses = [sense(p, part) for p in group]
    first = senses[0]
    for s in senses:
        # a homograph's later part of speech is a new word, with its own forms and label (frecc, the noun,
        # then frecc/frecia, the adjective)
        s["new_word"] = bool(head == "dialect" and s is not first and s["label"]
                             and (s["pos"], s["dialect"]) != (first["pos"], first["dialect"]))
    raw = group[0][head]
    return {"head": first["dialect"] if head == "dialect" else first[head],
            # the words of a Dialett headword: each form with its label, once ('frecc n. m., pl. frecc',
            # 'frecc/frecia adj.')
            "words": list(dict.fromkeys(s["dialect"] + (f" *{s['label']}*" if s["label"] else "") for s in senses)),
            "flag": first["check"],
            # each sense's own comment, then the word's learner's note once
            "notes": [n for n in dict.fromkeys([s["note"] for s in senses] + [s["entry_note"] for s in senses]) if n],
            "no_word": not raw or raw.startswith("["),
            "senses": senses}


def part_model(words, part):
    head, k = part["head"], sort_key(part["head"])
    rows = order(rows_for(words, head), head)
    letters = {}
    for p in rows:
        first = (pages.plain(k(p)) or "#")[0].upper()
        letters.setdefault(first if first.isalpha() else "#", []).append(p)
    names = sorted(x for x in letters if x != "#") + (["#"] if "#" in letters else [])
    sections = []
    for name in names:
        group = letters[name]
        merged = pages.merge_same_head([p for p in group if p[head]], head, part["others"], pages.region) \
            + [[p] for p in group if not p[head]]
        sections.append({"letter": name, "name": part["no_word"] if name == "#" else name,
                         "entries": [entry(g, part) for g in merged]})
    return {**{x: part[x] for x in ("head", "lang", "title", "pdf_title")}, "rows": len(rows),
            "blank": sum(not p[head] for p in rows), "sections": sections}


def build(words):
    return {"words": len(words), "flagged": sum(bool(p["check"]) for p in words),
            "parts": [part_model(words, part) for part in PARTS]}


def save(book):
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(book, ensure_ascii=False, indent=1))


def load():
    return json.loads(PATH.read_text()) if PATH.exists() else None


def entries(book, head):
    """Every entry of one look-up, in order."""
    part = next(p for p in book["parts"] if p["head"] == head)
    return [e for s in part["sections"] for e in s["entries"]]

