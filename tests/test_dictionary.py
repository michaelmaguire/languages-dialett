"""The dictionary look-ups (Dictionary/*.md and the dictionary PDF)."""
import re

import pytest

from conftest import DICT, ETC, DATA, build, headword, lookup_rows, pdf_pages, read_csv, report

PAGES = ["dialett.md", "italiano.md", "english.md"]
LOOKUP = {"italian": ("italiano.md", "Italiano"), "english": ("english.md", "English")}


@pytest.mark.parametrize("lang", ["english", "italian"])
def test_every_translation_word_is_a_headword(lang):
    """viagg means 'journey, trip': both journey and trip are English headwords (owner, 2026-10-29).
    Every word of every translation on the Dialett page is a headword of that language's look-up."""
    page, col = LOOKUP[lang]
    heads = {headword(r["_head"]) for r in lookup_rows(page)}
    missing = []
    for r in lookup_rows("dialett.md"):
        if "(= " in r["_head"]:
            continue                                   # an alternate spelling's line: its entry is checked
        for sense in r["_senses"][col]:
            if not sense or sense.startswith("["):
                continue
            for w in build.split_translation(sense, verb=lang == "english" and sense.startswith("to ")):
                if build.key(w) not in heads:
                    missing.append(f"{w!r} (from {r['_head'][:40]!r})")
    report(missing, f"words of a translation with no headword on {page}")


@pytest.mark.parametrize("page", PAGES)
def test_no_row_without_translation(page):
    """Every sense of every row has its Italian and its English (the cross-reference lines too:
    'cumün (= comün)' once had neither, owner 2026-10-28)."""
    bad = []
    for r in lookup_rows(page):
        head_col = next(iter(r))                      # the look-up language: one headword per row
        if not r["_head"].strip():
            bad.append(f"empty headword in section {r['_section']}")
        for c in ("Dialett", "Italiano", "English"):
            if c != head_col and any(not s.strip() for s in r["_senses"][c]):
                bad.append(f"{r['_head'][:50]!r}: no {c}")
    report(bad, f"rows with a missing translation on {page}")


@pytest.mark.parametrize("page", PAGES)
def test_no_repeated_sense(page):
    """A row never shows the same sense twice (rügà once had 'mescolare' twice, 2026-10-28)."""
    bad = []
    for r in lookup_rows(page):
        cols = [c for c in ("Dialett", "Italiano", "English") if c in r]
        senses = list(zip(*(r["_senses"][c] for c in cols)))
        dup = {s for s in senses if senses.count(s) > 1}
        if dup:
            bad.append(f"{r['_head'][:40]!r}: {min(dup)}")
    report(bad, f"rows repeating a sense on {page}")


def test_no_double_arrow():
    """Each line of the PDF has one arrow between headword and translations ('cumün → → comün', 2026-10-28)."""
    bad = [l.strip() for p in pdf_pages("Dictionary/arogno-dictionary.pdf") for l in p.splitlines()
           if re.search(r"→\s*→", l)]
    bad += [f"{page}: {l[:80]}" for page in PAGES for l in (DICT / page).read_text().splitlines() if re.search(r"→\s*→", l)]
    report(bad, "lines with a double arrow")


def test_alternate_spellings_have_their_own_line():
    """Every spelling in etc/spelling_variants.csv can be looked up: it is a headword, or it has an
    'alt (= main)' line with the main entry's senses, or it differs from a headword only by accents or a
    doubled letter (it then sorts next to it; owner 2026-10-15)."""
    rows = lookup_rows("dialett.md")
    heads = {}
    for r in rows:
        for f in re.split(r"\s+/\s+|\s+o\s+", re.sub(r"\s*\*.*$", "", r["_head"])):
            heads.setdefault(build.key(f.replace("†", "").strip()), r)
    refs = {build.key(r["_head"].split(" (= ")[0]): r for r in rows if " (= " in r["_head"]}
    near = {build.same_letters(h) for h in heads}
    bad = []
    for v in read_csv(ETC / "spelling_variants.csv"):
        forms = [f.strip() for f in [v["Headword"]] + v["Variants"].split(";") if f.strip()]
        for f in forms:
            k = build.key(f)
            if k in heads or k in refs or build.same_letters(f) in near:
                if k in refs:
                    main = build.key(refs[k]["_head"].split(" (= ")[1].rstrip(")"))
                    m = heads.get(main)
                    if m and set(refs[k]["_senses"]["Italiano"]) - set(m["_senses"]["Italiano"]):
                        bad.append(f"{f!r}: senses differ from {main!r}")
                continue
            bad.append(f"{f!r} ({';'.join(forms)}) cannot be looked up")
    report(bad, "alternate spellings")


def word_classes():
    """Part of speech of every dialect headword, from pipeline/data/dictionary.csv."""
    out = {}
    for w in read_csv(DATA / "dictionary.csv"):
        out.setdefault(build.key(w["dialect"]), set()).add(w["pos"])
    return out


def test_homographs_keep_each_part_of_speech():
    """A noun and an adjective written alike stay two senses with two labels (frecc, owner 2026-10-28)."""
    classes = word_classes()
    labels = {"noun": "n.", "adjective": "adj.", "verb": "v.", "adverb": "adv."}
    bad = []
    for r in lookup_rows("dialett.md"):
        k = headword(r["_head"])
        for pos in classes.get(k, set()) & set(labels):
            if f"*{labels[pos]}" not in r["_head"]:
                bad.append(f"{r['_head'][:60]!r}: no {labels[pos]} label")
    report(bad, "homographs missing a part of speech")


