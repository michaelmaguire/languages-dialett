"""Build the CLDF dataset (../cldf) from raw/ and etc/, and read it back for the pages.

Called by cldfbench (../cldfbench_rogn.py, `cldfbench makecldf`) on every build, so the dataset is always
regenerated from the sources plus the curation in etc/. It is never edited by hand: a decision about a
row goes in etc/decisions.csv (see apply_decisions below and etc/README.md).
"""
import csv, re, unicodedata
from collections import defaultdict

from pycldf import Dataset, Source

import step4_build_pages as pages
import grammar
import noun_plurals
from paths import RAW, ETC, CLDF, DATA

METADATA = CLDF / "Dictionary-metadata.json"
DAGGER = " †"
TERMS = "http://cldf.clld.org/v1.0/terms.rdf#"

LOMBARD = ("lomb1257", "lmo")
LANGUAGES = [  # ID, Name, Glottocode, ISO 639-3, description, short label used on the pages
    ("rogn", "Lombard: Rögn (Arogno)", *LOMBARD, "The dialect of the course, Lugano district", "Rögn"),
    ("basso-ceresio", "Lombard: Basso Ceresio", *LOMBARD, "Gaggini's glossary", "Basso Ceresio"),
    ("mendrisiotto", "Lombard: Mendrisiotto", *LOMBARD, "", "Mendrisiotto"),
    ("lumino", "Lombard: Lumino (Bellinzonese)", *LOMBARD, "", "Lumino (Bellinzonese)"),
    ("giubiasco", "Lombard: Giubiasco", *LOMBARD, "", "Giubiasco"),
    ("lugano-old", "Lombard: Lugano, older printed texts", *LOMBARD, "Paul e Ghita a Lügan", "Lugano (old printed play)"),
    ("ticinese", "Lombard: Ticino, variety not identified", *LOMBARD, "Sources whose variety is not yet known", ""),
    ("ita", "Italian", "ital1282", "ita", "Meta-language: sense descriptions and translations", None),
    ("eng", "English", "stan1293", "eng", "Meta-language: added translations", None),
]
LABEL = {l[0]: l[5] for l in LANGUAGES}
VARIETY_OF = {"Rögn": "rogn", "Rögn (Arogno)": "rogn", "Basso Ceresio": "basso-ceresio",
              "Mendrisiotto": "mendrisiotto", "Lumino (Bellinzonese)": "lumino", "Giubiasco": "giubiasco",
              "Lugano (old printed play)": "lugano-old"}
AUTHORS = {  # as in ATTRIBUTIONS.md
    "Dizionario con filastrocche di R. Gaggini.docx": "Gaggini, Raffaele",
    "dialett-poesia-Spartaco-Arigoni.pdf": "Arigoni, Spartaco",
    "NUVANT'ANN.pdf": "Tantardini, Celso",
    "2025-02-19-Piove governo ladro di Fausto Boffi.docx": "Boffi, Fausto",
    "Filatrocca di Carlino.docx": "Delucchi, Mario",
    "GP Lavelli 2x.docx": "Lavelli, G. P.",
    "CDE_come_si_scrive_in_dialetto.pdf": "{Centro di dialettologia e di etnografia}",
}
STATUS = {
    "entries": "accepted|pending|inferred|rejected",
    "senses": "attested|supplied|confirmed|pending|rejected",
    "examples": "accepted|pending|rejected",
    "variants": "accepted|pending|typo|rejected",
    "paradigms": "attested|inferred|rejected",
}
UNSURE = {"direction?": "direction", "split?": "split", "pairing?": "pairing", "meaning?": "meaning"}
SUPPLIED_NOTE = "Italian and English supplied; the lesson gives the dialect only"
CONFIRMED_NOTE = "Italian and English supplied (the lesson gives the dialect only) and confirmed by the owner"
NO_ITALIAN_NOTE = "the source gives no Italian; the English is shown in brackets"
TABLE_OF = {"entries.csv": "EntryTable", "senses.csv": "SenseTable", "examples.csv": "ExampleTable",
            "languages.csv": "LanguageTable", "contributions.csv": "ContributionTable", "media.csv": "MediaTable"}
# What kind of expression a row is: set per document in etc/lesson_sources.csv (column genre), or per
# expression in etc/expression_topics.csv. Texts are read in order; the others are grouped by topic.
# `grammar`: the numbered examples of the grammar (etc/grammar_examples.csv), shown only there.
GENRES = ("phrase", "saying", "exercise", "text", "grammar")


def slug(text, limit=48):
    s = unicodedata.normalize("NFD", str(text).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:limit].strip("-") or "x"


class Ids:
    """Readable, unique IDs matching CLDF's [a-zA-Z0-9_-]+."""
    def __init__(self, used=()):
        self.used = set(used)

    def make(self, base):
        base, n = slug(base), 2
        out = base
        while out in self.used:
            out, n = f"{base}-{n}", n + 1
        self.used.add(out)
        return out


# ------------------------------------------------------------------ sources
def source_key(name):
    if name == "notes_added_by_hand.csv":
        return "owner-notes"
    if name.startswith("Rosetta Stone"):
        return "owner-spreadsheet"
    return slug(re.sub(r"\.(docx|pdf|txt)$", "", name), 60)


def bib_entry(name, lesson_meta):
    meta = lesson_meta.get(name, {})
    fields = {"title": re.sub(r"\.(docx|pdf|txt)$", "", name), "note": f"raw/{name}"}
    if name.startswith("Rosetta Stone"):
        fields["title"] = "Rosetta Stone: English, Italian, Ticino dialect (owner's own spreadsheet)"
    elif name == "notes_added_by_hand.csv":
        fields["title"] = "Vocabulary from the owner's handwritten course notes"
    elif meta.get("canonical") == "yes":
        fields.update(author="Casellini, Guido", howpublished="Cors da dialett da Rögn, course material")
    if name in AUTHORS:
        fields["author"] = AUTHORS[name]
    year = re.match(r"(20\d\d)-", name)
    if year:
        fields["year"] = year.group(1)
    return Source("misc", source_key(name), **fields)


def cite(name, line=None):
    k = source_key(name)
    return f"{k}[l.{line}]" if line not in (None, "", "0", 0) else k


