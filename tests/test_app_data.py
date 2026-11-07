"""The phone app's data (pipeline/step6_build_app_data.py, owner 2026-11-07): built from the same models as the
pages and PDFs, it must hold all of them and nothing the pages do not publish."""
import re

import pytest

from conftest import report

import dictionary_model
import expressions_model
import grammar_model
import step6_build_app_data as app
import verbs_model


@pytest.fixture(scope="module")
def data():
    return app.build()


def test_every_dictionary_entry(data):
    """Every headword of the Dialett look-up is in the app, except the "(= …)" rows that point from an
    alternate spelling to its entry (the app finds a word by any of its spellings)."""
    heads = [e["head"] for e in dictionary_model.entries(dictionary_model.load(), "dialect") if not app.POINTER.search(e["head"])]
    assert heads == [e["head"] for e in data["dictionary"]]


def test_every_verb_and_expression(data):
    """Every verb page and every expression, in the models' order."""
    assert [v["file"] for v in verbs_model.load()["verbs"]] == [v["id"] + ".md" for v in data["verbs"]]
    exprs = expressions_model.load()
    assert exprs["pairs"] == sum(len(s["entries"]) for t in data["expressions"] for s in t["sections"])
    assert [t["id"] for t in exprs["topics"]] == [t["id"] for t in data["expressions"]]


def test_every_grammar_chapter(data):
    model = grammar_model.load()
    assert [c["id"] for c in model["chapters"]] == [c["id"] for c in data["grammar"]]
    assert [len(c["blocks"]) for c in model["chapters"]] == [len(c["blocks"]) for c in data["grammar"]]


def test_verb_links_resolve(data):
    """Each link to a verb page (from a dictionary sense, or a grammar table) names a verb the app has."""
    ids = {v["id"] for v in data["verbs"]}
    bad = [f"{e['head']}: {s['verb']}" for e in data["dictionary"] for s in e["senses"] if s["verb"] and s["verb"] not in ids]
    for c in data["grammar"]:
        for b in c["blocks"]:
            if b["type"] == "verbs":
                bad += [f"{c['id']}: {x['verb']}" for x in [b["caption"], *b["columns"]] if x["verb"] and x["verb"] not in ids]
    report(bad, "links to verbs the app does not have")


def test_no_markdown_links(data):
    """Links to other pages are reduced to their text: those pages are not in the app."""
    bad = re.findall(r"\[[^\]]*\]\([^)]*\)", str(data["grammar"]))
    report(bad, "Markdown links left in the app's grammar")


def test_verb_tables_complete(data):
    """Every tense of a verb page has a form for each person, with the inferred ones marked."""
    bad = [f"{v['id']} {t['name']}" for v in data["verbs"] for t in v["tenses"] if not t["forms"] or any(not f["text"] for f in t["forms"])]
    report(bad, "verb tenses with missing forms")
