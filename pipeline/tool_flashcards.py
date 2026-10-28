#!/usr/bin/env python3
"""Anki flashcards (an .apkg file) from the CLDF dataset: English → Dialett and Dialett → English.

    .venv/bin/python tool_flashcards.py OUT.apkg [--decks words,verbs,expressions] [--verbs pagare,essere]
                                                 [--inferred]

Decks (all by default), each card in both directions:
  words        every dictionary entry with English, from every region (the region is on the card and in
               the tags); nouns show gender and plural (m., pl. purcei), spelling variants are on the back
  verbs        one card per verb form: "to pay · ti · futuro" ↔ "ta pagaré". Only forms found in a course
               document unless --inferred, which adds the predicted (†) forms, marked and tagged `inferred`
  expressions  sayings and phrases with English, one sub-deck per topic (as on the Expressions pages)

Every note's id comes from its CLDF ID, so a rebuilt deck imported again updates the cards already in Anki
(corrections, new English) and keeps their review history. Reads ../cldf only; writes only OUT.apkg.
"""
import argparse, csv, re, sys, zlib
from collections import defaultdict
from pathlib import Path

try:
    import genanki
except ImportError:
    sys.exit("needs genanki: .venv/bin/pip install -r requirements.txt")

from paths import ROOT

CLDF = ROOT / "cldf"
ROOT_DECK = "Dialett da Rögn"
PERSONS = {"1s": "mi", "2s": "ti", "3s": "le / lü", "1p": "nüm", "2p": "vialtri", "3p": "lur", "-": ""}
TENSE_ORDER = ["presente", "imperfetto", "passato prossimo", "trapassato prossimo", "futuro", "futuro prossimo",
               "condizionale presente", "condizionale passato", "congiuntivo presente", "congiuntivo imperfetto",
               "imperativo", "imperativo negativo", "gerundio", "participio passato"]

CSS = """
.card { font-family: "DejaVu Sans", Arial, sans-serif; font-size: 22px; text-align: center; color: #111; background: #fff; }
.night_mode .card { color: #eee; background: #222; }
.di { font-weight: bold; font-size: 28px; }
.g { font-style: italic; font-size: 18px; color: #555; }
.night_mode .g, .night_mode .info { color: #aaa; }
.info { font-size: 15px; color: #666; margin-top: 14px; line-height: 1.5; }
.r { font-size: 14px; letter-spacing: .05em; text-transform: uppercase; color: #8a5a00; }
"""

FIELDS = [{"name": n} for n in ("English", "Dialett", "Grammar", "Region", "Italian", "Also", "Source")]
BACK_INFO = ('<div class="info">{{#Also}}also: {{Also}}<br>{{/Also}}{{#Italian}}it. {{Italian}}<br>{{/Italian}}'
             '{{Source}}</div>')
# model ids are fixed: Anki recognises the card types on every re-import
MODEL = genanki.Model(
    1607392319, "Dialett da Rögn (English ↔ Dialett)", fields=FIELDS, css=CSS,
    templates=[
        {"name": "English → Dialett",
         "qfmt": '{{English}}{{#Region}}<div class="r">{{Region}}</div>{{/Region}}',
         "afmt": '{{FrontSide}}<hr id="answer"><div class="di">{{Dialett}}</div>'
                 '{{#Grammar}}<div class="g">{{Grammar}}</div>{{/Grammar}}' + BACK_INFO},
        {"name": "Dialett → English",
         "qfmt": '<div class="di">{{Dialett}}</div>{{#Region}}<div class="r">{{Region}}</div>{{/Region}}',
         "afmt": '{{FrontSide}}<hr id="answer">{{English}}'
                 '{{#Grammar}}<div class="g">{{Grammar}}</div>{{/Grammar}}' + BACK_INFO},
    ])


def note(key, english, dialett, grammar="", region="", italian="", also="", source="", tags=()):
    """guid from the CLDF ID, not from the text: a corrected card replaces the old one in Anki."""
    return genanki.Note(model=MODEL, fields=[english, dialett, grammar, region, italian, also, source],
                        tags=[re.sub(r"\s+", "_", t) for t in tags if t], guid=genanki.guid_for(key))


def read(name):
    return list(csv.DictReader((CLDF / name).open())) if (CLDF / name).exists() else []


def deck(name):
    full = f"{ROOT_DECK}::{name}"
    return genanki.Deck(zlib.crc32(full.encode()) % (1 << 30) + (1 << 30), full)      # fixed id per name


def region_names():
    return {r["ID"]: re.sub(r"^Lombard:\s*", "", r["Name"]) for r in read("languages.csv")}


def source_names():
    names = {c["ID"]: c["Name"] for c in read("contributions.csv")}
    def cite(refs):
        out = []
        for ref in (refs or "").split(";"):
            m = re.match(r"([^\[]+)(?:\[l\.(\d+)\])?", ref.strip())
            if m and m.group(1):
                out.append(names.get(m.group(1), m.group(1)) + (f", l. {m.group(2)}" if m.group(2) else ""))
        return "; ".join(dict.fromkeys(out))
    return cite


