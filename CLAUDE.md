# languages-dialett: notes for Claude

This file is loaded automatically by Claude Code. It records what the repo is, how it is built and the
decisions already made, so work can resume from a fresh context.

## What this is

A public GitHub repo (`michaelmaguire/languages-dialett`) that is a **cldfbench dataset** (id `rogn`): material
from a weekly course in the Lombard dialect of Arogno (*Rögn*), Lugano district, Ticino. The owner,
Michael Maguire, is a native English speaker who reads Italian. Until 2026-10-14 everything lived in a
`Dialect/` folder; it was moved to the repository root so the repo follows cldfbench conventions (one
dataset per repository, ready for a Zenodo release). For a while `Dialect/` kept copies of the dictionary and
verb PDFs at their old shared URLs; the owner had them removed on 2026-10-19, so those old links no longer work.
The repository itself was renamed on GitHub from `languages` to `languages-dialett` at the same time;
GitHub redirects the old URLs, so never create a new repo called `languages`, or the redirects break. The local checkout may still be in a folder called `languages`.

Course documents (Word, PDF, some scanned) go in `raw/`. A Python pipeline turns them, with the curation
in `etc/`, into a CLDF dataset in `cldf/`, and from that into a three-language dictionary, expression
pages grouped by topic, 501-Verbs-style conjugation charts, a bilingual grammar and four printable PDFs.

## Layout (cldfbench conventions: raw/ → etc/ → cldf/)

```
README.md, TO-CHECK.md       GENERATED from cldf/ (README intro from pipeline/templates/readme_intro.md);
                             TO-CHECK.md is in Italian, for checking with the teacher (owner, 2026-10-14)
CLAUDE.md                    this file
raw/                         SOURCE DATA, never modified: course documents, the owner's spreadsheet
                             (Rosetta Stone_….xlsx) and notes_added_by_hand.csv (owner's handwritten notes).
                             A private git submodule (michaelmaguire/languages-dialett-raw, SSH URL): the
                             build must keep working without it (see "Building")
etc/                         CURATION: every decision and correction (see etc/README.md). Edit these.
cldf/                        THE CLDF DATASET (Dictionary module, https://cldf.clld.org/). Regenerated from
                             etc/ + the extraction of raw/ saved in pipeline/data/ on every build by
                             cldfbench: NEVER edit by hand.
cldfbench_rogn.py            cldfbench dataset definition; makecldf calls pipeline/lexicon.py
metadata.json                cldfbench metadata: licence CC-BY-4.0, creator Michael Maguire (owner's choice)
setup.py, setup.cfg, test.py registers the dataset with cldfbench (`pip install -e .`, then `cldfbench ls rogn`);
                             `pytest` runs the standard pytest-cldf validation
CONTRIBUTORS.md, LICENSE, .zenodo.json   cldfbench / Zenodo release files (hand-written)
ANKI-FLASHCARDS.md           hand-written: the Anki deck script (pipeline/tool_flashcards.py), how to import and update
Dictionary/ Expressions/ Verbs/ Grammar/   GENERATED from cldf/ (pages cleared and rewritten every build; the
                             PDFs are kept until step 5 replaces them). Do not commit while a build is running
ATTRIBUTIONS.md              hand-written: thanks, authors, tools, what Claude generated. Printed after the
                             cover of all four PDFs. Add a row when a new document brings in a new author.
                             The teacher, Guido Casellini, is credited at the owner's request.
pipeline/                    the build: README.md there has the data-flow diagram and all file roles
```

## Building

```sh
pipeline/build_all.sh
```