# ------------------------------------------------------------------ candidates: what the lessons say today
def candidates():
    """Rows in CLDF shape, with provisional IDs, from everything steps 1-2 and etc/ provide."""
    uniq, tables, eng = pages.assemble()
    lesson_meta = {r["file"]: r for r in pages.read(ETC / "lesson_sources.csv")}
    files = set()
    ids = {t: Ids() for t in ("entries", "senses", "examples", "variants", "paradigms")}
    entries, senses, examples, variants, paradigms = {}, [], [], [], []
    by_key = {}

    def entry_for(headword, language, verb=False, **extra):
        # homographs stay apart: the verb `vert` (to open) is not the colour `vert` (green)
        k = (pages.key(headword), language, "verb" if verb else "")
        if k not in by_key:
            eid = ids["entries"].make(headword if language == "rogn" else f"{headword}-{language}")
            by_key[k] = eid
            entries[eid] = {"ID": eid, "Language_ID": language, "Headword": headword, "Part_Of_Speech": None,
                            "Variant_Of": None, "Conjugation_Class": None, "Auxiliary": None,
                            "Gender": None, "Plural": None, "Status": "accepted",
                            "Comment": None, "Source": []}
        e = entries[by_key[k]]
        for f, v in extra.items():
            if v:
                e[f] = v
        return e

    def add_source(row, ref):
        if ref not in row["Source"]:
            row["Source"].append(ref)

    # verbs first: they own their headwords
    verb_rows = pages.read(DATA / "extracted_verb_forms.csv")
    manual = {pages.key(r["italian"]): r for r in pages.read(ETC / "verb_details.csv")}
    seen_at = defaultdict(list)

    def as_shown(v):
        name = manual.get(pages.key(v["italian"]), {}).get("merge_into") or v["italian"]
        return pages.key(pages.shown_form(name, v["tense"], v["form"], manual))
    for v in verb_rows:
        seen_at[(v["tense"], v["person"], as_shown(dict(v, italian=v["verb_italian"])))].append(cite(v["source"], v["line"]))
        files.add(v["source"])
    confirmed = {}                                            # forms the owner has confirmed (no document)
    for v in pages.read(ETC / "verb_forms_from_texts.csv"):     # forms found in running text, where noted
        if v.get("source") and v.get("basis") == "attested":
            seen_at[(v["tense"], v["person"], as_shown(v))].append(cite(v["source"], v["line"]))
            files.add(v["source"])
        elif v.get("basis") == "confirmed":
            confirmed[(pages.key(v["italian"]), v["tense"], v["person"], as_shown(v))] = "confirmed by the owner"
    aux_essere = {pages.key(r["italian"]): r.get("aux") == "essere" for r in pages.read(ETC / "verb_details.csv")}
    for name in sorted(tables):
        t = tables[name]
        head = t["dialect"][0] if t["dialect"] else name
        grid = t["grid"]
        aux = "ves" if re.match(r"(ma )?(sum|ta se|l’è)\b", grid["passato prossimo"]["1s"][0]) else "vegh"
        if grid["passato prossimo"]["1s"][0] == "–":    # no compound tense to read it from: the general rule
            head_word = head.split()[0]
            aux = "ves" if aux_essere.get(pages.key(name)) or (head_word.endswith("ss") or
                                                                head_word.endswith("as") and len(head_word) > 3) else "vegh"
        e = entry_for(head, "rogn", verb=True, Part_Of_Speech="verb", Conjugation_Class=t["class"].split(":")[0],
                      Auxiliary=aux, Status="inferred" if t["basis"] == "inferred" else "accepted",
                      Comment=t.get("evidence") or None)
        for f in t["sources"]:
            add_source(e, cite(f))
            files.add(f)
        for form in t["dialect"][1:]:
            variants.append({"ID": ids["variants"].make(f"{e['ID']}-{form}"), "Entry_ID": e["ID"], "Form": form,
                             "Kind": "spelling", "Status": "accepted", "Comment": None, "Source": list(e["Source"])})
        for i, italian in enumerate([name] + t["aliases"]):
            en = eng.get(pages.key(italian))
            senses.append({"ID": ids["senses"].make(f"{e['ID']}-{italian}"), "Entry_ID": e["ID"],
                           "Description": italian, "Description_English": f"to {en}" if en else None,
                           "Status": "attested", "Unsure_About": None,
                           "Comment": f"Italian synonym of {name}" if i else None, "Source": list(e["Source"])})
        for tense in pages.ALL_TENSES:
            for person, (form, inferred) in grid[tense].items():
                if form == "–":
                    continue
                src = [] if inferred else sorted(set(seen_at.get((tense, person, pages.key(form)), [])))[:4]
                paradigms.append({"ID": ids["paradigms"].make(f"{e['ID']}-{tense}-{person}"), "Entry_ID": e["ID"],
                                  "Tense": tense, "Person": person if person != "-" else None, "Form": form,
                                  "Status": "inferred" if inferred else "attested",
                                  "Comment": None if inferred else confirmed.get((pages.key(name), tense, person, pages.key(form))),
                                  "Source": src})

    for p in uniq:
        files.add(p["source"])
        language = VARIETY_OF.get(p.get("variety") or "") or \
            VARIETY_OF.get(lesson_meta.get(p["source"], {}).get("variety", "")) or "ticinese"
        ref = cite(p["source"], p["line"])
        # a translation aligned with its Italian original (etc/parallel_texts.csv) cites both documents
        refs = [ref] + ([cite(p["italian_source"], p.get("italian_line"))] if p.get("italian_source") else [])
        if p.get("italian_source"):
            files.add(p["italian_source"])
        unsure = UNSURE.get(p["check"]) if p["check"] else None
        if p["kind"] == "expression":
            examples.append({"ID": ids["examples"].make(f"{p['source'][:24]}-{p['line']}"), "Language_ID": language,
                             "Primary_Text": unquote(p["dialect"]), "Translated_Text": unquote(p["italian"]),
                             "Meta_Language_ID": "ita", "Translated_Text_English": unquote(p["english"]) or None,
                             "Status": "pending" if unsure else "accepted", "Unsure_About": unsure,
                             "Comment": p["note"] or None, "Source": refs})
            continue
        # a word pair whose Italian is one of a verb's infinitives belongs to that verb ("andare = na")
        vk = (pages.key(p["dialect"]), language, "verb")
        verb_entry = entries.get(by_key.get(vk))
        is_verb_sense = verb_entry and any(s["Entry_ID"] == verb_entry["ID"] and pages.key(s["Description"]) ==
                                           pages.key(p["italian"]) for s in senses)
        e = verb_entry if is_verb_sense else entry_for(p["dialect"], language)
        if unsure:
            e["Status"] = "pending"
        add_source(e, ref)
        italian, missing = p["italian"], not p["italian"].strip()
        if missing:
            italian = f"[{p['english'] or '?'}]"             # "[?]": neither Italian nor English is known
        if any(s["Entry_ID"] == e["ID"] and pages.key(s["Description"]) == pages.key(italian) for s in senses):
            continue
        senses.append({"ID": ids["senses"].make(f"{e['ID']}-{italian}"), "Entry_ID": e["ID"], "Description": italian,
                       "Description_English": p["english"] or None,
                       "Status": ("confirmed" if p.get("confirmed") else "supplied") if p.get("supplied") else
                                 ("pending" if unsure or missing else "attested"),
                       "Unsure_About": unsure or ("meaning" if missing else None),     # meaning: no Italian given
                       "Comment": (CONFIRMED_NOTE if p.get("confirmed") else SUPPLIED_NOTE) if p.get("supplied") else (p["note"] or NO_ITALIAN_NOTE) if missing else (p["note"] or None),
                       "Source": [ref]})
    bib = [bib_entry(f, lesson_meta) for f in sorted(files)]
    return {"entries.csv": list(entries.values()), "senses.csv": senses, "examples.csv": examples,
            "variants.csv": variants, "paradigms.csv": paradigms}, bib


