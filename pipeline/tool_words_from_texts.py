#!/usr/bin/env python3
"""Find dictionary words in the course's line-by-line translations (owner, 2026-10-28).

The dictionary takes its words from pairs a document gives one to one (il freddo / al frecc). Words that
only ever occur inside translated sentences (tardi, quand, indua) never reach it. This tool lists them,
for review in a Claude session; the reviewed words go in ../etc/words_from_texts.csv, which the build reads.

    .venv/bin/python tool_words_from_texts.py list [--min N]   # write ../raw/extracted/words_todo.csv
    .venv/bin/python tool_words_from_texts.py merge FILE        # add the reviewed words to etc/

FILE has one tab-separated line per word kept: n (the row of words_todo.csv), headword, part of speech,
gender, plural, feminine, (unused), Italian, English. Gender, plural and feminine may be blank (predicted);
a plural or feminine is given only where the texts show it. Each word cites the first line of the
documents where it occurs; words already in etc/words_from_texts.csv or in the dictionary are left out.

For each dialect word form of the canonical sentence pairs that the dictionary has in no form (headword,
spelling, feminine, plural, verb form), used at least N times (default 3): how often, a suggested Italian
word (the word of the teacher's translation that looks most alike: sctrada -> strada), and up to three
sentence pairs with their document and line. The list quotes the documents, so it is written to the private
raw/ submodule, never to this repository.
"""
import argparse, csv, difflib, re, sys, unicodedata
from collections import Counter, defaultdict

from paths import CLDF, ETC, PRIVATE, extraction

OUT = ETC / "words_from_texts.csv"
FIELDS = ["Language_ID", "Form", "Part_Of_Speech", "Gender", "Plural", "Feminine", "Italian", "English",
          "Source", "Line", "Reason", "Date"]

WORD = re.compile(r"[^\W\d_]+")


def plain(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if not unicodedata.combining(c))


def words(text):
    return WORD.findall(text.lower().replace("’", " ").replace("'", " "))


def known_forms():
    """Every form the dictionary already has, accents ignored."""
    out = set()
    split = lambda s: (plain(w) for w in re.split(r"[\s/,()]+", s or "") if w)
    for e in csv.DictReader((CLDF / "entries.csv").open(encoding="utf-8")):
        if e["Status"] != "rejected":
            for col in ("Headword", "Feminine", "Plural"):
                out.update(split(e.get(col)))
    for name in ("variants.csv", "paradigms.csv"):
        for r in csv.DictReader((CLDF / name).open(encoding="utf-8")):
            out.update(split(r["Form"]))
    return out


def suggest(form, italian):
    """The word of the Italian sentence most like the dialect form, if any is alike enough."""
    best, score = "", 0.0
    for w in words(italian):
        s = difflib.SequenceMatcher(None, plain(form), plain(w)).ratio()
        if s > score:
            best, score = w, s
    return (best, round(score, 2)) if score >= 0.6 else ("", round(score, 2))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["list", "merge"])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--min", type=int, default=3, help="list forms used at least this many times")
    args = ap.parse_args()
    if not (PRIVATE / "extracted_pairs.csv").exists():
        sys.exit("needs the full extraction in raw/extracted/ (the raw/ submodule)")
    known = known_forms()
    if args.command == "merge":
        return merge(args.file, known)
    pairs = [p for p in csv.DictReader(extraction("extracted_pairs.csv").open(encoding="utf-8"))
             if p["canonical"] == "yes" and p["kind"] == "expression"]
    count, seen = Counter(), defaultdict(list)
    for p in pairs:
        for w in words(p["dialect"]):
            if len(w) < 3 or plain(w) in known:
                continue
            count[plain(w)] += 1
            seen[plain(w)].append((w, p))
    out = PRIVATE / "words_todo.csv"
    rows = []
    for n, (form, c) in enumerate(sorted(((f, c) for f, c in count.items() if c >= args.min),
                                         key=lambda x: (-x[1], x[0])), 1):
        written = Counter(w for w, _ in seen[form]).most_common(1)[0][0]
        guesses = Counter(suggest(w, p["italian"])[0] for w, p in seen[form])
        guesses.pop("", None)
        row = {"n": n, "form": written, "count": c,
               "suggested_italian": " / ".join(g for g, _ in guesses.most_common(2))}
        for i, (w, p) in enumerate(seen[form][:3], 1):
            row[f"dialect_{i}"], row[f"italian_{i}"] = p["dialect"], p["italian"]
            row[f"where_{i}"] = f"{p['source']}|{p['line']}"
        rows.append(row)
    fields = ["n", "form", "count", "suggested_italian"] + [f"{k}_{i}" for i in (1, 2, 3)
                                                            for k in ("dialect", "italian", "where")]
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} forms used at least {args.min} times and not in the dictionary -> {out}")


def merge(path, known):
    import datetime
    todo = {r["n"]: r for r in csv.DictReader((PRIVATE / "words_todo.csv").open(encoding="utf-8"))}
    genre = {r["file"]: (r.get("genre") or "").strip()
             for r in csv.DictReader((ETC / "lesson_sources.csv").open(encoding="utf-8"))}
    rows = list(csv.DictReader(OUT.open(encoding="utf-8"))) if OUT.exists() else []
    have = {plain(r["Form"]) for r in rows}
    added, skipped = 0, []
    for line in open(path, encoding="utf-8"):
        if not line.strip():
            continue
        f = (line.rstrip("\n").split("\t") + [""] * 9)[:9]
        n, form, pos, gender, plural, fem, _, italian, english = (x.strip() for x in f)
        if plain(form) in have or plain(form) in known:
            skipped.append(form)
            continue
        # cite a line of the teacher's own sheets where there is one, rather than of a story or article
        wheres = [todo[n][f"where_{i}"] for i in (1, 2, 3) if todo[n].get(f"where_{i}")]
        source, _, ln = next((w for w in wheres if genre.get(w.partition("|")[0]) != "text"), wheres[0]).partition("|")
        rows.append({"Language_ID": "rogn", "Form": form, "Part_Of_Speech": pos, "Gender": gender,
                     "Plural": plural, "Feminine": fem, "Italian": italian, "English": english,
                     "Source": source, "Line": ln, "Date": datetime.date.today().isoformat(),
                     "Reason": f"Claude inferred: aligned with the teacher's Italian in {todo[n]['count']} "
                               "translated sentences"})
        have.add(plain(form))
        added += 1
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"added {added} words to {OUT}" + (f"; already there: {', '.join(skipped)}" if skipped else ""))


if __name__ == "__main__":
    main()