| Step | Script | Reads | Writes |
|---|---|---|---|
| 1 | `step1_extract_text.py` | `raw/*.docx`, `*.pdf` | `pipeline/cache/lesson_text/*.txt`; new rows in `etc/lesson_sources.csv` |
| 2 | `step2_find_pairs_and_verbs.py` | the text, `etc/lesson_sources.csv`, `raw/notes_added_by_hand.csv` | `pipeline/data/extracted_*.csv`, `unparsed_lines.csv` |
| 3 | `step3_make_cldf.py` → `cldfbench_rogn.py` → `lexicon.py` | step 2 output + all of `etc/` + owner's spreadsheet and notes (from `raw/`, else `pipeline/data/owner_*.csv`) | fresh `pipeline/data/owner_*.csv` copies when `raw/` is there; `cldf/` from scratch; then `cldf validate` (build stops if invalid) |
| 4 | `step4_build_pages.py` (+ `grammar.py`) | `cldf/` only (the grammar from `cldf/grammar/`) | all Markdown; `pipeline/data/dictionary.csv`, `expressions.csv`, `verb_tables.csv` |
| 5 | `step5_build_pdfs.py` (+ `grammar.py`) | `cldf/`, `pipeline/data/dictionary.csv` (from step 4), `pipeline/templates/cover_*.html`, `ATTRIBUTIONS.md` | the four PDFs |

Step 3 uses cldfbench's Python interface because `cldfbench makecldf` on the command line demands a local
Glottolog catalogue, which this dataset does not use (codes set in `lexicon.py`).

### Setting up a machine

These are the packages the owner was asked to install (Ubuntu), plus what was already there:

```sh
sudo apt install python3-venv python3-pip poppler-utils tesseract-ocr tesseract-ocr-ita tesseract-ocr-deu hunspell-it
```

| Package | Why | Status on the owner's machine |
|---|---|---|
| `python3-venv`, `python3-pip` | to create `pipeline/.venv`; Ubuntu blocks system-wide pip | installed on request |
| `openpyxl`, `pycldf`, `cldfbench`, `pypdf`, `genanki`, `pytest-cldf` (pip, inside the venv) | read the owner's spreadsheet; build and validate the CLDF dataset; read back page numbers for the PDF contents pages; write Anki decks (`pipeline/tool_flashcards.py`, owner's request 2026-10-15); run `test.py` (`pipeline/.venv/bin/python -m pytest test.py`, installed 2026-10-19) | installed by `build_all.sh` from `requirements.txt`. The venv holds absolute paths: if the repo folder is renamed or moved, delete `pipeline/.venv` and rebuild |
| `tesseract-ocr`, `tesseract-ocr-ita`, `tesseract-ocr-deu` | OCR of scanned lessons; German so that ü and ö survive | installed on request |
| `poppler-utils` | `pdftotext`, `pdftoppm` | was already installed |
| Google Chrome or Chromium | prints the PDFs; step is skipped with a message if absent | was already installed |
| `hunspell-it` | Italian word list (`/usr/share/hunspell/it_IT.dic`) used to tell Italian from dialect; `step2_find_pairs_and_verbs.py` falls back to a copy inside the Firefox or Thunderbird snap, then to no list | installed on request |
| `ocrmypdf` | none | installed on request early on, but the pipeline calls tesseract directly and does not use it |

`raw/` may be a private submodule (`michaelmaguire/languages-dialett-raw`). Without it, `build_all.sh`
skips steps 1-2 and builds from the committed `pipeline/data/extracted_*.csv` plus the copies of the
owner's spreadsheet and notes in `pipeline/data/owner_*.csv` (refreshed by every full build), so decisions
in `etc/` still apply and all output is regenerated. Steps 1-2 refuse to run on an empty `raw/`.

Extraction is cached by file hash; OCR of all scans takes over ten minutes from cold, so keep
`cache/lesson_text/` in git.

After a build, check the summary lines it prints (entries, senses, examples, found versus inferred verb
forms, entries without English, decisions that matched nothing) and the `git diff` of `cldf/` and the pages.

## Curation files (in `etc/`; details in etc/README.md)

