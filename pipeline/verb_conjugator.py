"""Fill in verb forms the course material does not give, using the patterns it does give.

The model paradigms are the fully conjugated verbs of lessons 8, 17 and 18 (ciapà, bef, dörmi,
vegnì ...), the conditional sheets and the imperative sheet.  Everything produced here is a
prediction: the pages mark it with a dagger (†) and never lets it replace a form found in a document.
"""
import re
import unicodedata

PERSONS = ["1s", "2s", "3s", "1p", "2p", "3p"]
SIMPLE = ["presente", "imperfetto", "futuro", "condizionale presente"]
SUBJUNCTIVE = ["congiuntivo presente", "congiuntivo imperfetto"]
# The course has no subjunctive table; these patterns come from the few forms found in its sentences:
# imperfect 'füdessa, al füdess, füdessum' (like the conditional's -essa endings), present 'che al naga,
# che i ma faga, che i ma daga, ta siat, sian'. Regular verbs: present = stressed stem + a/at/a/um/uf/an,
# imperfect = unstressed stem + ass/ess/iss + the same endings, except the 3rd singular, which has none
# (al füdess; 'che quaidun ma brasciass e ma disess', frasi fai 1).
SUBJ_ENDINGS = ["a", "at", "a", "um", "uf", "an"]
SUBJ_IMPERFECT_ENDINGS = ["a", "at", "", "um", "uf", "an"]
SUBJ_VOWEL = {"1": "a", "2": "e", "3": "e", "4": "i", "4i": "i"}
SUBJ_IRREGULAR = {  # infinitive -> (present stem, imperfect stem)
    "ves": ("si", "füdess"), "vegh": ("gh’abi", "gh’avess"), "na": ("nag", "nass"), "nà": ("nag", "nass"),
    "fa": ("fag", "fass"), "fà": ("fag", "fass"), "dà": ("dag", "dass"), "stà": ("stag", "stass"),
    "dì": ("dig", "disess"), "savé": ("sapi", "savess"), "podé": ("pod", "pudess"), "vöré": ("vör", "vuress"),
}
COMPOUND = ["passato prossimo", "trapassato prossimo", "futuro prossimo", "condizionale passato"]
CLITIC = {"2s": "ta ", "3s": "la/al ", "3p": "i "}
REFLEXIVE = ["ma sa ", "ta sa ", "la/al sa ", "sa ", "sa ", "i sa "]

AUX_AVERE = {
    "passato prossimo": ["u", "te", "l’a", "em", "ii", "i an"],
    "trapassato prossimo": ["eva", "ta evat", "la/al eva", "evum", "evuf", "i evan"],
    "futuro prossimo": ["avrò", "ta avret", "la/al avrà", "avrem", "avrii", "i avran"],
    "condizionale passato": ["avria/avress", "t’avriat/t’avressat", "l’avria/l’avressa",
                             "avrium/avressum", "avriuf/avressuf", "i avrian/i avressan"],
}
AUX_ESSERE = {
    "passato prossimo": ["sum", "ta se/set", "l’è", "sem", "sii", "i è"],
    "trapassato prossimo": ["seva", "ta sevat", "la/al eva", "sevum", "sevuf", "i evan"],
    "futuro prossimo": ["sarò", "ta saret", "la/al sarà", "sarem", "sarii", "i saran"],
    "condizionale passato": ["saria/saress", "ta sariat/ta saressat", "la/al saria/saressa",
                             "sarium/saressum", "sariuf/saressuf", "i sarian/i saressan"],
}
AUX_REFLEXIVE = {
    "passato prossimo": ["ma sum", "ta sa set", "la/al s’è", "sa sem", "sa sii", "i s’è"],
    "trapassato prossimo": ["ma seva", "ta sa sevat", "la/al s’eva", "sa sevum", "sa sevuf", "i s’evan"],
    "futuro prossimo": ["ma sarò", "ta sa saret", "la/al sa sarà", "sa sarem", "sa sarii", "i sa saran"],
    "condizionale passato": ["ma saria/saress", "ta sa sariat/saressat", "la/al sa saria/saressa",
                             "sa sarium/saressum", "sa sariuf/saressuf", "i sa sarian/saressan"],
}

COND = [("aria", "aressa"), ("ariat", "aressat"), ("aria", "aressa"),
        ("arium", "aressum"), ("ariuf", "aressuf"), ("arian", "aressan")]      # two endings, both in use