def words(regions, cite):
    E = [e for e in read("entries.csv") if e["Status"] not in ("rejected", "typo")]
    senses = defaultdict(list)
    for s in read("senses.csv"):
        if s["Status"] not in ("rejected", "typo") and s["Description_English"]:
            senses[s["Entry_ID"]].append(s)
    spellings = defaultdict(list)
    for v in read("variants.csv"):
        if v["Kind"] == "spelling" and v["Status"] == "accepted":
            spellings[v["Entry_ID"]].append(v["Form"])
    d = deck("Words")
    for e in E:
        mine = senses[e["ID"]]
        if not mine:
            continue
        english = "; ".join(dict.fromkeys(s["Description_English"] for s in mine))
        italian = "; ".join(dict.fromkeys(s["Description"] for s in mine))
        grammar = ""
        if e["Part_Of_Speech"] == "noun" and e["Gender"]:
            grammar = f"{e['Gender']}." + (f", pl. {e['Plural']}" if e["Plural"] else "")
        elif e["Part_Of_Speech"] == "verb":
            grammar = "verb"
        region = regions.get(e["Language_ID"], e["Language_ID"])
        # keyed on the entry's first sense, whose ID survives a corrected headword (the entry ID follows the headword)
        d.add_note(note(f"sense:{mine[0]['ID']}", english, e["Headword"], grammar, region, italian,
                        ", ".join(spellings[e["ID"]]), cite(e["Source"]),
                        ["word", e["Language_ID"], e["Part_Of_Speech"]]))
    return d


def verbs(only, inferred, cite):
    E = {e["ID"]: e for e in read("entries.csv") if e["Part_Of_Speech"] == "verb" and e["Status"] != "rejected"}
    english = {}
    for s in read("senses.csv"):
        if s["Entry_ID"] in E and s["Status"] != "rejected" and s["Description_English"]:
            english.setdefault(s["Entry_ID"], s["Description_English"])
    italian = {}
    for s in read("senses.csv"):
        if s["Entry_ID"] in E and s["Status"] != "rejected":
            italian.setdefault(s["Entry_ID"], s["Description"])
    if only:
        wanted = {i for i, it in italian.items() if it in only}
        missing = set(only) - {italian[i] for i in wanted}
        if missing:
            sys.exit(f"no verb for: {', '.join(sorted(missing))} (use the Italian infinitive)")
    d = deck("Verbs")
    rank = {t: i for i, t in enumerate(TENSE_ORDER)}
    rows = sorted(read("paradigms.csv"), key=lambda p: (p["Entry_ID"], rank.get(p["Tense"], 99), p["Person"]))
    for p in rows:
        e = E.get(p["Entry_ID"])
        if not e or (only and e["ID"] not in wanted) or p["Form"] in ("", "–"):
            continue
        guess = p["Status"] == "inferred"
        if guess and not inferred:
            continue
        person = PERSONS.get(p["Person"], p["Person"])
        cue = f"{english.get(e['ID'], italian.get(e['ID'], ''))} · {e['Headword']}<br>{p['Tense']}" + (f" · {person}" if person else "")
        d.add_note(note(f"verb:{p['ID']}", cue, p["Form"] + (" †" if guess else ""),
                        "† predicted from the course patterns, not found in a document" if guess else "",
                        "", italian.get(e["ID"], ""), "", cite(p["Source"]),
                        ["verb", e["Headword"], p["Tense"], "inferred" if guess else "attested"]))
    return d


def expressions(regions, cite):
    topics = {t["ID"]: t for t in read("topics.csv")}
    decks = {}
    for x in read("examples.csv"):
        if x["Status"] == "rejected" or not x["Topic_ID"] or not x["Translated_Text_English"]:
            continue
        t = topics.get(x["Topic_ID"], {})
        name = f"Expressions::{t.get('Name_English') or x['Topic_ID']}"
        d = decks.setdefault(name, deck(name))
        d.add_note(note(f"expr:{x['ID']}", x["Translated_Text_English"], x["Primary_Text"],
                        "saying" if x["Genre"] == "saying" else "", regions.get(x["Language_ID"], ""),
                        x["Translated_Text"], "", cite(x["Source"]),
                        ["expression", x["Genre"], x["Language_ID"], x["Topic_ID"]]))
    return list(decks.values())


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("out")
    ap.add_argument("--decks", default="words,verbs,expressions")
    ap.add_argument("--verbs", default="", help="Italian infinitives, comma-separated (default: all verbs)")
    ap.add_argument("--inferred", action="store_true", help="add the predicted (†) verb forms")
    a = ap.parse_args()
    regions, cite = region_names(), source_names()
    chosen = {d.strip() for d in a.decks.split(",")}
    decks = []
    if "words" in chosen:
        decks.append(words(regions, cite))
    if "verbs" in chosen:
        decks.append(verbs([v.strip() for v in a.verbs.split(",") if v.strip()], a.inferred, cite))
    if "expressions" in chosen:
        decks += expressions(regions, cite)
    out = Path(a.out).resolve()
    genanki.Package(decks).write_to_file(out)
    for d in decks:
        print(f"{d.name}: {len(d.notes)} notes, {2 * len(d.notes)} cards")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