| File | Purpose |
|---|---|
| `decisions.csv` | Decisions about dictionary entries and expressions: `typo` (fold into the correct form, keep the typo as a variant), `reject`, `accept` (clear ⚠), `variant`, `correct` (fix dialect/Italian/English), `expression` (an idiom or sentence that had landed in the dictionary: it becomes an expression). Columns `Decision,Language_ID,Form,Sense,Target_Form,Target_Language_ID,Italian,English,Reason,Date`. **This is where the owner's corrections go.** Rows whose Reason starts "Claude inferred:" came from Claude's full review on 2026-10-14 (about 260 rows, plus 93 `expression` rows); the owner's have no prefix. |
| `pair_corrections.csv` | Delete / replace / add an extracted pair, by `source,line` from `pipeline/data/extracted_pairs.csv`. |
| `lesson_sources.csv` | One row per document: variety, canonical yes/no, layout (`auto`, `skip`, `text_only`, `gerund`, `imperative`, `bullets`, `parallel`), include, genre of its expressions (`phrase`, `saying`, `exercise`, `text`). New files arrive with `?`. |
| `topics.csv` | The expression topics (ID, dialect name, Italian name, English name), in page order. Dialect names composed by Claude from course words; † on a word not found in any course document (listed in `TO-CHECK.md`). |
| `expression_topics.csv` | One row per expression (`Language_ID,Form,Topic,Genre`, Form = dialect text): its topic, and a genre when it differs from its document's. Written by Claude on 2026-10-14; new expressions via `tool_expression_topics.py`. |
| `spelling_variants.csv` | Spellings of one word that all occur in the lessons (`giò;giô;giõ`); all accepted as `spelling` variants and shown together in the dictionary. The Dialett look-up (Markdown and PDF) also lists every alternate spelling in its own place, pointing to the full entry (*scultà → scoltà o scultà*), so a word is found however it is written; a spelling that differs only by accents or a doubled letter (*pé*, *pee* for *pè*) gets no pointer, since it sorts next to the entry anyway (owner saw them as duplicates, 2026-10-15). `TO-CHECK.md` asks Guido which spelling he prefers; the answer only changes which comes first. |
| `open_questions.csv` | Open questions for the teacher (Area, About, Question, Current_Handling, Date), shown at the top of `TO-CHECK.md`. Only real uncertainties (owner: do not be pedantic with the teacher); never spellings, which the lessons settle by using them (see `spelling_variants.csv`). Delete a row once answered and recorded. |
| `english_translations.csv` | Italian → English, keyed by the Italian text. |
| `verb_details.csv` | Per verb: dialect infinitive (attested/inferred/confirmed + evidence), merges, class, stems, participle, auxiliary, tenses to ignore, a particle to drop (`drop_particle`: the *gh’* of *avere* in conditional and subjunctive, owner 2026-10-19). |
| `verb_forms_from_texts.csv` | Verb forms found in running text (attested, with `source,line`), supplied by hand (inferred) or confirmed by the owner (`confirmed`). With a `verb_details.csv` row, enough to give an untabled verb a page (*töö*, *duprà*). |
| `verb_forms_reassigned.csv` | Moves extracted forms to another verb when two dialect verbs share an Italian infinitive (*töö* vs *ciapà* for *prendere*). |
| `parallel_texts.csv` | Class translations and their Italian originals in other documents, aligned by step 2 (*I düü magnan*, Inferno I–VI against `raw/Divina Commedia Inferno I-VI (Dante, Project Gutenberg).txt`). |
| `nouns.csv` | Nouns whose source gives no article (gender), and corrections of gender or plural: `Language_ID,Form,Gender,Plural,Reason`, Form as written in the source. About 400 rows written by Claude on 2026-10-15 (every noun gets m./f.): gender from an article in the lesson texts where one is found (cited), else a best guess from the Italian. A Plural written in the headword (`curtel/curtei`, `sedèla (sedèl)`) is removed from it. |
| `dialect_lists_italian_supplied.csv` | Dialect-only list words (lessons 1–2, 5, 6) with Italian/English supplied by Claude; Italian shown with †. |
| `grammar/NN-slug.md` | The grammar's chapters (CLDF Markdown; format in the docstring of `pipeline/grammar.py`): `IT:`/`EN:` paragraph pairs printed side by side, `[](ExampleTable#cldf:ID)` and `[](EntryTable#cldf:ciapa?tenses=presente)` lines for examples and verb tables, dialect tables. The number in the file name is the chapter number (`00` = introduction, unnumbered). Text drafted by Claude, 2026-10-19. |
| `grammar_examples.csv` | The grammar's examples: `ID,Primary_Text,Analyzed_Word,Gloss,Italian,English,Source,Line,Comment`. Every one is quoted from a canonical document; the build warns if `Primary_Text` is not on the cited line, if a chapter uses an unknown ID, or if words and glosses differ in number. Glosses are Leipzig-style, Claude's (abbreviations in chapter 00). |