# ------------------------------------------------------------------ the dataset
def configure(ds):
    """Declare everything beyond the Dictionary module's defaults in the metadata: components, added
    columns, the allowed Status values and the foreign keys. ds is the writer's pycldf Dataset."""
    source = {"name": "Source", "propertyUrl": TERMS + "source", "separator": ";", "datatype": "string"}
    comment = {"name": "Comment", "propertyUrl": TERMS + "comment", "datatype": "string"}
    status = lambda t: {"name": "Status", "datatype": {"base": "string", "format": STATUS[t]}}
    unsure = {"name": "Unsure_About", "datatype": {"base": "string", "format": "direction|split|pairing|meaning"},
              "dc:description": "What the extraction was unsure about when it marked the row pending"}
    rid = {"name": "ID", "required": True, "propertyUrl": TERMS + "id",
           "datatype": {"base": "string", "format": "[a-zA-Z0-9_\\-]+"}}
    entry_ref = {"name": "Entry_ID", "required": True, "propertyUrl": TERMS + "entryReference"}
    form = {"name": "Form", "required": True, "propertyUrl": TERMS + "form"}
    ds.properties.update({
        "dc:title": "Lexicon of the dialect of Rögn (Arogno), Ticino",
        "dc:description": "Dialect entries, senses (Italian with English), examples and verb paradigms from "
                          "the course Cors da dialett da Rögn and related texts. See README.md.",
        "dc:creator": "Michael Maguire",
        "dc:contributor": "Guido Casellini (course material) and the other authors listed in ATTRIBUTIONS.md",
    })
    ds.add_component("LanguageTable", {"name": "Description", "propertyUrl": TERMS + "description", "datatype": "string"})
    ds.add_component("ExampleTable",
                     {"name": "Translated_Text_English", "datatype": "string",
                      "dc:description": "English translation, added; Translated_Text is the Italian"},
                     status("examples"), unsure, source)
    ds.add_columns("EntryTable",
                   {"name": "Variant_Of", "datatype": "string",
                    "dc:description": "ID of the main entry when this entry is a regional variant of it"},
                   {"name": "Conjugation_Class", "datatype": "string"},
                   {"name": "Gender", "datatype": {"base": "string", "format": "m|f"},
                    "dc:description": "Grammatical gender of a noun: m (masculine) or f (feminine). Not a CLDF term "
                                      "(CLDF has none for gender); from the article in the source, else the Italian, "
                                      "else etc/nouns.csv"},
                   {"name": "Plural", "datatype": "string",
                    "dc:description": "Plural of a noun. Not a CLDF term. From the source where it gives one, "
                                      "otherwise predicted from the course's patterns (corrections: etc/nouns.csv)"},
                   {"name": "Auxiliary", "datatype": {"base": "string", "format": "ves|vegh"}},
                   status("entries"), comment, source)
    ds.add_columns("SenseTable",
                   {"name": "Description_English", "datatype": "string",
                    "dc:description": "English translation of the Description, which is in Italian"},
                   status("senses"), unsure, comment, source)
    ds.add_columns("SenseTable",
                   {"name": "Example_IDs", "propertyUrl": TERMS + "exampleReference", "separator": ";",
                    "dc:description": "Expressions that use this word in this sense (found automatically: the "
                                      "dialect word in the expression and its Italian in the translation)"})
    # the TextCorpus pattern (https://github.com/cldf/cldf/tree/master/modules/TextCorpus): every expression
    # points to the document it comes from (a contribution) and its place there
    ds.add_component("ContributionTable",
                     {"name": "Genre", "datatype": {"base": "string", "format": "|".join(GENRES)},
                      "dc:description": "What the document mostly holds; an expression may override it"},
                     source)
    ds.add_table("topics.csv", rid,
                 {"name": "Name_Dialect", "datatype": "string",
                  "dc:description": "Rögn name of the topic, composed by Claude from words of the course; "
                                    "† marks a word not found in any course document"},
                 {"name": "Name", "required": True, "propertyUrl": TERMS + "name", "dc:description": "Italian name of the topic"},
                 {"name": "Name_English", "datatype": "string"}, primaryKey=["ID"])
    ds.add_columns("ExampleTable",
                   {"name": "Contribution_ID", "propertyUrl": TERMS + "contributionReference"},
                   {"name": "Position", "propertyUrl": TERMS + "position", "datatype": "integer",
                    "dc:description": "Line of the expression in its document (pipeline/cache/lesson_text)"},
                   {"name": "Genre", "datatype": {"base": "string", "format": "|".join(GENRES)}},
                   {"name": "Topic_ID", "dc:description": "What the expression is about (etc/expression_topics.csv); "
                                                         "blank for texts, which are read in order"})
    ds.add_foreign_key("ExampleTable", "Topic_ID", "topics.csv", "ID")
    # the grammar's chapters (CLDF Markdown, Italian and English side by side), copied to cldf/grammar/
    ds.add_component("MediaTable")
    ds.add_foreign_key("EntryTable", "Variant_Of", "EntryTable", "ID")
    ds.add_table("variants.csv", rid, entry_ref, form,
                 {"name": "Kind", "datatype": {"base": "string", "format": "spelling|typo|ocr-error|article"}},
                 status("variants"), comment, source, primaryKey=["ID"])
    ds.add_table("paradigms.csv", rid, entry_ref, {"name": "Tense", "required": True},
                 {"name": "Person", "datatype": {"base": "string", "format": "1s|2s|3s|1p|2p|3p"}},
                 form, status("paradigms"), comment, source, primaryKey=["ID"])


