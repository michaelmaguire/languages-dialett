#!/usr/bin/env python3
"""Step 2: pull Italian/dialect pairs and verb conjugations out of the extracted text.

Reads  ../raw/extracted/lesson_text/*.txt, ../etc/lesson_sources.csv, ../etc/parallel_texts.csv,
       ../etc/expression_topics.csv, ../raw/notes_added_by_hand.csv
Writes ../raw/extracted/extracted_pairs.csv   one row per Italian/dialect pair (word or expression); private
       ../raw/extracted/unparsed_lines.csv    lines that look like dialect but were not paired; private
       data/extracted_pairs.csv               the same pairs without the lines of stories, poems and
                                              articles (genre `text`), which are never published; public
       data/extracted_verb_forms.csv          one row per conjugated form

Which side of a pair is dialect is decided by scoring each side: Italian words
nearly always end in a vowel and never contain ü/ö, dialect words often end in
a consonant.  An Italian word list is used as well when one is installed.
"""
import csv, difflib, glob, re, sys, unicodedata
from pathlib import Path

from paths import RAW, ETC, DATA, PRIVATE, TEXT

CELL_SEP = "¦"

# ---------------------------------------------------------------- language scoring
WORD = re.compile(r"[^\W\d_]+")
IT_FUNC = set("""il lo la i gli le un uno una di a da in con su per tra fra del dello della dei degli
delle al allo alla ai agli alle dal dallo dalla dai dagli dalle nel nello nella nei negli nelle sul
sullo sulla sui sugli sulle e ed o ma se che chi non più come dove quando perché anche io tu lui lei
noi voi loro mi ti si ci vi è sono sei siamo siete ho hai ha abbiamo avete hanno mio tuo suo questo
questa quello quella molto poco tutto tutti cosa già ancora sempre mai oggi ieri domani""".split())
IT_CONS_FINAL = set("il un in con per non del al nel sul dal col ed ad od bar sport film tram nord sud est ovest".split())
DIALECT_FUNC = set("""mia ul cun par ga ta anca cumè cumé cume gh ghè sum sem gò vo fò nal dala nala
ala nà fà dì vün na indua cusè cusé parché vialtri lur nüm pö dopu quand adess inscì sa i'è ièn
gnanca denta dent sciur sciura tusa nagot quai""".split())
DIALECT_CHARS = set("üöôõ")
DIALECT_ENDINGS = ("aa", "ii", "üü", "oo", "ee", "öö", "ée", "àa")


def load_italian():
    words = set()
    for pat in ("/usr/share/hunspell/it_IT.dic", "/snap/*/current/usr/share/hunspell/it_IT.dic"):
        for path in glob.glob(pat):
            with open(path, encoding="utf-8", errors="ignore") as f:
                next(f, None)
                words.update(line.split("/")[0].strip().lower() for line in f)
            return words
    return words


IT_WORDS = load_italian()


def dialect_score(text):
    """> 0 leans dialect, < 0 leans Italian; roughly per-word average."""
    toks = [t.lower() for t in WORD.findall(text)]
    if not toks:
        return 0.0
    s = 0.0
    for t in toks:
        if DIALECT_CHARS & set(t):
            s += 2
        elif t in IT_FUNC:
            s -= 1
        elif t in DIALECT_FUNC:
            s += 1.5
        elif t in IT_WORDS:
            s -= 1
        elif len(t) > 1 and t[-1] not in "aeiouàèéìòù" and t not in IT_CONS_FINAL:
            s += 1
        elif t.endswith(DIALECT_ENDINGS):
            s += 1
        elif t[-1] in "oe" and len(t) > 3:
            s -= 0.3
    return s / len(toks)


def italian_share(text):
    toks = [t.lower() for t in WORD.findall(text)]
    return sum(t in IT_WORDS or t in IT_FUNC for t in toks) / max(1, len(toks))


def looks_italian_first(a, b):
    """For near-identical lines (Italian and dialect often differ by a letter or two): is the first
    one clearly the more Italian? Both need a few words, so that lists of numbers or names do not pair."""
    return len(WORD.findall(a)) >= 3 and len(WORD.findall(b)) >= 3 and italian_share(a) - italian_share(b) >= 0.1


def orient(a, b):
    """Return (italian, dialect, margin)."""
    sa, sb = dialect_score(a), dialect_score(b)
    return (a, b, sb - sa) if sb >= sa else (b, a, sa - sb)


# ---------------------------------------------------------------- verb blocks
PRONOUNS = [  # dialect and Italian subject pronouns -> person slot
    (r"mi|io", "1s"), (r"ti|tu", "2s"),
    (r"l[eé]\s*[-/–]\s*l[üu]|l[üu]\s*[-/–]\s*l[eé]|lui\s*/\s*lei(?:\s*/\s*lei)?|l[üu]|lui", "3s"),
    (r"n[üu]m+|noi", "1p"), (r"vialtri|voi", "2p"), (r"lur|lor|loro", "3p"),
]
PRON_RE = [(re.compile(rf"^\s*(?:{p})(?=[\s\t]|$)(.*)$", re.I), slot) for p, slot in PRONOUNS]
CLITIC = re.compile(r"^(ma|ta|t'|la/al|al/la|al|la|i|a|l'|l’)$", re.I)
TENSES = ["trapassato prossimo", "passato prossimo", "futuro prossimo", "futuro anteriore",
          "imperfetto", "presente", "futuro"]