Templates (not data) are in `pipeline/templates/`: `readme_intro.md`, `cldf_readme_intro.md`,
`cover_verbs.html`, `cover_dictionary.html`, `cover_expressions.html`, `cover_grammar.html` (`{{…}}` placeholders filled at build time).

## Decisions already made (do not relitigate)

- **CLDF via cldfbench (decided 2026-10-14).** `cldf/` follows CLDF exactly (Dictionary module, extended
  conformance) and is regenerated from `raw/` + `etc/`; decisions live in `etc/`, never in `cldf/`.
  Senses: `Description` is Italian, English in the added `Description_English`. One `languages.csv` row
  per variety, all Glottocode `lomb1257` / ISO `lmo`. IDs `[a-zA-Z0-9_-]+` derived from the headword.
  Homographs are separate entries (verb `vert` vs colour `vert`). **Nouns (owner, 2026-10-15):** the
  headword is the bare word without its article (`purcel`, not `ul/un purcel`); Part_Of_Speech `noun`;
  custom columns `Gender` (m/f, from the article, else the Italian, else `etc/nouns.csv`) and `Plural`
  (from the source, else predicted by `pipeline/noun_plurals.py`), stored as plain values with no
  attested/inferred flag (owner: wrong values get corrected in `etc/nouns.csv`). Dictionary pages and PDF
  print *m., pl. purcei* after every noun. A leading `al/la/l’` is only an article when it is a pair or the
  Italian has one too: `al piöf` (piove) and `l’è …` keep their clitic. Done by `noun_forms()` after the
  decisions; it also merges entries that become the same word (`piöcc` / `ul/un piöcc`), keeps the source
  form as a variant of Kind `article`, and strips the article from the senses' Italian and English. Nothing is deleted: typos and wrong
  rows get status `typo`/`rejected`. Sources cited as `key[l.N]` (line in `pipeline/cache/lesson_text`).
- **Canonical variety:** the Rögn course lessons and the teacher's own exercise sheets. Other varieties
  stay in the same dictionary pages with a **Region** column.
- **Output is Markdown** in folders at the repository root, plus four PDFs. No spreadsheet output.
- **Teacher's spelling is kept** as written, variants included. Exceptions: Word's automatic capitals
  are lowered on words and non-sentence phrases, "idem" is replaced by the text it refers to, the
  conditional sheets' hyphens (`ciapa-ria/ress`) are written out (`ciaparia/ciaparess`), quotation marks around a whole expression are dropped (`«Dài, ta spéci l’ann che vegn!»`; owner, 2026-10-15), and the third
  person is always `la/al` (feminine first, as the teacher mostly writes it; the few `al/la` are normalised)
  under the label *le / lü* (owner, 2026-10-14). `l'a` in compound tenses is the auxiliary (*lü l'a
  credüü*), not the feminine clitic.
- **Markers:** ⚠ = `pending` (the extraction was unsure: direction, split or pairing). † = inferred, not
  found in a document (verb forms, verb infinitives, Italian supplied for dialect-only lists). On verb
  pages a fully inferred column carries † in its heading only. Marker explanations live only in the
  READMEs and on the PDF covers.
- **Look-ups give the Rögn word:** from Italian or English, an entry from another region is hidden when a
  Rögn entry has the same Italian or English (owner, 2026-10-14). English pages: English, Dialett, Italiano.
  One row per headword: senses and regional forms share it, and a form contained in another form of the
  same region is dropped (`merge_same_head()`, used by pages and PDF).
