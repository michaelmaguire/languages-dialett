"""Typographic quotes for the text this project writes itself (typesetting review, owner, 2026-10-31).

smart() turns straight quotes into curly ones: "…" into “…”, '…' into ‘…’, and any other ' into the
apostrophe ’ (people’s, All Souls’ Day, l’è). Used on the English, the notes and the grammar's explanations
in etc/, never on the course's own text (dialect and Italian are kept as the teacher wrote them)."""
import re

_OPEN_DOUBLE = re.compile(r'(^|[\s(\[{—–/])"')
_SINGLE_PAIR = re.compile(r"(^|[\s(\[{—–/])'([^'\n]*?\w[.,;:!?…]?)'(?=$|[\s)\]},.;:!?—–/])")


def smart(text):
    """text with typographic quotes and apostrophes."""
    text = _OPEN_DOUBLE.sub(r"\1“", text).replace('"', "”")
    text = _SINGLE_PAIR.sub(r"\1‘\2’", text)
    return text.replace("'", "’")