FUT = ["arò", "aret", "arà", "arem", "arii", "aran"]    # ta dormaret (lesson 18 on, and every later text); lesson 8 had ta bevaré
ENDINGS = {  # class -> tense -> endings; "@3" = special 3rd person singular
    "1": {"presente": ["i", "at", "a", "um", "uf", "an"],
          "imperfetto": ["ava", "avat", "ava", "avum", "avuf", "avan"],
          "imperative": ["a", "em", "ii"], "gerund": "ando", "participle": "aa"},
    "2": {"presente": ["i", "at", "@3", "um", "uf", "an"],
          "imperfetto": ["eva", "evat", "eva", "evum", "evuf", "evan"],
          "imperative": ["@3", "em", "ii"], "gerund": "endo", "participle": "üü"},
    "4": {"presente": ["i", "at", "a", "um", "uf", "an"],
          "imperfetto": ["iva", "ivat", "iva", "ivum", "ivuf", "ivan"],
          "imperative": ["a", "em", "ii"], "gerund": "endo", "participle": "ii"},
    "4i": {"presente": ["isi", "isat", "is", "isum", "isuf", "is"],
           "imperfetto": ["iva", "ivat", "iva", "ivum", "ivuf", "ivan"],
           "imperative": ["is", "isem", "isii"], "gerund": "endo", "participle": "ii"},
}
ENDINGS["3"] = ENDINGS["2"]
STRESSED_TENSES = {"presente", "futuro", "condizionale presente"}
PARTICLES = {"giò", "sü", "sù", "föra", "fö", "via", "insema", "innanz", "indré", "ben", "dré"}


def plain(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if not unicodedata.combining(c))


def join(stem, ending):
    """Attach an ending, with the spelling adjustments the lessons show:
    cerc+i = cerchi, mangi+em = mangem, mangi+ii = mangii, tai+i = tai."""
    if not ending:
        return stem
    first = ending[0]
    if first in "eiì" and stem[-1:] in "cg":
        return stem + "h" + ending
    if stem.endswith("i"):
        if first == "i":
            return stem + ending[1:]
        if first == "e" and stem[-2:-1] in ("c", "g"):
            return stem[:-1] + ending
    return stem + ending


def strip_clitics(form):
    form = re.sub(r"^(ma sa|ta sa|i sa|sa|ta|la/al|al/la|al|la|i)\s+", "", form.strip(), flags=re.I)
    return re.sub(r"^(la/al|al/la)\s+", "", form)


def head_word(form):
    words = strip_clitics(re.split(r"\s*/\s*|\s+o\s+|\s*\(", form)[0]).split()
    return words[0] if words else ""


def split_infinitive(infinitive):
    """'bürlà giò' -> ('bürlà', 'giò');  'vöras ben' -> ('vöras', 'ben')."""
    first = re.split(r"\s+o\s+|\s*/\s*", infinitive)[0].strip()
    words = first.split("-")[0].split()
    if len(words) > 1 and plain(words[-1]) in {plain(p) for p in PARTICLES}:
        return words[0], " ".join(words[1:])
    return (words[0] if words else ""), ""


def cut(word, endings):
    for e in sorted(endings, key=len, reverse=True):
        if word.endswith(e) and len(word) > len(e) + 1:
            return word[:-len(e)]
    return ""


def unharden(stem):
    return stem[:-1] if stem.endswith(("ch", "gh")) else stem


def derive(inf_head, cls, forms, reflexive):
    """Stressed and unstressed stem, from attested forms where possible."""
    base = inf_head[:-2] if reflexive else inf_head
    # a reflexive has already lost its -as (lav-as, svegli-as): its last letter is part of the stem
    guess = base[:-1] if not reflexive and cls in ("1", "2", "4", "4i") and base[-1:] in "àaéèìíi" else base

    def ok(stem):
        return stem if stem and plain(stem)[0] == plain(guess)[0] and abs(len(stem) - len(guess)) <= 3 else ""

    def first(tense, person):
        got = forms.get(tense, {}).get(person, [])
        return head_word(got[0]) if got else ""

    stressed = ok(unharden(cut(first("presente", "1p"), ["um"])))
    if not stressed:
        w = first("presente", "1s")
        stressed = ok(unharden(w[:-1]) if w.endswith(("i", "í")) and cls != "4i" and not guess.endswith("i") else "")
    if not stressed:
        # the conditional is written out in full by now (paga-ria -> pagaria): take its ending off
        w = re.split(r"-", first("condizionale presente", "1s"))[0]
        stressed = ok(unharden(cut(w, ["aressa", "aress", "aria", "eressa", "eress", "eria", "iressa", "iress", "iria",
                                       "ressa", "ress", "ria"])))
    unstressed = ok(cut(first("gerundio", "-"), ["ando", "andu", "and", "andos", "andus", "endo", "endu", "endos", "endus"]))
    if not unstressed:
        unstressed = ok(unharden(cut(first("imperativo negativo", "1p"), ["em", "emas"])))
    if cls == "4i":                                   # cüsis-um, partis-a: drop the -is- extension
        stressed = re.sub(r"is$", "", stressed) or stressed
        unstressed = re.sub(r"is$", "", unstressed) or unstressed
    stressed = stressed or unstressed or guess
    return stressed, unstressed or (guess if cls == "1" else stressed)


