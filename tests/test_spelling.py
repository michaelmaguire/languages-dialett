"""Canadian English spelling (owner, 2026-10-31: all stored and generated English in Canadian English).

Checked: the CLDF data (cldf/*.csv: the English is the same text as the pages') and every generated page,
README.md and ATTRIBUTIONS.md. The 2026-10-31 review found mum, maths, programme, learnt, tyres, cosy,
draught, -ise endings (organised, globalisation, recognised) and fixed them in etc/ and the templates.
Word choice (biscuit, rubbish) is not checked, only spelling (owner, same day). Code spans and URLs are
skipped (a CSS `color`, a folder named color)."""
import re

from conftest import CLDF, ROOT, report

# not Canadian -> Canadian. Canadian English: -our, -re, -ize, -yze, doubled l (travelled), grey, cheque,
# licence (noun), defence; but program, tire, math, mom, learned, cozy, draft
WRONG = {
    "color": "colour", "colors": "colours", "colored": "coloured", "favorite": "favourite", "favor": "favour",
    "behavior": "behaviour", "neighbor": "neighbour", "honor": "honour", "flavor": "flavour", "humor": "humour",
    "labor": "labour", "center": "centre", "centered": "centred", "theater": "theatre", "meter": "metre",
    "meters": "metres", "kilometer": "kilometre", "liter": "litre", "fiber": "fibre", "gray": "grey",
    "catalog": "catalogue", "defense": "defence", "offense": "offence", "traveled": "travelled",
    "traveling": "travelling", "traveler": "traveller", "canceled": "cancelled", "labeled": "labelled",
    "jewelry": "jewellery", "mold": "mould", "pajamas": "pyjamas", "mustache": "moustache",
    "programme": "program", "programmes": "programs", "tyre": "tire", "tyres": "tires", "aluminium": "aluminum",
    "analyse": "analyze", "analysed": "analyzed", "whilst": "while", "learnt": "learned", "spelt": "spelled",
    "maths": "math", "mum": "mom", "mums": "moms", "cosy": "cozy", "draught": "draft", "sceptical": "skeptical",
}
# British -ise words: Canadian spelling is -ize (but advise, surprise, exercise … are -ise everywhere)
ISE = re.compile(r"\b(organis|recognis|realis|apologis|specialis|summaris|emphasis|prioritis|criticis|"
                 r"memoris|categoris|characteris|normalis|capitalis|mobilis|globalis|authoris|unauthoris|"
                 r"civilis|finalis|minimis|maximis|utilis|symbolis|standardis|visualis|personalis|"
                 r"modernis|optimis|familiaris|sympathis|harmonis|colonis|fertilis|sterilis|stabilis)"
                 r"(e|ed|es|ing|ation|ations|er|ers)\b", re.I)
KNOWN = {"mum's the word", "mum’s the word"}          # an idiom (keep quiet), not a mother


def english_of(text):
    text = re.sub(r"`[^`]*`|https?://\S+|\]\([^)]*\)", " ", text)
    for k in KNOWN:
        text = text.replace(k, "")
    return text


def test_canadian_spelling():
    files = sorted(CLDF.glob("*.csv")) + [ROOT / "README.md", ROOT / "ATTRIBUTIONS.md"]
    for folder in ("Dictionary", "Expressions", "Verbs", "Grammar"):
        files += sorted((ROOT / folder).glob("*.md"))
    bad = []
    for f in files:
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            line = english_of(line)
            for w in re.findall(r"[A-Za-z]+", line):
                if w.lower() in WRONG:
                    bad.append(f"{f.relative_to(ROOT)}:{n}: {w} -> {WRONG[w.lower()]}")
            for m in ISE.finditer(line):
                bad.append(f"{f.relative_to(ROOT)}:{n}: {m.group(0)} -> -iz-")
    report(bad, "spellings that are not Canadian")