# "prendere (ciapà)", "lavarsi (lavas" (bracket never closed), "correre (cor)   transitivo intransitivo",
# "scegliere / cata fö"
VERB_HEAD = re.compile(r"^\s*([A-Za-zÀ-ÿ' ]{2,30}?)\s*(?:\(([^)\t]{1,30})\)?\s*(\t.*)?|/\s*([a-zà-ü ]{2,20}))$")
COLON_HEAD = re.compile(r"^\s*([A-Za-zà-ü]{4,20})\s*(?::|=)\s*(mi\s.+)$")      # "Indossare:   mi meti sü"
COLS = re.compile(r"\t+|\s{2,}")
PRON_IN_VARIANT = re.compile(r"/\s*(?:mi|ti|lü|le|nüm|vialtri|lur|lor)\b\s*/?\s*")       # "mi mazi / mi copi"
# A conjugation row is short (the longest, lesson 17's six tenses, is 125 characters); a longer line
# that starts with a pronoun is prose ("Mi chiamo Bruno e ho 21 anni ...", varie situazioni).
MAX_CONJ_ROW = 200
# "che lu/le al/la sia", "che num a sium", "che l/l al/la naga": "che" and the subject pronoun(s)
SUBJ_LEAD = re.compile(r"^che\s+(?:(?:mi|ti|lu|lü|le|l|num|nüm|vialtri|lur|lor)\b\s*[/-]?\s*)*", re.I)


def tense_header(line):
    low = line.lower()
    if sum(t in low for t in ("presente", "imperfetto", "futuro", "prossimo")) < 2:
        return None
    cells = [c.strip().lower() for c in COLS.split(line) if c.strip()]
    return cells if all(any(t in c for t in TENSES) for c in cells) else None


def pronoun_row(line):
    for rx, slot in PRON_RE:
        m = rx.match(line)
        if m:
            rest = m.group(1)       # Word files separate columns with tabs; a double space inside a cell is a typo
            parts = re.split(r"\t+", rest) if "\t" in rest.strip() else COLS.split(rest)
            cells = [re.sub(r"\s+", " ", c).strip() for c in parts if c.strip()]
            out = []
            for c in cells:
                if out and re.fullmatch(r"\(\w{1,2}\)", c):       # "(a)" feminine ending
                    out[-1] += " " + c
                elif out and CLITIC.match(out[-1]):               # "ta" + "se"; "l’" + "è" (no space)
                    out[-1] += ("" if out[-1].endswith(("'", "’")) else " ") + c
                else:
                    out.append(c)
            return slot, out
    return None


# ---------------------------------------------------------------- line pairing
INLINE = re.compile(r"\t+|\s{3,}|\s=\s|\s:\s")
COLON_PAIR = re.compile(r"^\s*([^:=\t]{2,45}?):\s*(\S.*?)\s*$")
COLON_LABELS = {"significato", "esempio", "esempi", "nota", "attenzione", "scioglilingua", "es", "ps",
                "tu", "noi", "voi", "lui", "lei", "loro", "io"}


def plain_word(w):
    return re.sub(r"[^a-zà-ü]", "", w.lower())


JUNK = re.compile(r"^[\W\d_]*$|^[A-Z9]{2,6}$|^[a-z]{1,4}$")
SENT = re.compile(r"(?<=[.!?…])\s+(?=[A-ZÀ-ÝÜÖ«“\"])")
ALT_MARGIN = 0.2       # how differently two lines must score (Italian vs dialect) to be a pair
ALT_SIM = 0.42         # how alike a line and its translation on the next line must look
SPLIT_SIM = 0.62       # same, for two halves of one line


def norm(s):
    s = re.sub(r"^\s*[\w .]{1,20}:\s*", "", s)          # speaker label / "Significato:"
    s = unicodedata.normalize("NFD", s.lower())
    return re.sub(r"[^a-z ]", "", s)


def similarity(a, b):
    return difflib.SequenceMatcher(None, norm(a), norm(b), autojunk=False).ratio()


def clean(s):
    return re.sub(r"\s+", " ", s).strip(" \t•-–·")


def kind_of(italian, dialect=""):
    if len(dialect) > 45 or len(dialect.split()) > 5:
        return "expression"
    if re.match(r"\s*\d", italian) or italian.rstrip()[-1:] in ".!?":
        return "expression"
    n = len([t for t in WORD.findall(italian.lower()) if t not in IT_FUNC])
    return "word" if n <= 2 and len(italian) < 40 else "expression"


