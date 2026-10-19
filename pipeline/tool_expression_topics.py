#!/usr/bin/env python3
"""List the expressions that have no topic yet, or merge topics back in.

  tool_expression_topics.py list          -> prints  n<TAB>italian<TAB>dialect, and the topic IDs to choose from
  tool_expression_topics.py merge FILE    -> FILE has n<TAB>topic lines (topic = an ID from etc/topics.csv);
                                             appended to etc/expression_topics.csv

Reads the dataset in ../cldf, so run it after a build. Texts (genre `text`) are read in order and need no
topic. To give one expression a genre of its own (a proverb in a phrase list), set the Genre column of its
row in etc/expression_topics.csv by hand.
"""
import csv, sys
from pathlib import Path

import lexicon
from paths import ETC, CACHE

TODO = CACHE / "expression_topics_todo.csv"


def missing():
    _, rows = lexicon.load()
    return [x for x in rows["examples.csv"]
            if x["Status"] != "rejected" and x["Genre"] not in ("text", "grammar") and not x["Topic_ID"]]


if sys.argv[1] == "list":
    rows = missing()
    with TODO.open("w", newline="") as f:
        csv.writer(f).writerows([i, x["Language_ID"], x["Primary_Text"]] for i, x in enumerate(rows))
    for i, x in enumerate(rows):
        print(f"{i}\t{x['Translated_Text']}\t{x['Primary_Text']}")
    print("topics: " + ", ".join(t["ID"] for t in lexicon.topics()), file=sys.stderr)
elif sys.argv[1] == "merge":
    todo = {i: (language, form) for i, language, form in csv.reader(TODO.open())}
    known = {t["ID"] for t in lexicon.topics()}
    new = 0
    with (ETC / "expression_topics.csv").open("a", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        for line in Path(sys.argv[2]).read_text().splitlines():
            i, _, topic = line.partition("\t")
            topic = topic.strip()
            if i.strip() in todo and topic in known:
                w.writerow([*todo[i.strip()], topic, ""])
                new += 1
            elif line.strip():
                print(f"skipped: {line!r} (unknown number or topic)")
    print(f"added {new} topics to etc/expression_topics.csv")