QUOTED = re.compile(r'^\s*([«“"])([^«»“”"]*)([»”"])\s*$')


def unquote(text):
    """'«Dài, ta spéci l’ann che vegn!»' -> 'Dài, ta spéci l’ann che vegn!': quotation marks around a whole
    expression add nothing (most are written without). Quotes inside the text are kept."""
    m = QUOTED.match(text or "")
    return m.group(2).strip() if m else text


def fold_entry(rows, e, target, kind, status, note, vids, same=None):
    """Fold entry e into target: its sources, senses and variants move over, and e's headword is kept in
    variants.csv with the given Kind and Status. A sense the target already has (same(description) equal)
    is kept but rejected as a duplicate."""
    S, V = rows["senses.csv"], rows["variants.csv"]
    same = same or pages.key
    target["Source"] = list(dict.fromkeys((target["Source"] or []) + (e["Source"] or [])))
    have = {same(s["Description"]) for s in S if s["Entry_ID"] == target["ID"]}
    for s in S:
        if s["Entry_ID"] == e["ID"]:
            if same(s["Description"]) in have:
                s["Status"], s["Comment"] = "rejected", f"duplicate of a sense of {target['ID']}"
            s["Entry_ID"] = target["ID"]
    for v in V:
        if v["Entry_ID"] == e["ID"]:
            v["Entry_ID"] = target["ID"]
    twin = next((v for v in V if v["Entry_ID"] == target["ID"] and pages.key(v["Form"]) == pages.key(e["Headword"])), None)
    if twin:                                                   # the target already has this form: add the sources
        twin["Source"] = list(dict.fromkeys((twin["Source"] or []) + (e["Source"] or [])))
        twin["Comment"] = twin["Comment"] or note
    elif pages.key(e["Headword"]) != pages.key(target["Headword"]):   # moved to another variety unchanged: no new form
        V.append({"ID": vids.make(f"{target['ID']}-{e['Headword']}"), "Entry_ID": target["ID"], "Form": e["Headword"],
                  "Kind": kind, "Status": status, "Comment": note, "Source": e["Source"]})
    rows["entries.csv"].remove(e)


# ------------------------------------------------------------------ nouns
# A dialect article at the start of a headword: ul/un, la/na, l'/un, l'/n', al, la, i ... (the lesson tables
# write nouns with both articles to show the gender).
ARTICLE = re.compile(r"^(?:(?:al|ul|el|la|i|un|na|una)(?:/(?:un|na|una|n['’]))?\s+|l['’](?:/(?:n['’]|una?\s+))?\s*|['‘’][ln]\s+)", re.I)
GENDER_OF_ARTICLE = {"al": "m", "ul": "m", "el": "m", "un": "m", "'l": "m", "'n": "m", "l'/un": "m",
                     "la": "f", "na": "f", "una": "f", "l'/n'": "f", "l'/una": "f"}
IT_GENDER = re.compile(r"^(?:(?P<m>il|lo|un|uno|i|gli)|(?P<f>la|una|le|un['’]))(?:/\S+)?\s", re.I)
EN_ARTICLE = re.compile(r"^(?:the/an?|the|an?)\s+", re.I)
PLURAL_NOTE = re.compile(r"^i\s+([^;]+?)\s*(?:;\s*(.+))?$")          # lesson 6 notes: 'i purcei', 'i gai; canta'


def _article_gender(article):
    a = re.sub(r"\s+", "", article.lower()).replace("’", "'")
    return GENDER_OF_ARTICLE.get(a) or GENDER_OF_ARTICLE.get(a.split("/")[0])


def _strip_articles(form):
    """'al bagat / al sciavatin' -> 'bagat / sciavatin': the article off each alternative."""
    rest = ARTICLE.sub("", form, count=1)                       # the leading pair first: 'ul/un piöcc'
    return " / ".join(ARTICLE.sub("", part).strip() for part in re.split(r"\s*/\s*(?=\S)", rest))