class Doc:
    def __init__(self, name, meta):
        self.name, self.meta = name, meta
        self.pairs, self.verbs, self.unparsed, self.columns = [], [], [], []

    def settle_columns(self):
        """In a two-column list every row has the dialect on the same side. Let each row's
        neighbours vote, so one ambiguous row cannot flip on its own."""
        for i, (idx, line, a, b, d) in enumerate(self.columns):
            near = [c for c in self.columns[max(0, i - 5):i + 6] if abs(c[1] - line) <= 12]
            vote = sum(c[4] for c in near) + d
            it, di = (a, b) if vote >= 0 else (b, a)
            p = self.pairs[idx]
            p.update(italian=it, dialect=di, kind=kind_of(it, di),
                     check="" if abs(vote) >= 1.0 else "direction?")

    def pair(self, a, b, line, note="", fixed=False, column=False):
        a, b = clean(a), clean(b)
        if not a or not b or a.lower() == b.lower():
            return
        it, di, margin = (a, b, 9) if fixed else orient(a, b)
        if column:                              # remember the raw columns for settle_columns()
            self.columns.append((len(self.pairs), line, a, b, dialect_score(b) - dialect_score(a)))
        self.pairs.append({"italian": it, "dialect": di, "kind": kind_of(it, di),
                           "variety": self.meta["variety"], "canonical": self.meta["canonical"],
                           "source": self.name, "line": line,
                           "check": "" if margin >= 0.3 else "direction?", "note": note})

    def expand_idem(self):
        """The handouts write "idem" for "same meaning as the line above". Spell it out."""
        last = ""
        for p in sorted(self.pairs, key=lambda p: int(p["line"])):
            m = re.match(r"idem\b[\s,:;-]*(.*)$", p["italian"], re.I)
            if m and last:
                p["italian"] = last + (f" ({m.group(1)})" if m.group(1) else "")
                p["kind"] = kind_of(p["italian"], p["dialect"])
            elif not m:
                last = p["italian"]
        above = {}                              # same verb and tense, previous person
        for v in self.verbs:
            k = (v["verb_italian"], v["tense"])
            m = re.search(r"\(idem (\w+)\)", v["form"])
            if m and k in above:
                shown = re.search(rf"\({m.group(1)}\s*=\s*[^)]*\)", above[k])
                if shown:
                    v["form"] = v["form"].replace(m.group(0), shown.group(0))
            elif "(idem)" in v["form"] and k in above:          # same bracketed note as the person above
                shown = re.findall(r"\([^)]*\)", above[k])
                v["form"] = v["form"].replace("(idem)", shown[-1] if shown else "").strip()
            above[k] = v["form"]

    def verb(self, it, di, tense, slot, form, line):
        self.verbs.append({"verb_italian": clean(it).lower(), "verb_dialect": clean(di).lower(),
                           "tense": tense, "person": slot, "form": clean(form),
                           "italian_form": "", "variety": self.meta["variety"],
                           "canonical": self.meta["canonical"], "source": self.name, "line": line})


def parse_bullets(doc, lines):
    """brevi frasi: each item is a bullet with the Italian, then the dialect, either of which may wrap.
    Split each item where the two halves look most like translations of each other."""
    blocks, cur = [], None
    for n, raw in enumerate(lines, 1):
        t = raw.strip()
        if t.startswith("•"):
            cur = [n, []]
            blocks.append(cur)
            t = t.lstrip("• ").strip()
        if cur is not None and t and not JUNK.match(t):
            cur[1].append(t)
    for n, parts in blocks:
        if len(parts) < 2:
            continue
        best = max(((similarity(" ".join(parts[:k]), " ".join(parts[k:])), k) for k in range(1, len(parts))))
        it, di = " ".join(parts[:best[1]]), " ".join(parts[best[1]:])
        if it.lower() == di.lower():
            continue
        doc.pair(it, di, n, fixed=True)
        if best[0] < 0.45:
            doc.pairs[-1]["check"] = "pairing?"


