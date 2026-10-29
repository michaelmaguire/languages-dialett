"""The material's text is never published in this repository (owner, 2026-10-28: no permission).

Lines of documents of genre `text` (poems, stories, articles, dialogues) stay in the private
raw/extracted/; only the sayings and phrases kept by a row of etc/expression_topics.csv, and the
grammar's own examples, may appear in published files. Needs the raw/ submodule; skipped without it.
"""
import re

import pytest

from conftest import CLDF, DATA, ETC, PRIVATE, ROOT, build, read_csv, report

PUBLISHED = [p for d in ("Dictionary", "Expressions", "Verbs", "Grammar") for p in sorted((ROOT / d).glob("*.md"))] \
    + sorted(DATA.glob("*.csv")) + sorted(CLDF.glob("*.csv")) + [ROOT / "README.md", ROOT / "TO-CHECK.md"]


def norm(s):
    return re.sub(r"\s+", " ", build.key(s)).strip(" .,;:!?«»\"“”")


def test_no_text_lines_published():
    pairs = PRIVATE / "extracted_pairs.csv"
    if not pairs.exists():
        pytest.skip("needs the full extraction in the private raw/ submodule")
    texts = {r["file"] for r in read_csv(ETC / "lesson_sources.csv") if (r.get("genre") or "").strip() == "text"}
    kept = {norm(r["Form"]) for r in read_csv(ETC / "expression_topics.csv") if r.get("Genre")}
    kept |= {norm(r["Primary_Text"]) for r in read_csv(ETC / "grammar_examples.csv")}
    kept |= {norm(r["Form"]) for r in read_csv(ETC / "decisions.csv")}
    # a whole line of a text, long enough to be a quotation rather than a common phrase
    lines = {norm(p["dialect"]) for p in read_csv(pairs) if p["source"] in texts and len(p["dialect"]) >= 40}
    lines = {l for l in lines if l not in kept}
    published = {p.relative_to(ROOT): norm(p.read_text(encoding="utf-8")) for p in PUBLISHED if p.exists()}
    bad = [f"{path}: {line[:70]!r}" for line in sorted(lines) for path, text in published.items() if line in text]
    report(bad, "lines of texts found in published files")