def noun_forms(rows):
    """Nouns get their bare citation form as headword, with Part_Of_Speech 'noun', a Gender and a Plural.

    A leading article is the article of a noun when it is a pair (ul/un, la/na: never a clitic) or when one
    of the senses' Italian starts with an article too; otherwise it is a clitic and the headword is left
    alone ('al piöf' = piove: 'al' is the subject clitic of the verb). The gender comes from the article
    (ul, al, un: m; la, na: f), or for an article that does not show it (l', i) from the Italian. The plural
    comes from the headword ('al tecc / i tecc', 'la poma – i pomm') or a lesson 6 note ('i purcei').
    etc/nouns.csv marks further nouns (bare headwords) and overrides gender and plural. The original form
    stays in variants.csv as Kind `article`; entries that become the same word are merged (a Ticinese
    entry into the Rögn one when the two differed only by the article: 'piöcc' and 'ul/un piöcc').
    Runs after the decisions, so a decision always applies to the entry it names. Returns a summary."""
    E, S, V = rows["entries.csv"], rows["senses.csv"], rows["variants.csv"]
    vids = Ids(v["ID"] for v in V)
    curated = {(r["Language_ID"], pages.key(r["Form"])): r for r in pages.read(ETC / "nouns.csv")}
    senses = defaultdict(list)
    for x in S:
        if x["Status"] != "rejected":
            senses[x["Entry_ID"]].append(x)
    stripped, used = set(), set()
    for e in E:
        if e["Status"] == "rejected" or e["Part_Of_Speech"] == "verb":
            continue
        mine = senses[e["ID"]]
        cur = curated.get((e["Language_ID"], pages.key(e["Headword"])))
        m = ARTICLE.match(e["Headword"])
        if m and not ("/" in m.group(0) or cur or any(pages.IT_ARTICLE.match(x["Description"]) for x in mine)):
            m = None                                             # a clitic, not an article
        if m and re.match(r"[èéaà]\b", e["Headword"][m.end():]):
            m = None                                             # "l'è sofic", "l'a ...": clitic + verb
        if not (m or cur):
            continue
        if cur:
            used.add((e["Language_ID"], pages.key(e["Headword"])))
        original = e["Headword"]
        rest, plural = original, None
        pm = re.match(r"^(.*?\S)\s*(?:/|–|-)\s*i\s+(\S.*)$", original)
        if pm and ARTICLE.match(original):                       # 'al tecc / i tecc', 'la poma – i pomm'
            rest, plural = pm.group(1), pm.group(2).strip()
        rest = _strip_articles(rest) if m else rest
        if cur and cur.get("Plural"):                            # 'curtel/curtei', 'sedèla (sedèl)': the plural is not the headword
            singular = re.sub(rf"\s*(?:/|\()\s*{re.escape(cur['Plural'])}\s*\)?$", "", rest) or rest
            if singular != rest:                                 # and 'coltello/coltelli' has its plural too
                for x in mine:
                    for k in ("Description", "Description_English"):
                        if x.get(k) and x[k].count("/") == 1:
                            x[k] = x[k].split("/")[0].strip()
            rest = singular
        gender = _article_gender(m.group(0)) if m else None
        if not gender:
            g = next((IT_GENDER.match(x["Description"] + " ") for x in mine if IT_GENDER.match(x["Description"] + " ")), None)
            gender = (g and ("m" if g.group("m") else "f")) or None
        for x in mine:
            note = PLURAL_NOTE.match(x["Comment"] or "")
            if note and m:
                plural, x["Comment"] = plural or note.group(1).strip(), note.group(2)
            if m and pages.IT_ARTICLE.match(x["Description"]):
                x["Description"] = re.split(r"\s+[–-]\s+", pages.IT_ARTICLE.sub("", x["Description"]))[0].strip()
                if x["Description_English"]:
                    x["Description_English"] = re.split(r"\s+[–-]\s+", EN_ARTICLE.sub("", x["Description_English"]))[0].strip()
        if cur:
            gender = cur.get("Gender") or gender
            plural = cur.get("Plural") or plural
        e.update(Headword=rest, Part_Of_Speech="noun", Gender=gender, Plural=plural)
        if pages.key(rest) != pages.key(original):
            V.append({"ID": vids.make(f"{e['ID']}-{original}"), "Entry_ID": e["ID"], "Form": original,
                      "Kind": "article", "Status": "accepted", "Comment": "the form written in the source",
                      "Source": e["Source"]})
            stripped.add(e["ID"])

    # entries that are now the same word
    bare_it = lambda d: pages.plain(pages.bare(d or ""))
    groups = defaultdict(list)
    for e in E:
        if e["Status"] != "rejected" and e["Part_Of_Speech"] != "verb":
            groups[pages.key(e["Headword"])].append(e)
    merged = []
    for group in groups.values():
        group.sort(key=lambda e: (e["Language_ID"] != "rogn", e["ID"] not in stripped, e["ID"]))
        target = group[0]
        for e in group[1:]:
            if e["Language_ID"] == target["Language_ID"] or e["ID"] in stripped or target["ID"] in stripped:
                for k in ("Gender", "Plural", "Part_Of_Speech"):
                    target[k] = target.get(k) or e.get(k)
                fold_entry(rows, e, target, "article", "accepted",
                           f"the same word as {target['Headword']} (merged automatically)", vids, same=bare_it)
                merged.append((e["Headword"], target["Headword"]))
    # every noun gets a plural: the source's, else etc/nouns.csv's, else predicted (noun_plurals.py)
    predicted = 0
    for e in E:
        if e.get("Part_Of_Speech") == "noun" and not e.get("Plural"):
            e["Plural"], predicted = noun_plurals.predict(e["Headword"], e.get("Gender")), predicted + 1
    unused = [r["Form"] for k, r in curated.items() if k not in used]
    return {"nouns": sum(e.get("Part_Of_Speech") == "noun" for e in E), "stripped": len(stripped),
            "predicted": predicted,
            "merged": merged, "unused": unused}


def renumber_entries(rows):
    """IDs follow the headword ([a-zA-Z0-9_-]+, CLDF): after noun_forms() 'ul-un-piocc' becomes 'piocc'.
    References (senses, variants, paradigms, Variant_Of) follow."""
    E = rows["entries.csv"]
    ids = Ids()
    new = {}
    for e in sorted(E, key=lambda e: (e["Language_ID"] != "rogn", e["ID"])):
        base = e["Headword"] if e["Language_ID"] == "rogn" else f"{e['Headword']}-{e['Language_ID']}"
        if e["Part_Of_Speech"] == "verb":
            base = e["ID"]                                       # verb IDs name the verb pages: unchanged
        new[e["ID"]] = ids.make(base)
    for e in E:
        e["ID"] = new[e["ID"]]
        if e.get("Variant_Of"):
            e["Variant_Of"] = new.get(e["Variant_Of"], e["Variant_Of"])
    for t in ("senses.csv", "variants.csv", "paradigms.csv"):
        for r in rows.get(t, []):
            r["Entry_ID"] = new.get(r["Entry_ID"], r["Entry_ID"])