def parse(doc, text):
    lines = text.replace("\f", "\n").split("\n")
    if doc.meta["layout"] == "bullets":
        return parse_bullets(doc, lines)
    tenses = ["presente", "congiuntivo presente"] if doc.meta["layout"] == "subjunctive" else ["presente"]
    verb = None                # (italian, dialect) of the open conjugation block
    head_candidate = None
    table_head, table_tense, head_line = [], "", -9
    double_past = False
    singles = []                # (lineno, text) waiting for alternating-line pairing

    def flush():
        """Pair up the waiting single lines: line + its translation on the next line,
        or both halves on one line. A translation resembles its original, so
        similarity decides what belongs together and the language score decides
        which half is Italian."""
        i = 0
        while i < len(singles):
            n, cur = singles[i]
            if i + 1 < len(singles):
                n2, nxt = singles[i + 1]
                s_here = similarity(cur, nxt)
                s_next = 0
                if i + 2 < len(singles) and orient(nxt, singles[i + 2][1])[2] >= ALT_MARGIN:
                    s_next = similarity(nxt, singles[i + 2][1])
                it, di, margin = orient(cur, nxt)
                if s_here >= ALT_SIM and s_here >= s_next and margin >= ALT_MARGIN and n2 - n <= 3:
                    doc.pair(it, di, n, fixed=True)
                    if s_here < 0.55:
                        doc.pairs[-1]["check"] = "pairing?"
                    i += 2
                    continue
                if s_here >= 0.6 and s_here >= s_next and n2 - n <= 2 and doc.meta["canonical"] == "yes" \
                        and looks_italian_first(cur, nxt):
                    doc.pair(cur, nxt, n, fixed=True)          # Italian first, as on the course sheets
                    doc.pairs[-1]["check"] = "direction?"
                    i += 2
                    continue
            # both halves on one line: try sentence boundaries first, then any word boundary
            best = None
            parts = SENT.split(cur)
            cands = [(" ".join(parts[:k]), " ".join(parts[k:]), "") for k in range(1, len(parts))]
            words = cur.split()
            if 4 <= len(words) <= 30:
                cands += [(" ".join(words[:k]), " ".join(words[k:]), "split?")
                          for k in range(2, len(words) - 1)]
            for a, b, flag in cands:
                if not 0.6 <= len(a) / max(1, len(b)) <= 1.7:
                    continue
                s = similarity(a, b) + (0.1 if not flag else 0)
                if best is None or s > best[0]:
                    best = (s, a, b, flag)
            if best and best[0] >= SPLIT_SIM and orient(best[1], best[2])[2] >= ALT_MARGIN:
                it, di, _ = orient(best[1], best[2])
                doc.pair(it, di, n, fixed=True)
                if best[3]:
                    doc.pairs[-1]["check"] = best[3]
            elif best and best[0] >= 0.7 and not best[3] and doc.meta["canonical"] == "yes" \
                    and looks_italian_first(best[1], best[2]):
                doc.pair(best[1], best[2], n, fixed=True)      # "Italian sentence. Dialect sentence."
                doc.pairs[-1]["check"] = "direction?"
            elif dialect_score(cur) > 0.3 and len(WORD.findall(cur)) >= 2:
                doc.unparsed.append({"source": doc.name, "line": n, "text": clean(cur),
                                     "variety": doc.meta["variety"]})
            i += 1
        singles.clear()

    for n, raw in enumerate(lines, 1):
        line = raw.rstrip()
        if not line.strip():
            continue
        if JUNK.match(line.strip()):
            continue

        # --- Word tables
        if line.startswith("| "):
            flush()
            cells = [c.strip() for c in line[2:].split(" | ")]
            row = pronoun_row(cells[0].split(CELL_SEP)[0]) if cells else None
            if row and any(CELL_SEP in c for c in cells[1:]):
                for k, c in enumerate(cells[1:]):
                    parts = [p.strip() for p in c.split(CELL_SEP) if p.strip()]
                    if len(parts) < 2:
                        continue
                    name = table_head[k] if k < len(table_head) else f"col{k + 1}"
                    it_name, _, di_name = name.partition("/")
                    # Word auto-capitalises the first letter of each table cell: undo that
                    parts = [p[:1].lower() + p[1:] for p in parts]
                    doc.verb(it_name, di_name, table_tense or "?", row[0], " / ".join(parts[1:]), n)
                    doc.verbs[-1]["italian_form"] = parts[0]
            elif not row and max(c.count(CELL_SEP) for c in cells) >= 2:
                # a cell holding a whole list of lines: only usable if two cells line up one-to-one
                cols = [[p.strip() for p in c.split(CELL_SEP) if p.strip()] for c in cells if c]
                if len(cols) == 2 and len(cols[0]) == len(cols[1]):
                    for a, b in zip(*cols):
                        if similarity(a, b) >= ALT_SIM and orient(a, b)[2] >= ALT_MARGIN:
                            doc.pair(a, b, n)
                else:
                    for col in cols:
                        doc.unparsed += [{"source": doc.name, "line": n, "text": clean(t),
                                          "variety": doc.meta["variety"]} for t in col]
            elif not row and max(c.count(CELL_SEP) for c in cells) >= 2:
                # a cell holding a whole list of lines: only usable if two cells line up one-to-one
                cols = [[p.strip() for p in c.split(CELL_SEP) if p.strip()] for c in cells if c]
                if len(cols) == 2 and len(cols[0]) == len(cols[1]):
                    for a, b in zip(*cols):
                        if similarity(a, b) >= ALT_SIM and orient(a, b)[2] >= ALT_MARGIN:
                            doc.pair(a, b, n)
                else:
                    for col in cols:
                        doc.unparsed += [{"source": doc.name, "line": n, "text": clean(t),
                                          "variety": doc.meta["variety"]} for t in col]
            elif not row:
                cells = [c.replace(CELL_SEP, "/") for c in cells if c]
                if doc.meta["layout"] == "opposites" and len(cells) == 4:
                    # "Aggettivi e contrari": Italian | its opposite | dialect | its opposite.
                    # The first row is the heading. Word capitalises each paragraph of a cell
                    # ("Internu ¦ Da denta"), so lower the first letter of each.
                    if cells[0].lower() == "aggettivo":
                        continue
                    # A cell with several words ("Piöcc/brascin ¦ Tirex", "Al solit, urdinari", "Vösct (Vöi)")
                    # gives one pair per word, so each has its own dictionary entry (owner, 2026-10-28).
                    it, it_opp, di, di_opp = ([w.strip()[:1].lower() + w.strip()[1:]
                                               for w in re.split(rf"\s*(?:{CELL_SEP}|/|,|\(|\))\s*", c) if w.strip()]
                                              for c in (x.strip() for x in line[2:].split(" | ") if x.strip()))
                    for its, dis, other_it, other_di in ((it, di, it_opp, di_opp), (it_opp, di_opp, it, di)):
                        note = f"contrario: {' / '.join(other_di)} ({' / '.join(other_it)})"
                        for d in dis:
                            doc.pair(" / ".join(its), d, n, note=note, fixed=True)
                    continue
                if len(cells) == 2:
                    doc.pair(cells[0], cells[1], n)
                elif len(cells) == 3 and max(map(dialect_score, cells)) > 0:   # two dialect variants + Italian
                    cells.sort(key=dialect_score)
                    doc.pair(cells[0], cells[2], n, note=f"also: {cells[1]}", fixed=True)
            continue

        low = line.lower()
        m = re.search(r"(condizionale|congiuntivo)\s+(presente|passato|imperfetto|trapassato)", low)
        if m:
            table_tense = f"{m.group(1)} {m.group(2)}"
        if "\t" in line and not pronoun_row(line) and len(line) < 120:
            heads = [c.strip().lower() for c in COLS.split(line) if c.strip()]
            if heads and all(len(h.split()) <= 3 for h in heads):
                if n - head_line == 1 and len(heads) == len(table_head):   # Italian row, then dialect row
                    table_head = [f"{a}/{b}" for a, b in zip(table_head, heads)]
                else:
                    table_head = heads
                head_line = n

        # --- conjugation blocks in running text
        th = tense_header(line)
        if th:
            flush()
            tenses, verb = th, None
            continue
        ch = COLON_HEAD.match(line)
        if ch and pronoun_row(ch.group(2)):
            flush()
            verb, tenses, double_past = (ch.group(1), ""), ["presente"], False
            pieces = [p for p in re.split(r",\s*(?=(?:ti|lü|le|nüm|vialtri|lur|lor)\b)", ch.group(2))]
            for piece in pieces:                # one person per line, or all six on one line
                r = pronoun_row(piece)
                if r and r[1]:
                    doc.verb(verb[0], "", "presente", r[0], PRON_IN_VARIANT.sub("/ ", r[1][0]), n)
            continue
        vh = VERB_HEAD.match(line) if not pronoun_row(line) else None
        if vh and (vh.group(2) or vh.group(4)):
            flush()
            head_candidate = (vh.group(1), vh.group(2) or vh.group(4), n)
            double_past = "intransitivo" in (vh.group(3) or "")
            continue
        row = pronoun_row(line)
        if row and len(line) > MAX_CONJ_ROW:     # prose starting "Mi chiamo Bruno ...", not a conjugation row
            row = None
        if row and row[1] and (verb or (head_candidate and n - head_candidate[2] <= 3)):
            if head_candidate and n - head_candidate[2] <= 3:
                verb = head_candidate[:2]
                # the header itself is a dictionary entry: "prendere (ciapà)"
                doc.pair(verb[0], verb[1], head_candidate[2], note="verb", fixed=True)
                head_candidate = None
            cells = row[1]
            if doc.meta["layout"] == "subjunctive":
                # "al congiuntif": each row is the present indicative and, after "che", the present
                # subjunctive ("sum che mi sia"), often with only a space between them. Keep the
                # subjunctive as the other tables of forms do: no "che", no subject pronoun ("sia").
                # (tabs can fall inside either half, so the row is joined again before splitting)
                cells = [p for p in re.split(r"\s+(?=che\s)", " ".join(cells)) if p.strip()]
                if len(cells) == 1:     # "che" left out ("i vegnan lor i vegnan"): split at the repeated pronoun
                    cells = [p for p in re.split(r"\s+(?=(?:mi|ti|lü|le|nüm|num|vialtri|lor)\s)", cells[0], maxsplit=1)
                             if p.strip()]
                    cells = cells[:1] + ["che " + c for c in cells[1:]]
                cells = cells[:1] + [SUBJ_LEAD.sub("", c) for c in cells[1:]]
            forms = [PRON_IN_VARIANT.sub("/ ", f) for f in cells]
            if double_past and len(forms) == len(tenses) + 1:      # passato prossimo with avere and with essere
                forms = [forms[0], f"{forms[1]} / {forms[2]}"] + forms[3:]
            lead = re.match(r"(ta|la/al|al/la|i)\s+\S", forms[0])
            if lead and len(tenses) >= 4:       # lessons 17-18: the clitic sits in the pronoun column
                clitic = lead.group(1)          # and so belongs to every tense in the row
                forms = [f if f.startswith(clitic + " ") else f"{clitic} {f}" for f in forms]
            for k, form in enumerate(forms):
                doc.verb(verb[0], verb[1], tenses[k] if k < len(tenses) else f"col{k + 1}",
                         row[0], form, n)
            continue
        if not row:
            verb = None
        elif len(row[1]) >= 1:              # stray conjugation row with no verb heading: not a word pair
            flush()
            doc.unparsed.append({"source": doc.name, "line": n, "text": clean(line),
                                 "variety": doc.meta["variety"]})
            continue

        # --- "Aprire: vert mia, verdem mia, verdii mia" (negative imperative: tu, noi, voi)
        if doc.meta["layout"] == "imperative":
            m = re.match(r"\s*([A-Za-zà-ü]+(?: [a-zà-ü]+)?):\s*(.*\bmia\b.*)$", line)
            forms = [f.strip(" .…") for f in re.split(r",|…+\.*", m.group(2))] if m else []
            forms = [f for f in forms if f]
            if m and len(forms) == 3 and not re.search(r"\(|–", line):
                flush()
                for slot, form in zip(("2s", "1p", "2p"), forms):
                    doc.verb(m.group(1), "", "imperativo negativo", slot, form[:1].lower() + form[1:], n)
                continue

        # --- two things on one line
        segs = [s for s in (clean(x) for x in INLINE.split(line)) if s]
        # "Grembiule: scusaa": a colon straight after the word, so INLINE (which wants a space before
        # it) does not see it. Only short label-and-answer lines; not "Significato: ..." or speakers.
        cm = COLON_PAIR.match(line)
        if len(segs) < 2 and cm and len(cm.group(1).split()) <= 5 and len(cm.group(2).split()) <= 8 \
                and plain_word(cm.group(1).split()[0]) not in COLON_LABELS \
                and doc.meta["canonical"] == "yes" and re.search(r"[^\W\d_]", cm.group(2)) \
                and not re.search(r"[\"“«!?.]|\(es\.", cm.group(1) + cm.group(2)) \
                and not re.fullmatch(r"[A-Z][a-z]+", cm.group(2).strip()) \
                and orient(cm.group(1), cm.group(2))[2] >= 0.5:     # one side clearly dialect
            segs = [clean(cm.group(1)), clean(cm.group(2))]
        if doc.meta["layout"] == "gerund" and len(segs) == 3 and len(line) < 100:
            if segs[1].lower() != "italiano":      # infinitive | Italian gerund | dialect gerund
                doc.verb(segs[0], "", "gerundio", "-", segs[2], n)
                doc.verbs[-1]["italian_form"] = segs[1]
            continue
        if len(segs) >= 2 and re.match(r"[\"“«”]", segs[1]) and len(segs[0].split()) <= 2:
            segs = []                           # 'Andrea : "Ciao Marco"' is a speaker label, not a pair
        if len(segs) >= 2 and len(line) < 200:
            flush()
            note = "; ".join(segs[2:])
            doc.pair(segs[0], segs[1], n, note=note, column=True)
            continue
        singles.append((n, line))
    flush()


