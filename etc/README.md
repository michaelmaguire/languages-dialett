# Curation: `etc/`

In [cldfbench](https://github.com/cldf/cldfbench) terms this is the configuration directory: the data
that guides the conversion of the raw sources in [`../raw/`](https://github.com/michaelmaguire/languages-dialett-raw) into the CLDF dataset in
[`../cldf/`](../cldf/). **Every decision about the data lives here.** The dataset and all the pages are
regenerated from `raw/` + `etc/` on every build (`../pipeline/build_all.sh`), so this is the only place
to make a correction that lasts. Decisions here can be applied even without `raw/`: the build then uses
the extraction saved in `../pipeline/data/` (see the pipeline README).

| File | One row per | What it decides |
|---|---|---|
| [`decisions.csv`](decisions.csv) | decision about a dictionary entry or an expression | Typos, rejections, corrections, acceptance of uncertain (⚠) rows, variants, sayings moved out of the dictionary. Format below. |
| [`pair_corrections.csv`](pair_corrections.csv) | extracted pair | Delete, replace or add a pair found by the parser: `source,line,action,italian,dialect,english,note,kind`, where `source` and `line` come from `../pipeline/data/extracted_pairs.csv` and `action` is `delete`, `replace` or `add`. `kind` (`word` or `expression`) is optional; an added pair takes the variety of the pair on the same line. |
| [`lesson_sources.csv`](lesson_sources.csv) | document in `raw/` | Its dialect variety, whether it is canonical Rögn course material, how to parse it (`layout`: `auto`, `skip`, `text_only`, `gerund`, `imperative`, `bullets`, or `parallel` for a class translation aligned with its Italian original, see `parallel_texts.csv`), whether to include it, and the `genre` of its expressions: `phrase`, `saying` (proverbs, idioms, similes), `exercise` (grammar sheets) or `text` (poems, stories, articles, dialogues: kept in `../cldf/` only, never reprinted on the pages or in a PDF). New documents are added automatically with `?` to fill in. |
| [`parallel_texts.csv`](parallel_texts.csv) | translation | A dialect document (layout `parallel`) and its Italian original in another file: `dialect_file,italian_file,unit,part,notes`. `unit` is `sentence` (prose) or `line` (verse, aligned within each canto); `part` names the canto when the dialect file has no headings. Step 2 aligns the two texts and each pair cites both documents. The original may be a `.txt` in `raw/` (Dante's Italian from Project Gutenberg). |
| [`topics.csv`](topics.csv) | topic | The topics expressions are grouped by (`ID`, `Name_Dialect`, Italian `Name`, `Name_English`), in the order of the pages. The dialect names were composed by Claude from words in the course; † follows a word not found in any course document. A page is named from the dialect name and the ID (`mangia-e-bef-cibo.md`), so renaming a topic renames its page. |
| [`expression_topics.csv`](expression_topics.csv) | expression | Its `Topic` (an ID from `topics.csv`), and a `Genre` when it differs from its document's (a proverb in a list of phrases, or a saying or phrase worth keeping from a `text`). Keyed by `Language_ID` and `Form`, the dialect text as in `../cldf/examples.csv`. Added with `../pipeline/tool_expression_topics.py`. |
| [`spelling_variants.csv`](spelling_variants.csv) | dictionary word | `Language_ID,Headword,Variants,Evidence`: other spellings of the same word that the lessons use (`giò` with `giô;giõ`, `sempru` with `sémpru`). All are accepted and none is preferred: each becomes a `spelling` variant in `../cldf/variants.csv`, and the dictionary shows them together (*giò / giô / giõ*). In the Dialett look-up each spelling also has its own entry pointing to the full one, so any spelling can be looked up. `../TO-CHECK.md` lists the sets for Guido to say which he prefers; put that spelling first in `Headword`. Verb inflections (*ciapa*, *ciapaa*) and different words that differ by an accent (*da*, *dà*) are not variants. |
| [`open_questions.csv`](open_questions.csv) | open question | Written in Italian, as it appears in `../TO-CHECK.md`. A real uncertainty only the teacher can settle (a form the course does not give), with how the pages show it meanwhile. Not for spellings: when the lessons spell a word several ways, all go in `spelling_variants.csv`. Listed in `../TO-CHECK.md`; when answered, record the answer in the right file here and delete the row. |
| [`nouns.csv`](nouns.csv) | noun needing help | `Language_ID,Form,Gender,Plural,Reason`. Marks a headword as a noun when its source gives no article (and so no gender), and corrects a gender or a plural. `Form` is the headword as the source writes it, article included (`l’istaa`, `la dona da cà`). Blank fields leave the automatic value. A Plural written in the headword (`curtel/curtei`, `sedèla (sedèl)`) is taken out of it. Reasons starting “Claude inferred: the gender from the texts” cite the article found; “best guess from the Italian” rows are the ones to check. |
| [`english_translations.csv`](english_translations.csv) | Italian text | Its English. Every translation is made once and kept here. |
| [`verb_details.csv`](verb_details.csv) | verb needing help | Dialect infinitive (attested or inferred, with the evidence), merges of duplicate verbs, class, stems, participle, auxiliary, tenses to ignore, and `also_italian`: more Italian infinitives of the same dialect verb, `;`-separated (*töö*: `prendere`). `basis` `confirmed` = the owner confirmed the infinitive (no †). `drop_particle` and `drop_particle_tenses` (both `;`-separated): a particle the documents write with the verb that is not part of it, removed in those tenses (*avere*: `gh’;g’` in the conditional and subjunctive, so *ta gh’avressat* is shown *t’avressat*; owner, 2026-10-19). A verb no lesson conjugates in a table gets a page when it has a row here and an attested form in `verb_forms_from_texts.csv` (*töö*, *duprà*). |
| [`verb_forms_from_texts.csv`](verb_forms_from_texts.csv) | verb form | `italian,tense,person,form,basis,source,line`: a form found in running text (`basis` = `attested`, with the document and line it is cited from in `../cldf/paradigms.csv`), supplied by hand (`inferred`), or confirmed by the owner (`confirmed`, no source: shown without †, `Comment` “confirmed by the owner” in `../cldf/paradigms.csv`). Several attested forms for one cell are all shown (*dopri / duperi*). Tenses include `congiuntivo presente` and `congiuntivo imperfetto`. |
| [`verb_forms_reassigned.csv`](verb_forms_reassigned.csv) | extracted line of verb forms | `source,line,from_italian,to_italian,reason`: forms the parser filed under the wrong verb because two dialect verbs share an Italian infinitive (*ciapà* and *töö* both give *prendere*). Moves the forms of that document line to another verb, named by its Italian. |
| [`grammar/`](grammar/) | chapter of the grammar | The text of [`../Grammar/`](../Grammar/README.md): one CLDF Markdown file per chapter, numbered (`00-introduzione.md` is the unnumbered introduction). `# Titolo \| Title`, `## Sezione \| Section`, then paragraphs in pairs, a line `IT: …` followed by a line `EN: …` (printed side by side); a line `[](ExampleTable#cldf:g-dimm)` places an example, a line `[](EntryTable#cldf:canta,bef?tenses=presente)` a table of verb forms from the data (one verb in several tenses, or several verbs in one tense; `_` for a space in a tense name). Ordinary Markdown tables are for dialect tables. In the text, † marks a rule worked out from the forms rather than stated by the course. Full description in the docstring of `../pipeline/grammar.py`. |
| [`grammar_examples.csv`](grammar_examples.csv) | example in the grammar | `ID,Primary_Text,Analyzed_Word,Gloss,Italian,English,Source,Line,Comment`. `Primary_Text` is quoted exactly from line `Line` of document `Source` (as numbered in `../pipeline/cache/lesson_text/`); the build warns when it is not there. `Analyzed_Word` and `Gloss` are space-separated and must have the same number of items (`di-mm` / `tell.IMP.2SG-1SG.DAT`). IDs: letters a-z, digits and `-` only. Becomes a row of `../cldf/examples.csv` with genre `grammar`. |
| [`dialect_lists_italian_supplied.csv`](dialect_lists_italian_supplied.csv) | word | Words a lesson lists in dialect only (colours, numbers, the house, the calendar, the family), with the Italian and English supplied: `source,line,dialect,italian,english,confirmed`. Shown with † on the Italian and listed in `../TO-CHECK.md` until `confirmed` is filled in (who and when, e.g. `owner 2026-10-14`); then the sense gets status `confirmed` and the † goes. |

## `decisions.csv`

```
Decision,Language_ID,Form,Sense,Target_Form,Target_Language_ID,Italian,English,Reason,Date
typo,ticinese,semper,,sempru,rogn,,,"Typo in the owner's spreadsheet; the course writes sempru …",2026-10-14
correct,ticinese,böcc,,,,buco,hole,"Claude inferred: Italian misspelt ""bucco"" in the spreadsheet",2026-10-14
```

| Column | Meaning |
|---|---|
| `Decision` | `typo`, `reject`, `accept`, `variant`, `correct` or `expression` |
| `Language_ID` | the variety of the entry the decision is about, as in `../cldf/languages.csv` (`rogn`, `basso-ceresio`, `ticinese` …) |
| `Form` | the entry's headword, or for an expression its dialect text, as it appears in the data |
| `Sense` | optional: the Italian of one sense of the entry, to limit `reject`, `accept` or `correct` to that sense |
| `Target_Form` | for `typo` and `variant`: the correct or main headword; for `correct`: the corrected dialect |
| `Target_Language_ID` | for `typo` and `variant`: the variety of the target, if it differs |
| `Italian`, `English` | for `correct`: the corrected Italian and English (blank = unchanged) |
| `Reason`, `Date` | recorded in the `Comment` of the rows affected. A reason that starts **"Claude inferred:"** comes from Claude's review of the whole dataset (2026-10-14), not from the owner: check it, and delete or change the row if it is wrong |

| Decision | Effect |
|---|---|
| `typo` | The entry is folded into `Target_Form`; the mistaken form is kept in `variants.csv` as a `typo` so it is recognised but never shown. |
| `reject` | The entry is kept with status `rejected` and the reason, and left off the pages. |
| `accept` | A `pending` (⚠) entry becomes accepted and its pending senses attested. |
| `variant` | Same variety: the form becomes an accepted spelling of the target entry. Another variety: the entry is linked to the target with `Variant_Of`, or, if the target does not exist yet, folded into a new target entry (how `avech pagüra` became the Rögn `vegh pagüra`). |
| `correct` | Replaces the dialect, Italian and/or English of the entry's senses (or the one named in `Sense`), or of an expression, and marks it accepted. |
| `expression` | The entry is an idiom, a saying or a sentence rather than a word (*al bef cumè na pidria*, *E da indua ta set?*): it leaves the dictionary and becomes an expression, with its senses joined as the Italian. Give it a topic in `expression_topics.csv`. |

`reject`, `accept` and `correct` also work on expressions (`examples.csv`): `Form` is then the dialect
text. A decision that matches nothing is reported as a warning when the dataset is built.