def conjugate(infinitive, cls, forms, p):
    """Predicted forms for one verb: {tense: {person: form}}.
    p = manual parameters (ss, us, pp, aux, pres3, kind); forms = attested forms."""
    head, particle = split_infinitive(infinitive)
    # reflexive: an infinitive in -as (lavas, setas giò), or kind=refl in etc/verb_details.csv for one
    # that does not end so (töss fö, the reflexive of töö)
    reflexive = (head.endswith("as") and len(head) > 3) or p.get("kind") == "refl"
    if p.get("kind") == "inc" and cls == "4":
        cls = "4i"
    if cls not in ENDINGS or not head:
        return {}
    ss, us = derive(head, cls, forms, reflexive)
    ss, us = p.get("ss") or ss, p.get("us") or p.get("ss") or us
    E = ENDINGS[cls]
    tail = f" {particle}" if particle else ""
    third = p.get("pres3") or (head if cls == "3" and not reflexive else ss)
    out = {}

    def simple(tense, endings, stem):
        row = {}
        for i, (person, ending) in enumerate(zip(PERSONS, endings)):
            if isinstance(ending, tuple):
                word = "/".join(join(stem, x) for x in ending)
            else:
                word = third if ending == "@3" else join(stem, ending)
            lead = REFLEXIVE[i] if reflexive else CLITIC.get(person, "")
            row[person] = f"{lead}{word}{tail}"
        return row

    ext = "is" if cls == "4i" else ""
    out["presente"] = simple("presente", E["presente"], ss)
    out["imperfetto"] = simple("imperfetto", E["imperfetto"], us)
    out["futuro"] = simple("futuro", FUT, ss + ext)
    out["condizionale presente"] = simple("condizionale presente", COND, ss + ext)

    participle = p.get("pp") or join(us, E["participle"])
    essere = reflexive or p.get("aux") == "essere"
    aux = AUX_REFLEXIVE if reflexive else AUX_ESSERE if essere else AUX_AVERE
    for tense in COMPOUND:
        out[tense] = {person: f"{a} {participle}{tail}" for person, a in zip(PERSONS, aux[tense])}

    if reflexive:
        imp = [join(ss, "at"), join(us, "emas"), join(us, "evas")]
    else:
        imp = [third if e == "@3" else join(ss if i == 0 else us, e) for i, e in enumerate(E["imperative"])]
        if cls == "3":
            imp[0] = head
    out["imperativo"] = {person: f"{w}{tail}" for person, w in zip(("2s", "1p", "2p"), imp)}
    out["imperativo negativo"] = {person: f"{w} mia{tail}" for person, w in zip(("2s", "1p", "2p"), imp)}
    out.update(subjunctive_rows(simple, ss + ("is" if cls == "4i" else ""), us + SUBJ_VOWEL[cls] + "ss"))
    out["gerundio"] = {"-": join(us, E["gerund"]) + ("s" if reflexive else "") + tail}
    out["participio passato"] = {"-": participle}
    return out


def subjunctive_rows(simple, present_stem, imperfect_stem):
    return {"congiuntivo presente": simple("congiuntivo presente", SUBJ_ENDINGS, present_stem),
            "congiuntivo imperfetto": simple("congiuntivo imperfetto", SUBJ_IMPERFECT_ENDINGS, imperfect_stem)}


def irregular_subjunctive(infinitive):
    """Subjunctive of ves, vegh, na, fa, dà, stà, dì, savé, podé, vöré (and their compounds: na giò)."""
    head, particle = split_infinitive(infinitive)
    reflexive = head.endswith("as") and len(head) > 3
    stems = SUBJ_IRREGULAR.get(head[:-2] if reflexive else head)
    if not stems:
        return {}
    tail = f" {particle}" if particle else ""

    def simple(tense, endings, stem):
        return {person: f"{(REFLEXIVE[i] if reflexive else CLITIC.get(person, ''))}{stem}{ending}{tail}"
                for i, (person, ending) in enumerate(zip(PERSONS, endings))}
    return subjunctive_rows(simple, *stems)


def compound_only(participle, essere):
    """For irregular verbs: only the tenses that are auxiliary + participle."""
    aux = AUX_ESSERE if essere else AUX_AVERE
    out = {t: {person: f"{a} {participle}" for person, a in zip(PERSONS, aux[t])} for t in COMPOUND}
    out["participio passato"] = {"-": participle}
    return out


def with_particle(table, particle):
    """Paradigm of 'na föra' from that of 'na'."""
    out = {}
    for tense, row in table.items():
        out[tense] = {}
        for person, form in row.items():
            if tense == "participio passato":
                out[tense][person] = form
            elif tense == "imperativo negativo":
                out[tense][person] = form + f" {particle}"
            else:
                out[tense][person] = " / ".join(f"{part.strip()} {particle}" for part in form.split(" / "))
    return out