def apply_decisions(rows, decisions):
    """Apply etc/decisions.csv. One row per decision:

      Decision        typo | reject | accept | variant | correct
      Language_ID     variety of the form the decision is about (e.g. rogn, ticinese)
      Form            the headword as it appears in the data, or for an expression its dialect text
      Sense           optional: the Italian of one sense of the entry, to limit the decision to it
      Target_Form     typo/variant: the correct or main headword; correct: the corrected dialect
      Target_Language_ID   typo/variant: the variety the target belongs to, if different
      Italian, English     correct: the corrected Italian and English (blank = unchanged)
      Reason, Date    recorded in the Comment of the rows affected ("Claude inferred: …" when the
                      decision came from Claude's review rather than from the owner)

    typo     the form's entry is folded into the target entry (created if needed), and the form is kept
             in variants.csv with Kind and Status `typo`, so it is recognised but never shown.
    reject   the entry (or with Sense, that sense; or the expression) gets Status `rejected` and the
             reason; the pages leave it out.
    accept   a `pending` entry and its pending senses (or the expression) become accepted / attested.
    variant  same variety: the form becomes an accepted spelling in variants.csv of the target entry;
             other variety: the form's entry gets Variant_Of = the target entry, or if the target does
             not exist yet, is folded into a new target entry with the form kept as a spelling.
    correct  replaces the dialect, Italian and/or English of an entry's sense (all of them, or the one
             named in Sense) or of an expression, and marks it accepted.
    expression  the entry is an idiom, a saying or a sentence rather than a word: it leaves the dictionary
             and becomes an expression (examples.csv), its senses joined as the translation.
    Expressions (examples.csv) can be rejected, accepted or corrected; Form is then their dialect text.
    Returns the decisions that matched nothing, so they can be reported.
    """
    E, S, V, X = rows["entries.csv"], rows["senses.csv"], rows["variants.csv"], rows["examples.csv"]
    ids = Ids(e["ID"] for e in E)
    xids = Ids(x["ID"] for x in X)
    vids = Ids(v["ID"] for v in V)
    unmatched = []
    key = pages.key

    def find(form, language):
        return next((e for e in E if key(e["Headword"]) == key(form) and e["Language_ID"] == language), None)

    def find_example(form, language):
        return next((x for x in X if key(x["Primary_Text"]) == key(form) and x["Language_ID"] == language), None)

    for d in decisions:
        note = "; ".join(x for x in (d.get("Reason"), d.get("Date") and f"decided {d['Date']}") if x)
        kind = d["Decision"].strip().lower()
        e = find(d["Form"], d["Language_ID"])
        if e is None:
            x = find_example(d["Form"], d["Language_ID"]) if kind in ("reject", "accept", "correct") else None
            if x is None:
                unmatched.append(d)
            elif kind == "reject":
                x["Status"], x["Comment"] = "rejected", note
            else:                                         # the expression's own note stays as the page note
                x["Status"], x["Unsure_About"] = "accepted", None
                if kind == "correct":
                    for field, col in (("Primary_Text", "Target_Form"), ("Translated_Text", "Italian"),
                                       ("Translated_Text_English", "English")):
                        if (d.get(col) or "").strip():
                            x[field] = d[col].strip()
            continue
        mine = [s for s in S if s["Entry_ID"] == e["ID"]]
        if kind == "expression":
            live = [s for s in mine if s["Status"] != "rejected"] or mine
            english = [s["Description_English"] for s in live if s["Description_English"]]
            X.append({"ID": xids.make(e["ID"]), "Language_ID": e["Language_ID"], "Primary_Text": e["Headword"],
                      "Translated_Text": "; ".join(s["Description"] for s in live), "Meta_Language_ID": "ita",
                      "Translated_Text_English": "; ".join(english) or None,
                      "Status": "pending" if e["Status"] == "pending" else "accepted",
                      "Unsure_About": next((s["Unsure_About"] for s in live if s["Unsure_About"]), None)
                      if e["Status"] == "pending" else None,
                      "Comment": next((s["Comment"] for s in live if s["Comment"] and s["Comment"] not in
                                       (SUPPLIED_NOTE, NO_ITALIAN_NOTE)), None),
                      "Source": list(e["Source"] or [])})
            E.remove(e)
            S[:] = [s for s in S if s["Entry_ID"] != e["ID"]]
            V[:] = [v for v in V if v["Entry_ID"] != e["ID"]]
            continue
        if (d.get("Sense") or "").strip():
            mine = [s for s in mine if key(s["Description"]) == key(d["Sense"])]
            if not mine:
                unmatched.append(d)
                continue
        if kind == "reject" and (d.get("Sense") or "").strip():
            for s in mine:
                s["Status"], s["Comment"] = "rejected", note
        elif kind == "reject":
            e["Status"], e["Comment"] = "rejected", note
        elif kind == "accept":
            e["Status"], e["Comment"] = "accepted", note or e["Comment"]
            for s in mine:
                if s["Status"] == "pending":
                    s["Status"] = "attested"
        elif kind == "correct":
            if (d.get("Target_Form") or "").strip():
                e["Headword"] = d["Target_Form"].strip()
            e["Status"], e["Comment"] = "accepted", note
            for s in mine:
                if (d.get("Italian") or "").strip():
                    s["Description"] = d["Italian"].strip()
                    if s["Comment"] == NO_ITALIAN_NOTE:
                        s["Comment"] = None
                if (d.get("English") or "").strip():
                    s["Description_English"] = d["English"].strip()
                s["Status"], s["Unsure_About"] = "attested", None
        elif kind in ("typo", "variant"):
            language = d.get("Target_Language_ID") or d["Language_ID"]
            target = find(d["Target_Form"], language)
            if kind == "variant" and target and language != d["Language_ID"]:
                e["Variant_Of"], e["Comment"] = target["ID"], note
                continue
            if target is None:
                target = dict(e, ID=ids.make(d["Target_Form"] if language == "rogn" else f"{d['Target_Form']}-{language}"),
                              Headword=d["Target_Form"], Language_ID=language, Source=[], Comment=None)
                E.append(target)
            fold_entry(rows, e, target, "typo" if kind == "typo" else "spelling",
                       "typo" if kind == "typo" else "accepted", note, vids)
        else:
            unmatched.append(d)
    return unmatched


def make(writer):
    """cldfbench's cmd_makecldf: fill the writer with the whole dataset."""
    configure(writer.cldf)
    rows, bib = candidates()
    unmatched = apply_decisions(rows, pages.read(ETC / "decisions.csv"))
    nouns = noun_forms(rows)
    renumber_entries(rows)
    missing_spellings = add_spellings(rows)
    unsorted = place_examples(rows, bib)
    lesson_meta = {r["file"]: r for r in pages.read(ETC / "lesson_sources.csv")}
    grammar_warnings = grammar.cldf_rows(rows, bib, cite, bib_entry, lesson_meta, writer.cldf_spec.dir)
    link_examples(rows)
    writer.cldf.add_sources(*bib)
    writer.objects["LanguageTable"] = [{"ID": i, "Name": n, "Glottocode": g, "ISO639P3code": iso, "Description": d}
                                       for i, n, g, iso, d, _ in LANGUAGES]
    for url, rs in rows.items():
        # topics keep the order of etc/topics.csv, which is the order of the pages
        writer.objects[TABLE_OF.get(url, url)] = rs if url == "topics.csv" else sorted(rs, key=lambda r: r["ID"])
    print(f"cldf: {len(rows['entries.csv'])} entries, {len(rows['senses.csv'])} senses, "
          f"{len(rows['examples.csv'])} examples, {len(rows['variants.csv'])} variants, "
          f"{len(rows['paradigms.csv'])} paradigm cells, {len(bib)} sources, "
          f"{len(rows['contributions.csv'])} contributions, {len(rows['topics.csv'])} topics")
    linked = [s for s in rows["senses.csv"] if s["Example_IDs"]]
    print(f"  {len(linked)} senses linked to {len({x for s in linked for x in s['Example_IDs']})} expressions")
    for r in missing_spellings:
        print(f"  WARNING: spelling variant row matched no entry: {r['Language_ID']} {r['Headword']!r}")
    print(f"  {nouns['nouns']} nouns ({nouns['stripped']} headwords lost their article, "
          f"{nouns['predicted']} plurals predicted); "
          f"{len(nouns['merged'])} entries merged into the same word: "
          + "; ".join(f"{a} -> {b}" for a, b in nouns["merged"]))
    for form in nouns["unused"]:
        print(f"  WARNING: etc/nouns.csv row matched no entry: {form!r}")
    for d in unmatched:
        print(f"  WARNING: decision matched nothing: {d['Decision']} {d['Language_ID']} {d['Form']!r}")
    for t in unsorted["topics"]:
        print(f"  WARNING: expression topic matched nothing: {t['Language_ID']} {t['Form']!r}")
    n_grammar = sum(x["Genre"] == "grammar" for x in rows["examples.csv"])
    print(f"  grammar: {len(rows.get('media.csv', []))} chapters, {n_grammar} glossed examples")
    for w in grammar_warnings:
        print(f"  WARNING: {w}")
    if unsorted["examples"]:
        print(f"  {len(unsorted['examples'])} expressions have no topic yet: add them to etc/expression_topics.csv "
              f"(tool_expression_topics.py list)")


