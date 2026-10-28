"""The feminine of an adjective or a past participle, predicted from the masculine.

Used by lexicon.py (adjectives: the Feminine column of cldf/entries.csv; etc/parts_of_speech.csv overrides)
and by the verb pages (the feminine participle). The patterns are the course's:

    -aa -> -ada   bagnaa, bagnada; tiraa, tirada; rivaa, rivada
    -üü -> -üda   sentüü, sentüda; perdüü, perdüda
    -ii -> -ida   finii, finida
    -i  -> -ia    the irregular participles: nai, naia; stai, sctaia; dai, daia
    -u  -> -a     negru, negra
    -ü  -> -üda   marü, marüda
    -ch -> -ca    stracch, stracca; spórch, spórca
    -cc -> -cia   (vecc has vegia: an override in etc/parts_of_speech.csv)
    -f  -> -va    vif, viva (a final -f is a -v at the end of a word)
    other consonants: add -a  (giall, gialla; fort, forta; grand, granda; gris, grisa)

A form ending in another vowel (blö, beige) or already in -a is returned unchanged as None: no feminine.
"""
import re

# words before an adjective that do not change in the feminine
MODIFIERS = {"mia", "ben", "pü", "tant", "tantu", "trop", "mal"}


def feminine(form):
    """The feminine of one masculine form, or None. 'tiraa / tirà' style alternatives are handled by
    feminine_all()."""
    w = form.strip()
    head, _, last = w.rpartition(" ")
    if head:
        # 'mia cuntent' -> 'mia cuntenta', 'ben visctii' -> 'ben visctida': only the adjective agrees
        if head.lower() not in MODIFIERS:
            return None
        f = feminine(last)
        return f"{head} {f}" if f else None
    if not w:
        return None
    for m, f in (("aa", "ada"), ("üü", "üda"), ("ii", "ida"), ("ch", "ca"), ("cc", "cia")):
        if w.endswith(m):
            return w[:-len(m)] + f
    if w.endswith("ü"):
        return w + "da"                                      # marü, marüda (owner)
    if w.endswith("i"):
        return w + "a"
    if w.endswith("u"):
        return w[:-1] + "a"
    if w.endswith("f"):
        return w[:-1] + "va"
    if re.search(r"[bcdgklmnprstvzñ]$", w):
        return w + "a"
    return None


def feminine_all(forms):
    """'curüü / corüü' -> 'curüda / corüda'; None when no alternative has a feminine."""
    out = [feminine(f) for f in re.split(r"\s*/\s*", forms or "")]
    return " / ".join(f for f in out if f) or None


def with_feminine(forms, fem=None):
    """'rubaa' -> 'rubaa/rubada'; 'curüü / corüü' -> 'curüü/curüda, corüü/corüda'. fem: a feminine already
    known (an adjective's Feminine column), used for a single form. Forms with no feminine are unchanged."""
    parts = [f.strip() for f in re.split(r"\s+/\s+", forms or "") if f.strip()]
    if fem and len(parts) == 1:
        return f"{parts[0]}/{fem}"
    if fem:
        return f"{forms} ({fem})"
    out = [f"{f}/{feminine(f)}" if feminine(f) else f for f in parts]
    return ", ".join(out) if any("/" in o for o in out) else (forms or "")