# ---------------------------------------------------------------- translations in a separate document
# A class translation (layout `parallel` in etc/lesson_sources.csv) is paired with its Italian original,
# listed in etc/parallel_texts.csv, by aligning the two texts: sentence by sentence for prose, line by line
# (within each canto) for verse. Dialect and Italian share most word roots, so two units are judged alike by
# how many of their words look related (same start, or similar spelling once the dialect's sct/scp and
# double letters are evened out), and by their length. A dynamic programme finds the best path through both
# texts, allowing one unit to match two. A weak match is marked `pairing?` (⚠).
CANTO = re.compile(r"^\s*Canto\s+([IVXL]+)\b", re.I)


def cognate_key(w):
    w = unicodedata.normalize("NFD", w.lower())
    w = "".join(c for c in w if not unicodedata.combining(c))
    w = w.replace("sct", "st").replace("scp", "sp").replace("sc", "s").replace("gh", "g").replace("ch", "c")
    return re.sub(r"(.)\1+", r"\1", w)


_RELATED = {}


def related(a, b):
    k = (a, b)
    if k not in _RELATED:
        _RELATED[k] = (a[:4] == b[:4] and len(a) >= 4 and len(b) >= 4) or (
            len(a) >= 3 and len(b) >= 3 and abs(len(a) - len(b)) <= 3
            and difflib.SequenceMatcher(None, a, b).ratio() >= 0.72)
    return _RELATED[k]