- **Dictionary:** three pages named for the look-up language (Dialett lists every entry), verbs included
  (English as `to …`). The owner's spreadsheet and notes are ordinary sources. No mention of "Oxford 3000".
- **Expressions (decided 2026-10-14):** grouped by **topic** (`etc/topics.csv`), not by lesson. Topics are named
  Dialett · Italiano · English; page files follow the verb pages, dialect then Italian:
  `mangia-e-bef-cibo.md` (slug of the dialect name, then the topic ID). Each topic page
  (columns Dialett, Italiano, English, sorted by the dialect, as in the PDF) lists sayings and idioms (genre `saying`), then phrases (`phrase`, `exercise`); the same dialect text from
  several documents is one row with every source. **Source texts are not reprinted** (owner, 2026-10-14):
  lines of genre `text` documents (poems, stories, articles, dialogues, `varie situazioni`) stay in `cldf/`
  and `pipeline/` as raw material but appear on no page and in no PDF. Sayings and self-contained everyday
  phrases found in them are kept as expressions: their row in `etc/expression_topics.csv` overrides the
  genre (`saying`/`phrase`) and gives a topic (about 80 so far, mostly from the teacher's two sheets; from
  published texts only short idioms). In `cldf/` this follows
  the TextCorpus pattern: `contributions.csv` (one row per document) with `Contribution_ID` and `Position` on
  each example, plus `Genre` and `Topic_ID` (FK to `topics.csv`). `senses.csv` has `Example_IDs`, linked
  automatically (dialect word and its Italian stem must both appear). Idioms, similes and sentences do not
  belong in the dictionary: move them with an `expression` decision. PDF `arogno-expressions.pdf`: topics in two
  columns (dialect first, sorted by dialect); no texts.
- **Grammar (decided 2026-10-19):** a short learner's grammar, `Grammar/` and `Grammar/arogno-grammar.pdf`,
  from `etc/grammar/` + `etc/grammar_examples.csv`. Explanations in Italian and English in two columns
  throughout (owner); examples and tables in dialect. Examples only from canonical documents, cited by line
  (not from *Chi che l'è un vero ticinés*, whose variety is unverified). In `cldf/` the chapters are copied
  to `cldf/grammar/` and listed in `media.csv` (MediaTable); the examples are rows of `examples.csv` with
  `Analyzed_Word`/`Gloss`, Genre `grammar`, Contribution `grammar` (shown only in the grammar, not on the
  expression pages). † marks a rule Claude worked out rather than one the course states. Outline after the
  Wikibooks Lombard grammar (topics only; its text is CC BY-SA and was not copied). Chapter 10, pronouns
  attached to the verb (*dimm*, *purtam*, *setevas*), was the owner's request. Questions it raises are in
  `etc/open_questions.csv` (Area `Grammatica`).
- **Verb pages:** Infinitive section (Dialett, Italiano, English), then gerund, participle and class,
  then Indicativo as two three-tense tables (A4), Condizionale, Imperativo; same sections for every verb.
  Classes follow the four Western Lombard conjugations (not from the course).
- **Verb forms:** a form found in a document always wins; gaps predicted by `verb_conjugator.py` from
  lessons 8, 17, 18. Auxiliary *ves* for reflexives, compounds of `na`, and `aux=essere` in
  `etc/verb_details.csv`; otherwise *vegh*.
- **English** is produced by Claude translating the Italian in a session, not by an API script. Never
  guess a translation for an entry whose "Italian" side is really dialect.
- **PDFs** open with cover, contents (page numbers from a two-pass print), attributions. The edition
  stamp is at the top right of both covers. The joke publisher on the covers is MAGUIRE’S. In the
  dictionary PDF a headword's senses share one line. **PDF names** start with `arogno-`. Every PDF cover shows an edition `YYYYMMDDhhmm` (24-hour local
  time) filled into `{{edition}}`; `step5_build_pdfs.py` adds it even if a cover lacks the placeholder.