def add_spellings(rows):
    """etc/spelling_variants.csv: other spellings of an entry that the lessons use (giò, giô, giõ). All are
    accepted, none is preferred: each goes into variants.csv with Kind and Status spelling/accepted, and the
    dictionary shows them together. Returns the rows that matched no entry."""
    E, V = rows["entries.csv"], rows["variants.csv"]
    ids, missing = Ids(v["ID"] for v in V), []
    for r in pages.read(ETC / "spelling_variants.csv"):
        matches = [e for e in E if pages.key(e["Headword"]) == pages.key(r["Headword"]) and e["Language_ID"] == r["Language_ID"]]
        if not matches:
            missing.append(r)
        for e in matches:                      # homographs (vert, to open / green) share the spellings
            have = {pages.key(v["Form"]) for v in V if v["Entry_ID"] == e["ID"]} | {pages.key(e["Headword"])}
            for form in (f.strip() for f in r["Variants"].split(";")):
                if form and pages.key(form) not in have:
                    V.append({"ID": ids.make(f"{e['ID']}-{form}"), "Entry_ID": e["ID"], "Form": form, "Kind": "spelling",
                              "Status": "accepted", "Comment": r.get("Evidence") or None, "Source": list(e["Source"] or [])})
    return missing


def place_examples(rows, bib):
    """The TextCorpus side of the dataset: one contribution per document that has expressions, each
    expression's place in it (Contribution_ID, Position), its genre and its topic.
    Returns what could not be placed: topic rows that matched nothing and expressions with no topic."""
    meta = {source_key(r["file"]): r for r in pages.read(ETC / "lesson_sources.csv")}
    titles = {b.id: b for b in bib}
    topics = pages.read(ETC / "topics.csv")
    rows["topics.csv"] = [{"ID": t["ID"], "Name_Dialect": t.get("Name_Dialect") or None, "Name": t["Name"],
                           "Name_English": t["Name_English"] or None} for t in topics]
    known = {t["ID"] for t in topics}
    given = {}
    for t in pages.read(ETC / "expression_topics.csv"):
        given[(t["Language_ID"], pages.key(unquote(t["Form"])))] = t
    used, unsorted, contributions = set(), [], {}
    for x in rows["examples.csv"]:
        m = re.match(r"([^\[]+)(?:\[l\.(\d+)\])?", (x["Source"] or [""])[0])
        cid, line = m.group(1), m.group(2)
        doc_genre = (meta.get(cid, {}).get("genre") or "").strip()
        doc_genre = doc_genre if doc_genre in GENRES else "phrase"
        if cid not in contributions:
            b = titles.get(cid)
            contributions[cid] = {"ID": cid, "Name": b["title"] if b else cid, "Description": None,
                                  "Contributor": (b.get("author") if b else None) or None, "Citation": None,
                                  "Genre": doc_genre, "Source": [cid] if b else []}
        t = given.get((x["Language_ID"], pages.key(x["Primary_Text"])))
        if t:
            used.add((t["Language_ID"], pages.key(unquote(t["Form"]))))
        genre = (t or {}).get("Genre", "").strip() or doc_genre
        topic = (t or {}).get("Topic", "").strip() or None
        if topic and topic not in known:
            raise SystemExit(f"etc/expression_topics.csv: unknown topic {topic!r} for {x['Primary_Text']!r}")
        x.update({"Contribution_ID": cid, "Position": int(line) if line else None, "Genre": genre,
                  "Topic_ID": None if genre == "text" else topic})
        if genre != "text" and not topic and x["Status"] != "rejected":
            unsorted.append(x)
    rows["contributions.csv"] = list(contributions.values())
    return {"examples": unsorted, "topics": [t for k, t in given.items() if k not in used]}


WORD = re.compile(r"[^\W\d_]+")
# particles of verbs such as turnà indré, nà föra: shared by many verbs, so not evidence for any one
PARTICLES = {"indré", "indrè", "föra", "fora", "giò", "giõ", "giü", "sü", "via", "dent", "denta", "scià", "innanz", "inanz"}


def link_examples(rows):
    """Sense -> expressions that use it (Example_IDs). A Rögn word is linked to an expression when the
    expression has the word (or, for a verb, one of its forms) and its Italian translation has a word
    starting like the sense's Italian ("mangi-" for mangiare, "pomodor-" for pomodoro). Requiring both
    sides keeps the links fairly safe; short words (under four letters) and verb particles (indré, föra)
    are not used."""
    tokens = lambda s: set(WORD.findall((s or "").lower().replace("’", "'")))
    examples = [(x["ID"], tokens(x["Primary_Text"]), tokens(x["Translated_Text"]))
                for x in rows["examples.csv"] if x["Status"] != "rejected" and x["Language_ID"] == "rogn"
                and x.get("Genre") != "grammar"]
    forms = defaultdict(set)
    for p in rows["paradigms.csv"]:
        last = p["Form"].split("/")[0].split()
        if last:
            forms[p["Entry_ID"]].add(last[-1].lower())
    for v in rows["variants.csv"]:
        if v["Status"] == "accepted":
            forms[v["Entry_ID"]].add(v["Form"].lower())
    entries = {e["ID"]: e for e in rows["entries.csv"] if e["Language_ID"] == "rogn" and e["Status"] != "rejected"}
    for s in rows["senses.csv"]:
        s["Example_IDs"] = []
        e = entries.get(s["Entry_ID"])
        if not e or s["Status"] == "rejected":
            continue
        verb = e["Part_Of_Speech"] == "verb"
        head = pages.DI_ARTICLE.sub("", pages.key(e["Headword"]))
        heads = {alt.split()[0] for alt in re.split(r"\s+o\s+|\s*[/,]\s*", head) if alt.split()}
        mine = {w for f in forms[e["ID"]] | heads for w in WORD.findall(f) if len(w) >= 4 and w not in PARTICLES}
        italian = pages.bare(s["Description"])
        if " " in italian or not mine:
            continue
        stem = italian[:-3] if verb and italian.endswith(("are", "ere", "ire")) else italian[:max(4, len(italian) - 2)]
        if len(stem) < 4:
            continue
        s["Example_IDs"] = [i for i, di, it in examples if di & mine and any(w.startswith(stem) for w in it)]