def test_adjectives_show_both_genders():
    """Every adjective is shown masculine/feminine (bagnaa/bagnada; owner 2026-10-28), unless
    etc/parts_of_speech.csv says it has none ('-'). The adjective of a homograph row (frecc, noun and
    adjective) shows it too."""
    none = {build.key(r.get("Headword") or r.get("Form") or "") for r in read_csv(ETC / "parts_of_speech.csv")
            if (r.get("Feminine") or "").strip() == "-"}
    adjectives = {build.key(w["dialect"]): w for w in read_csv(DATA / "dictionary.csv") if w["pos"] == "adjective"}
    shown = {}
    for r in lookup_rows("dialett.md"):
        if "*adj." in r["_head"] or " *adj.*" in r["_head"]:
            shown[headword(r["_head"].split("/")[0])] = r["_head"]
    bad = []
    for k, w in adjectives.items():
        if k in none or not w["feminine"] and k in none:
            continue
        row = next((r["_head"] for r in lookup_rows("dialett.md") if headword(r["_head"]) == k
                    or headword(r["_head"]).split("/")[0] == k), None)
        if row is None:
            continue                                   # another region's word, merged: checked elsewhere
        if w["feminine"] and w["feminine"] != "-" and build.key(w["feminine"]) not in build.key(row):
            bad.append(f"{w['dialect']!r}: feminine {w['feminine']!r} not shown in {row[:60]!r}")
    report(bad, "adjectives without their feminine")


def test_nouns_show_gender_and_plural():
    """Every noun shows its gender and plural: 'purcel n. m., pl. purcei' (owner, 2026-10-15)."""
    bad = []
    for r in lookup_rows("dialett.md"):
        for label in re.findall(r"\*(n\.[^*]*)\*", r["_head"]):
            if not re.match(r"n\. [mf]\., pl\. \S", label):
                bad.append(f"{r['_head'][:60]!r}")
    report(bad, "nouns without gender or plural")


# the five verb headwords that are not infinitives, so they have no forms to show (step 5 lists them too)
NOT_INFINITIVE = {"taass", "vann", "punda giò", "sgraffirala", "ciapàr = take myself"}


def test_verbs_show_three_forms():
    """Every verb shows infinitive, 1st person singular and participle: 'truà v. (trövi, truaa)'
    (owner, 2026-10-28)."""
    bad = []
    for r in lookup_rows("dialett.md"):
        for label in re.findall(r"\*(v\.[^*]*)\*", r["_head"]):
            if headword(r["_head"]) in NOT_INFINITIVE:
                continue
            if not re.match(r"v\. \(.+, .+\)$", label):
                bad.append(f"{r['_head'][:60]!r}")
    report(bad, "verbs without their 1st singular and participle")


def test_no_doubled_to():
    """English verbs are 'to …' once ('to to arrive', 2026-10-28)."""
    bad = [f"{p}: {l[:80]}" for p in PAGES for l in (DICT / p).read_text().splitlines() if re.search(r"\bto to\b", l)]
    report(bad, "lines with 'to to'")


@pytest.mark.parametrize("page", ["italiano.md", "english.md"])
def test_lookup_gives_the_rogn_word(page):
    """Looking up from Italian or English, another region's word is left out when Rögn has the same word
    (owner, 2026-10-14): a row never mixes Rögn with other regions."""
    bad = []
    for r in lookup_rows(page):
        regions = r["_senses"]["Region"]
        if "Rögn" in regions and any(x != "Rögn" for x in regions):
            bad.append(f"{r['_head'][:40]!r}: {regions}")
    report(bad, f"rows mixing Rögn with other regions on {page}")


def test_readme_counts_match_pages():
    """Dictionary/README.md counts the entries of dictionary.csv and the rows of each look-up page."""
    text = (DICT / "README.md").read_text()
    counts = dict(re.findall(r"\[(\w+)\]\(\w+\.md\) \| [^|]+ \| (\d+)", text))
    n_entries = len(read_csv(DATA / "dictionary.csv"))
    bad = []
    if int(counts.get("Dialett", -1)) != n_entries:
        bad.append(f"Dialett: README says {counts.get('Dialett')}, dictionary.csv has {n_entries}")
    report(bad, "counts that do not match")


def test_every_entry_has_a_part_of_speech():
    """Every dictionary entry in cldf/ has a part of speech (owner, 2026-10-29; until then the build only
    warned). Nouns get it from their article, table verbs from their table, the rest from
    etc/parts_of_speech.csv or etc/words_from_texts.csv."""
    from conftest import CLDF
    bad = [f"{e['Headword']!r} ({e['Language_ID']})" for e in read_csv(CLDF / "entries.csv")
           if e["Status"] != "rejected" and not e["Part_Of_Speech"]]
    report(bad, "entries without a part of speech")


def test_curation_rows_all_match():
    """Every row of etc/ that names an entry matches one: the build's 'matched no entry' warnings are
    failures here (a renamed headword left 'ungia / unghie: uncc' behind in parts_of_speech.csv, 2026-10-29)."""
    import subprocess
    import sys
    from conftest import ROOT
    r = subprocess.run([sys.executable, "step3_make_cldf.py"], cwd=ROOT / "pipeline", capture_output=True,
                       text=True, check=False)
    bad = [line.strip() for line in (r.stdout + r.stderr).splitlines()
           if "matched no" in line or "matched nothing" in line]
    report(bad, "curation rows that match nothing")