## Adding new material

1. Put documents in `raw/` (commit and push there: it is a submodule) and run `build_all.sh`. Vocabulary from the owner's handwritten notes
   (same course, so canonical Rögn) goes in `raw/notes_added_by_hand.csv` exactly as written. For scans
   of those notes, transcribe by reading the images in the session, not with tesseract (handwriting).
2. Classify the new rows in `etc/lesson_sources.csv` (variety, canonical, layout) and rebuild.
3. From `pipeline/`, run `.venv/bin/python tool_missing_english.py list`, translate, save as
   `id<TAB>english` lines and feed back with `tool_missing_english.py merge FILE`. Then give new expressions a
   topic: `tool_expression_topics.py list`, choose a topic ID for each, `tool_expression_topics.py merge FILE`
   (`n<TAB>topic` lines). Set the document's `genre` in `etc/lesson_sources.csv` first. Lines of a `text` are not
   listed; to keep a saying or phrase from one, add its row to `etc/expression_topics.csv` with a Genre.
   An idiom or sentence that lands in the dictionary gets an `expression` row in `etc/decisions.csv`.
4. Check for silently dropped lines: list every line of each canonical document that produced no pair,
   verb form or unparsed row. This is how `Grembiule: scusaa` (lesson 4) and the bulleted pairs in
   `brevi frasi` were found. Also look at `pipeline/data/unparsed_lines.csv`.
5. For new verbs, add the infinitive and evidence to `etc/verb_details.csv`.
6. Owner's corrections ("X is a typo for Y") go in `etc/decisions.csv`, never in `raw/` or `cldf/`.
7. Before finishing, rebuild and compare the pages and `cldf/` with the previous version (`git diff`).

## Known gaps

- About 120 entries have no English: a block of well-known quotations at the end of `frasi fai 1` (an
  attempt to translate them in bulk was blocked by an output filter), entries with dialect on the Italian
  side, and nickname pairs.
- About 50 rows are still `pending` (⚠) after the 2026-10-14 review. Poems and prose produce fragments rather than clean pairs. Some
  headwords still hold several forms in one (`sacocia / scarsèla`): candidates for `variant` decisions.
- Roughly three quarters of verb forms are inferred. The weakest are `savé` and `duvé`, reflexive
  compound tenses, and futures and conditionals of -ì verbs with -is-. `TO-CHECK.md` lists them all.
- `Paul e Ghita`, `Topolino` and other dialect-only or multi-column texts are OCR'd but not used for the
  dictionary.
- Dialect lines on the dictionary and verb PDF covers were written by Claude, not the teacher (the two sayings on
  the expressions cover are from the course).
- Expression topics are Claude's judgement (`etc/expression_topics.csv`); *La vita e la saggezza* and
  *Carattere* are large catch-alls. A few single words are still among the expressions (13a: *falce per
  l'erba*, *gerla*, *carro*; 14a *ciliegio*; ): no decision moves an expression into the dictionary yet (a wrongly joined pair can be split with
  `etc/pair_corrections.csv`, as Gaggini's *cröcc / cumãa* was).
- The grammar has not been checked by the teacher. Its weakest parts: the subjunctive (no table in the course),
  the object pronouns for "us" and "them", and the doubled consonants (*lavass*, *dimm*).
- `Example_IDs` links only about 90 senses: the dialect word must appear in the expression exactly as
  written (inflected adjectives and nouns are missed), and words under four letters are skipped.
- `raw/` contains third-party material (published texts, the teacher's handouts, classmates' names).
  The owner has been told; do not add more of it to generated pages than is already there without asking.

## Working preferences for this repo

- Do not commit or push unless asked; the owner does that.
- When a better tool or package is missing, stop and suggest it with the install command rather than
  working around it. The owner runs `sudo` commands in their own terminal.
- Report counts and known weaknesses plainly after each change; say what was and was not verified.
- Prefer fixing the parser or an input file over patching generated output.
