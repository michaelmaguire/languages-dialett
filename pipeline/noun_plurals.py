"""Predict the plural of a Rögn noun from its singular and gender, from the patterns of the plurals the
course gives (mostly lesson 6). Used by lexicon.noun_forms() for nouns whose sources give no plural; a
wrong prediction is corrected in etc/nouns.csv. Tested against the attested plurals in the build output.

Masculine: invariable (can, gatt, ors), except a stressed final -l (caval, purcel, söl -> cavai, purcei,
söi), -u/-o -> -i (merlu, cervo -> merli, cervi), -ett/-et -> -itt/-it (cavrett -> cavritt).
Feminine: the final -a drops (pegura -> pegur), -ca -> -cc (vaca -> vacc), a cluster that cannot end a
word takes -i (magiosctra -> magiosctri); feminines not in -a are invariable (golp),
-gia/-cia -> -gg/-cc (vigia -> vigg).
In a compound only the noun and the words agreeing with it change, not what follows a preposition
(dona da cà -> donn da cà, rösa marina -> rös marin).
"""
import re
import unicodedata

PREPOSITIONS = {"da", "dal", "dala", "dai", "di", "dii", "del", "dela", "in", "int", "a", "al", "ala", "cul",
                "cun", "cunt", "par", "de", "d’", "d'", "sü", "sota", "e", "o"}
ACCENTS = str.maketrans("àèéìòóù", "aeeioou")
VOWELS = "aeiouöüàèéìòóù"


def _unaccent_last(w):
    return w[:-3] + w[-3:].translate(ACCENTS)


def _word(w, gender):
    lw = w.lower()
    if gender == "f":
        if not lw.endswith("a") or len(lw) < 3:
            return w
        stem = w[:-1]
        if stem.lower().endswith(("gi", "ci")) and len(stem) > 3:
            return stem[:-1] + stem[-2]                          # vigia -> vigg, sacocia -> sacocc
        if re.search(r"[^aeiouöüàèéìòóù]c$", stem.lower()) is None and stem.lower().endswith("c"):
            return stem + "c"                                    # vaca -> vacc
        if re.search(r"[bcdfgptv][rl]$", stem.lower()):
            return stem + "i"                                    # magiosctra -> magiosctri
        if re.search(r"[èé]l$", stem.lower()):
            return _unaccent_last(stem) + "l"                    # surèla -> surell
        if stem.lower().endswith("et"):
            return stem + "t"                                    # scigueta -> sciguett
        return stem
    # masculine (and unknown)
    if re.search(rf"[{VOWELS}]ll?$", lw) and not re.search(r"(in|un|on|an)$", lw):
        return _unaccent_last(re.sub(r"ll?$", "", w)) + "i"      # caval -> cavai, purcel -> purcei
    if re.search(r"[^aeiou][uo]$", lw):
        return w[:-1] + "i"                                      # merlu -> merli, cervo -> cervi
    if lw.endswith("ett"):
        return w[:-3] + "itt"                                    # cavrett -> cavritt
    if lw.endswith("et") and len(lw) > 3:
        return w[:-2] + "it"                                     # picet -> picit
    return w


def predict(singular, gender):
    """The plural of a noun (headword without article), or the singular when it does not change."""
    out = []
    for alt in re.split(r"\s*/\s*", re.sub(r"\s*\([^)]*\)", "", singular).strip()):
        words, changed, stop = alt.split(), [], False
        for i, w in enumerate(words):
            if w.lower() in PREPOSITIONS and i > 0:
                stop = True
            changed.append(w if stop else _word(w, gender))
        out.append(" ".join(changed))
    return " / ".join(out)
