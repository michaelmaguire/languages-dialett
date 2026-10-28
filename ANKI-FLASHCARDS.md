# Anki flashcards

`pipeline/tool_flashcards.py` turns the dictionary, the verb charts and the expressions of this dataset
into an [Anki](https://apps.ankiweb.net/) deck (an `.apkg` file). It reads `cldf/` only, so corrections
made in `etc/` reach the cards after the next build. It is not part of the build and writes nothing in the
repository.

## What is in the deck

Every note gives two cards: **English → Dialett** and **Dialett → English**.

| Deck | One note per | Example |
|---|---|---|
| Dialett da Rögn::Words | dictionary entry with English, from every region | *pig; boar* ↔ **purcel**, *m., pl. purcei* |
| Dialett da Rögn::Verbs | verb form found in a course document | *to want · vöré, condizionale presente · ti* ↔ **vörariat/vöraressat** |
| Dialett da Rögn::Expressions::*topic* | saying or phrase with English, one sub-deck per topic | *I like this restaurant…* ↔ **Al ma pias quesctu risturant…** |

The region is shown on both sides of a word card (*Rögn (Arogno)*, *Basso Ceresio*, …), so two regions'
words for the same English are not confused. The back of a card also shows the Italian, other spellings
and the source document with its line.

Cards are tagged, for filtered decks in Anki: `word` / `verb` / `expression`, the region (`rogn`,
`ticinese`, …), the part of speech, the verb and tense, the expression's genre and topic, and `attested`
or `inferred` for verb forms.

## Making the deck

From `pipeline/` (the build's virtual environment has `genanki`, listed in `requirements.txt`):

```sh
.venv/bin/python tool_flashcards.py ~/Documents/dialett-da-rogn.apkg
```

| Option | Effect |
|---|---|
| `--decks words,verbs,expressions` | which decks to include (default: all three) |
| `--verbs pagare,essere` | only these verbs, by Italian infinitive (default: all verbs) |
| `--inferred` | also the verb forms predicted from the course patterns (†), marked on the card and tagged `inferred`. Left out by default so that guesses are not drilled |

Run `pipeline/build_all.sh` first if `etc/` has changed since the last build.

## Importing and updating

The first time: in Anki, **File → Import** and choose the `.apkg` file, then sync. On Android
(AnkiDroid) the file can also be opened directly.

After regenerating the deck:

1. Sync on the phone, then open Anki on the computer and sync there, so the computer has the latest reviews.
2. Regenerate the deck (above).
3. On the computer, **File → Import** the new `.apkg`, with **Update notes** set to *If newer* (the default)
   or *Always*.
4. Sync on the computer, then on the phone.

Import on one device only; syncing carries the changes to the others.

What happens on re-import:

- Each note's id comes from a CLDF ID: a word card from its entry's first sense (`sense:ul-un-purcel-il-un-maiale`),
  which stays the same when the headword is corrected; a verb card from the paradigm cell (`verb:paga-futuro-2s`);
  an expression from the example (`expr:…`). So a changed card (corrected form, new English, fixed plural) is
  **updated in place and keeps its review history**.
- New words, verb forms and expressions arrive as new cards.
- A note whose entry has gone from the data (for example two entries merged into one) is **not deleted** from
  Anki. Delete it by hand in the card browser if it turns up.
- Edits made to a card in Anki are overwritten by the next import. Corrections belong in `etc/` (see
  `etc/README.md`), where they also reach the dictionary and the PDFs.

## Known weaknesses

- Words without English (about 130) have no cards.
- Most verb cards show no source: the dataset does not record the line each found verb form came from.
- Noun plurals not given by a source are predicted (`pipeline/noun_plurals.py`); some are wrong. Corrections
  go in `etc/nouns.csv`.
