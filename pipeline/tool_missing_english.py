#!/usr/bin/env python3
"""List the Italian entries that have no English yet, or merge translations back in.

  tool_missing_english.py list  [word|expression]   -> prints  id<TAB>italian
  tool_missing_english.py merge FILE                -> FILE has id<TAB>english lines; appended to etc/english_translations.csv

etc/english_translations.csv (italian,english) is the permanent store: step4_build_pages.py looks every entry up in it,
so a translation is only ever needed once.
"""
import csv, sys
from pathlib import Path
import step4_build_pages as build

from paths import ETC, CACHE

TODO = CACHE / "missing_english_todo.csv"


def missing(kind=None):
    eng, _ = build.load_english()
    seen, out = set(), []
    from paths import extraction
    for p in build.read(extraction("extracted_pairs.csv")):
        k = build.key(p["italian"])
        if (kind and p["kind"] != kind) or k in seen or k in eng or build.bare(p["italian"]) in eng:
            continue
        seen.add(k)
        out.append(p["italian"])
    return out


if sys.argv[1] == "list":
    rows = missing(sys.argv[2] if len(sys.argv) > 2 else None)
    with TODO.open("w", newline="") as f:
        csv.writer(f).writerows(enumerate(rows))
    for i, it in enumerate(rows):
        print(f"{i}\t{it}")
elif sys.argv[1] == "merge":
    todo = dict(csv.reader(TODO.open()))
    new = 0
    with (ETC / "english_translations.csv").open("a", newline="") as f:
        w = csv.writer(f)
        for line in Path(sys.argv[2]).read_text().splitlines():
            i, _, en = line.partition("\t")
            if en.strip() and i.strip() in todo:
                w.writerow([build.key(todo[i.strip()]), en.strip()])
                new += 1
    print(f"added {new} translations to etc/english_translations.csv")