def keys(text):
    return tuple(cognate_key(w) for w in WORD.findall(text) if len(w) >= 3)


def unit_similarity(di, it):
    """Share of the words of two units that have a related word on the other side (0 to 1)."""
    a, b = keys(di), keys(it)
    if not a or not b:
        return 0.0
    hits = sum(any(related(x, y) for y in b) for x in a) + sum(any(related(x, y) for x in a) for y in b)
    return hits / (len(a) + len(b))


def numbered(text):
    return [(n, re.sub(r"\s+", " ", raw).strip()) for n, raw in enumerate(text.split("\n"), 1)]


def units(lines, unit):
    """[(first line number, text)]: sentences (prose) or lines (verse) from numbered lines."""
    out, buf, start = [], [], None
    for n, line in lines:
        if not line:
            continue
        if unit == "line":
            out.append((n, line))
            continue
        for piece in re.split(r"(?<=[.!?…])\s+(?=[\"“«‘'(–-]?[A-ZÀ-Ü])", line):
            if start is None:
                start = n
            buf.append(piece)
            if re.search(r"[.!?…][\"”»’')]*$", piece):
                out.append((start, " ".join(buf)))
                buf, start = [], None
    if buf:
        out.append((start, " ".join(buf)))
    return out


def sections(lines, unit, whole=None):
    """{section: numbered lines}: cantos for verse (a document without canto headings is the canto named in
    etc/parallel_texts.csv `part`), the whole text otherwise. Text before the first heading is left out."""
    if unit != "line":
        return {"": lines}
    parts, name = {}, whole
    for n, line in lines:
        m = CANTO.match(line)
        if m:
            name = m.group(1).upper()
        elif name:
            parts.setdefault(name, []).append((n, line))
    return parts