def load():
    ds = Dataset.from_metadata(METADATA)
    return ds, {t.url.string: [dict(r) for r in t] for t in ds.tables}


# ------------------------------------------------------------------ reading it back for the pages
def for_pages():
    """(uniq, tables, eng) in the shapes step4_build_pages.render() expects, from the lexicon only.
    Rows marked rejected, and variants marked typo, are left out."""
    _, rows = load()
    bib_file = {}
    for line in (CLDF / "sources.bib").read_text().split("@misc{")[1:]:
        k = line.split(",", 1)[0].strip()
        m = re.search(r"note = \{(?:Dialect/)?(?:raw/)?(.+?)\}", line)
        bib_file[k] = m.group(1) if m else k

    def origin(refs):
        if not refs:
            return "", ""
        m = re.match(r"([^\[]+)(?:\[l\.(\d+)\])?", refs[0])
        return bib_file.get(m.group(1), m.group(1)), m.group(2) or "0"

    entries = {e["ID"]: e for e in rows["entries.csv"] if e["Status"] != "rejected"}
    contributions = {c["ID"]: c for c in rows.get("contributions.csv", [])}
    spellings = defaultdict(list)                  # all accepted spellings, shown together: giò / giô / giõ
    for v in rows["variants.csv"]:
        if v["Status"] == "accepted" and v["Kind"] == "spelling":
            spellings[v["Entry_ID"]].append(v["Form"])
    uniq = []
    for s in rows["senses.csv"]:
        e = entries.get(s["Entry_ID"])
        if not e or s["Status"] == "rejected" or (e["Part_Of_Speech"] == "verb" and not _in_word_list(s)):
            continue
        src, line = origin(s["Source"] or e["Source"])
        pending = "pending" in (s["Status"], e["Status"])
        shown = " / ".join([e["Headword"]] + [f for f in spellings[e["ID"]] if pages.key(f) != pages.key(e["Headword"])])
        uniq.append({"italian": s["Description"], "dialect": shown,
                     "english": s["Description_English"] or "",
                     "kind": "word", "variety": LABEL.get(e["Language_ID"]) or "",
                     "canonical": "yes" if e["Language_ID"] == "rogn" else "no", "source": src, "line": line,
                     "check": ((s["Unsure_About"] or "direction") + "?") if pending else "",
                     "note": "" if s["Comment"] in (SUPPLIED_NOTE, CONFIRMED_NOTE, NO_ITALIAN_NOTE) else
                             (s["Comment"] or ("verb" if e["Part_Of_Speech"] == "verb" else "")),
                     "supplied": s["Status"] == "supplied",
                     "gender": e.get("Gender") or "", "plural": e.get("Plural") or ""})
    for x in rows["examples.csv"]:
        if x["Status"] == "rejected" or x.get("Genre") == "grammar":      # the grammar's own examples
            continue
        src, line = origin(x["Source"])
        c = contributions.get(x["Contribution_ID"], {})
        uniq.append({"italian": x["Translated_Text"] or "", "dialect": x["Primary_Text"],
                     "english": x["Translated_Text_English"] or "", "kind": "expression",
                     "variety": LABEL.get(x["Language_ID"]) or "",
                     "canonical": "yes" if x["Language_ID"] == "rogn" else "no", "source": src, "line": line,
                     "check": ((x["Unsure_About"] or "direction") + "?") if x["Status"] == "pending" else "",
                     "note": x["Comment"] or "", "genre": x["Genre"] or "phrase", "topic": x["Topic_ID"] or "",
                     "text": c.get("Name") or "", "author": c.get("Contributor") or ""})

    variants = defaultdict(list)
    for v in rows["variants.csv"]:
        if v["Status"] == "accepted" and v["Kind"] == "spelling":
            variants[v["Entry_ID"]].append(v["Form"])
    cells = defaultdict(list)
    for p in rows["paradigms.csv"]:
        if p["Status"] != "rejected":
            cells[p["Entry_ID"]].append(p)
    senses_of = defaultdict(list)
    for s in rows["senses.csv"]:
        if s["Status"] != "rejected":
            senses_of[s["Entry_ID"]].append(s)
    tables, eng = {}, {}
    for e in entries.values():
        if e["Part_Of_Speech"] != "verb":
            continue
        ss = sorted(senses_of[e["ID"]], key=lambda s: (bool(s["Comment"]), s["ID"]))
        if not ss:
            continue
        name = ss[0]["Description"]
        for s in ss:
            if s["Description_English"]:
                eng[pages.key(s["Description"])] = re.sub(r"^to ", "", s["Description_English"])
        grid = {t: {} for t in pages.ALL_TENSES}
        forms = defaultdict(lambda: defaultdict(list))
        for p in cells[e["ID"]]:
            person = p["Person"] or "-"
            grid[p["Tense"]][person] = (p["Form"], p["Status"] == "inferred")
            if p["Status"] == "attested":
                forms[p["Tense"]][person].append(p["Form"])
        for t in pages.ALL_TENSES:
            persons = ["-"] if t in ("gerundio", "participio passato") else \
                ["2s", "1p", "2p"] if t.startswith("imperativo") else [s for s, _ in pages.PERSONS]
            for person in persons:
                grid[t].setdefault(person, ("–", False))
            grid[t] = {person: grid[t][person] for person in persons}      # mi, ti, lü … order
        cls = e["Conjugation_Class"] or ""
        full = next((v for k, v in pages.CLASSES.items() if v.startswith(cls + ":")), cls) if cls else ""
        tables[name] = {"entry_id": e["ID"], "dialect": [e["Headword"]] + variants[e["ID"]], "class": full,
                        "basis": "inferred" if e["Status"] == "inferred" else ("attested" if e["Comment"] else ""),
                        "evidence": e["Comment"] or "", "aliases": [s["Description"] for s in ss[1:]],
                        "grid": grid, "forms": forms, "aux": e["Auxiliary"],
                        "sources": list(dict.fromkeys(bib_file.get(re.sub(r"\[.*", "", r), r) for r in e["Source"] or []))}
    return uniq, tables, eng


def topics():
    """The topics of the expressions, in the order of etc/topics.csv (as written to cldf/topics.csv)."""
    return load()[1].get("topics.csv", [])


def _in_word_list(sense):
    """Verb senses appear in the dictionary too, like any other word."""
    return True
