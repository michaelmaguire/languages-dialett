"""Typographic quotes in the text this project writes (typesetting review, owner, 2026-10-31).

The English, the notes, the grammar's explanations (Italian and English) and ATTRIBUTIONS.md use curly
quotes and the apostrophe ’, never straight ' or ". The course's own dialect and Italian are left as the
teacher wrote them (straight apostrophes, spaces before ? and !, "…." included), so they are not checked.
pipeline/typography.py smart() makes the conversion."""
import csv
import re
from pathlib import Path

from conftest import ETC, ROOT, report

FIELDS = {"english_translations.csv": ["english"], "decisions.csv": ["English"], "notes.csv": ["Note", "Note_English"],
          "words_from_texts.csv": ["English"], "dialect_lists_italian_supplied.csv": ["english"],
          "topics.csv": ["Name_English"], "grammar_examples.csv": ["English"]}


def test_no_straight_quotes_in_our_text():
    bad = []
    for name, cols in FIELDS.items():
        with open(ETC / name, encoding="utf-8", newline="") as f:
            for n, row in enumerate(csv.DictReader(f), 2):
                bad += [f"etc/{name}:{n} {c}: {row[c][:60]!r}" for c in cols if re.search(r"['\"]", row.get(c) or "")]
    for path in sorted((ETC / "grammar").glob("*.md")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith(("IT:", "EN:")) and re.search(r"['\"]", line):
                bad.append(f"etc/grammar/{path.name}:{n}: {line[:60]!r}")
    protect = re.compile(r"`[^`]*`|\]\([^)]*\)|<!--.*?-->|<[^>]+>")
    for n, line in enumerate(Path(ROOT / "ATTRIBUTIONS.md").read_text(encoding="utf-8").splitlines(), 1):
        if re.search(r"['\"]", protect.sub("", line)):
            bad.append(f"ATTRIBUTIONS.md:{n}: {line[:60]!r}")
    report(bad, "straight quotes in text we write (use pipeline/typography.py smart())")


def test_smart_quotes():
    import sys
    sys.path.insert(0, str(ROOT / "pipeline"))
    from typography import smart
    cases = {"people's": "people’s", "All Souls' Day": "All Souls’ Day", 'the "to whom"': "the “to whom”",
             "'when are you going?'": "‘when are you going?’", "l'è": "l’è", '"Are you hungry?" — "Always."':
             "“Are you hungry?” — “Always.”"}
    report([f"{k!r} -> {smart(k)!r}, not {v!r}" for k, v in cases.items() if smart(k) != v], "smart() wrong")