def align(di_units, it_units):
    """Best monotone pairing of two lists of (line, text); returns [(di_units, it_units, similarity)]."""
    n, m = len(di_units), len(it_units)
    NEG = float("-inf")
    best = [[NEG] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    best[0][0] = 0.0
    join = lambda us: " ".join(t for _, t in us)

    def gain(a, b):
        da, ib = join(a), join(b)
        lp = abs((len(da) + 1) / (len(ib) + 1) - 1)
        return unit_similarity(da, ib) - 0.15 * min(lp, 2)

    band = max(12, abs(n - m) + 8)                    # translations keep the order: stay near the diagonal
    for i in range(n + 1):
        centre = round(i * m / n) if n else 0
        for j in range(max(0, centre - band), min(m, centre + band) + 1):
            if best[i][j] == NEG:
                continue
            for di, dj in ((1, 1), (2, 1), (1, 2), (1, 0), (0, 1)):
                if i + di > n or j + dj > m:
                    continue
                g = -0.12 if 0 in (di, dj) else gain(di_units[i:i + di], it_units[j:j + dj]) - (0.04 if di + dj == 3 else 0)
                if best[i][j] + g > best[i + di][j + dj]:
                    best[i + di][j + dj] = best[i][j] + g
                    back[i + di][j + dj] = (di, dj)
    out, i, j = [], n, m
    while i or j:
        di, dj = back[i][j]
        if di and dj:
            a, b = di_units[i - di:i], it_units[j - dj:j]
            out.append((a, b, unit_similarity(join(a), join(b))))
        i, j = i - di, j - dj
    return out[::-1]


def parallel_pairs(row, meta):
    """Pairs from one dialect document and its Italian original (one row of etc/parallel_texts.csv)."""
    di_path, it_path = TEXT / (row["dialect_file"] + ".txt"), TEXT / (row["italian_file"] + ".txt")
    if not (di_path.exists() and it_path.exists()):
        print(f"  parallel: missing text for {row['dialect_file']} or {row['italian_file']}")
        return []
    unit = row.get("unit") or "sentence"
    di_parts = sections(numbered(di_path.read_text()), unit, (row.get("part") or "").upper() or None)
    it_parts = sections(numbered(it_path.read_text()), unit)
    pairs = []
    for name, di_lines in di_parts.items():
        if name not in it_parts:
            print(f"  parallel: {row['dialect_file']}: section {name or '(whole text)'} not in {row['italian_file']}")
            continue
        for a, b, sim in align(units(di_lines, unit), units(it_parts[name], unit)):
            di, it = clean(" ".join(t for _, t in a)), clean(" ".join(t for _, t in b))
            if di and it:
                pairs.append({"italian": it, "dialect": di, "kind": "expression",
                              "variety": meta.get("variety", ""), "canonical": meta.get("canonical", ""),
                              "source": row["dialect_file"], "line": a[0][0], "check": "" if sim >= 0.12 else "pairing?",
                              "note": "", "italian_source": row["italian_file"], "italian_line": b[0][0]})
    return pairs


def public_pairs(pairs, manifest):
    """The pairs that may be published: all but the expressions from documents of genre `text` (stories,
    poems, articles), which reach neither the pages nor cldf/ (owner, 2026-10-14 and 2026-10-28). An expression
    from such a document that etc/expression_topics.csv keeps as a saying or phrase is kept here too, so a
    build without raw/ gives the same dataset. Words from them are kept: short, and in the dictionary."""
    genre = {m["file"]: (m.get("genre") or "").strip() for m in manifest}
    kept = set()
    path = ETC / "expression_topics.csv"
    for t in csv.DictReader(path.open(encoding="utf-8")) if path.exists() else []:
        if (t.get("Genre") or "").strip() not in ("", "text"):
            kept.add(norm(QUOTES.sub("", t["Form"])))
    # lines a decision or a pair correction names (its wording may then differ from expression_topics.csv)
    for d in csv.DictReader((ETC / "decisions.csv").open(encoding="utf-8")):
        kept.add(norm(QUOTES.sub("", d["Form"])))
    fixed = {(r["source"], r["line"]) for r in csv.DictReader((ETC / "pair_corrections.csv").open(encoding="utf-8"))}
    return [p for p in pairs if not (genre.get(p["source"]) == "text" and p["kind"] == "expression"
                                     and norm(QUOTES.sub("", p["dialect"])) not in kept
                                     and (p["source"], str(p["line"])) not in fixed)]


QUOTES = re.compile(r"^[\s«»“”\"„‘’']+|[\s«»“”\"„‘’']+$")


def main():
    from paths import raw_available
    if not raw_available():           # would overwrite the saved extraction with almost nothing
        sys.exit("step 2: no source documents in raw/ (the submodule is not checked out); "
                 "keeping the extraction already in pipeline/data/")
    DATA.mkdir(exist_ok=True)
    manifest = list(csv.DictReader((ETC / "lesson_sources.csv").open()))
    pairs, verbs, unparsed = [], [], []
    for meta in manifest:
        path = TEXT / (meta["file"] + ".txt")
        if meta["include"].strip().lower() != "yes" or meta["layout"] in ("skip", "text_only", "parallel") or not path.exists():
            continue
        doc = Doc(meta["file"], meta)
        parse(doc, path.read_text())
        doc.settle_columns()
        doc.expand_idem()
        print(f"{len(doc.pairs):5} pairs {len(doc.verbs):5} verb forms {len(doc.unparsed):4} unparsed  {meta['file']}")
        pairs += doc.pairs; verbs += doc.verbs; unparsed += doc.unparsed

    by_file = {m["file"]: m for m in manifest}
    for row in csv.DictReader((ETC / "parallel_texts.csv").open()) if (ETC / "parallel_texts.csv").exists() else []:
        meta = by_file.get(row["dialect_file"], {})
        if meta.get("include", "").strip().lower() != "yes" or meta.get("layout") != "parallel":
            continue
        found = parallel_pairs(row, meta)
        flagged = sum(bool(p["check"]) for p in found)
        print(f"{len(found):5} pairs aligned ({flagged} weak)  {row['dialect_file']}  <->  {row['italian_file']}")
        pairs += found

    # vocabulary the owner typed in from their own notes: already paired, nothing to guess
    notes = RAW / "notes_added_by_hand.csv"
    if notes.exists():
        # line = the row's line in the file (the header is line 1), so etc/pair_corrections.csv can name it;
        # a row with dialect and English but no Italian is kept: a correction supplies the Italian
        rows = [(i, r) for i, r in enumerate(csv.DictReader(notes.open()), 2)
                if r.get("dialect", "").strip() and (r.get("italian", "").strip() or r.get("english", "").strip())]
        for i, r in rows:
            it, di = clean(r["italian"] or ""), clean(r["dialect"])
            pairs.append({"italian": it, "dialect": di, "kind": kind_of(it, di), "variety": "Rögn (Arogno)",
                          "canonical": "yes", "source": "notes_added_by_hand.csv", "line": i, "check": "",
                          "note": (r.get("note") or "").strip()})
        print(f"{len(rows):5} pairs     0 verb forms    0 unparsed  notes_added_by_hand.csv (typed from my notes)")

    public = public_pairs(pairs, manifest)
    print(f"      {len(pairs) - len(public)} lines of texts (stories, poems, articles) kept out of pipeline/data/")
    PRIVATE.mkdir(parents=True, exist_ok=True)
    for folder, name, rows in ((PRIVATE, "extracted_pairs", pairs), (PRIVATE, "unparsed_lines", unparsed),
                               (DATA, "extracted_pairs", public), (DATA, "extracted_verb_forms", verbs)):
        if not rows:
            continue
        with (folder / f"{name}.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
            w.writeheader()
            w.writerows(rows)
    print(f"TOTAL {len(pairs)} pairs, {len(verbs)} verb forms, {len(unparsed)} unparsed lines")
    if not IT_WORDS:
        print("note: no Italian word list found; direction guessing is weaker without it")


if __name__ == "__main__":
    sys.exit(main())
