# Lexicon of the dialect of Rögn (Arogno)

This folder is the **CLDF dataset** for the dialect material in this repository: every dialect word, its
Italian and English meanings, example sentences, verb conjugations, the sources each one comes from, and
the decisions made about variants and typos. It is plain text (CSV and JSON), so every change can be
reviewed with `git diff`.

**Do not edit these files by hand.** Following the [cldfbench](https://github.com/cldf/cldfbench)
workflow, the dataset is regenerated on every build from the source documents in [`../raw/`](https://github.com/michaelmaguire/languages-dialett-raw)
and the curation in [`../etc/`](../etc/). The documents are read only by the first two steps, whose output
is saved in `../pipeline/data/`, so the dataset can also be rebuilt (with every decision applied) when
`../raw/` is not available. To change something, change it there (a typo or a rejected
entry goes in [`../etc/decisions.csv`](../etc/decisions.csv)) and run `../pipeline/build_all.sh`.

It follows the **[CLDF](https://cldf.clld.org/) (Cross-Linguistic Data Formats) specification, version
1.x, Dictionary module**, at the level the specification calls *extended conformance*: a metadata file
describes every table and column, and the dataset is validated against the specification on every build.

## The CLDF specification

| Document | Link |
|---|---|
| CLDF home page | <https://cldf.clld.org/> |
| The specification | <https://github.com/cldf/cldf/blob/master/README.md> |
| Dictionary module (what a CLDF dictionary must contain) | <https://github.com/cldf/cldf/tree/master/modules/Dictionary> |
| Components used here: entries, senses, examples, contributions, languages | <https://github.com/cldf/cldf/tree/master/components> |
| TextCorpus module (the pattern used for the expressions: contribution and position) | <https://github.com/cldf/cldf/tree/master/modules/TextCorpus> |
| The CLDF ontology (meaning of every `propertyUrl`) | <https://cldf.clld.org/v1.0/terms.html> |
| CSV on the Web (CSVW), which the metadata file uses | <https://www.w3.org/TR/tabular-metadata/> |
| pycldf, the reference software used to validate and query | <https://github.com/cldf/pycldf> |
| cldfbench, the tool used to build this dataset | <https://github.com/cldf/cldfbench> |
| Glottolog, for the language codes | <https://glottolog.org/> |

## What is in it

| File | CLDF role | One row per |
|---|---|---|
| [`Dictionary-metadata.json`](Dictionary-metadata.json) | Metadata (declares `dc:conformsTo` the Dictionary module) | |
| [`entries.csv`](entries.csv) | EntryTable (required) | dialect headword, in one variety |
| [`senses.csv`](senses.csv) | SenseTable (required) | meaning of an entry: `Description` is the Italian, `Description_English` the English |
| [`examples.csv`](examples.csv) | ExampleTable | sentence or saying: `Primary_Text` is the dialect, `Translated_Text` the Italian, `Translated_Text_English` the English; `Contribution_ID` and `Position` say which document and line it comes from, `Genre` what kind of expression it is, `Topic_ID` what it is about |
| [`contributions.csv`](contributions.csv) | ContributionTable | document that has expressions: its title, author and genre |
| [`topics.csv`](topics.csv) | additional table | topic the expressions are grouped by, in Italian and English |
| [`languages.csv`](languages.csv) | LanguageTable | variety (Rögn, Basso Ceresio, Mendrisiotto…), plus Italian and English as meta-languages |
| [`variants.csv`](variants.csv) | additional table | other spelling of an entry, including known typos and OCR errors |
| [`paradigms.csv`](paradigms.csv) | additional table | cell of a verb's conjugation chart |
| [`sources.bib`](sources.bib) | Sources (BibTeX) | lesson, handout, published text, or the owner's own notes |

The specification allows additional columns and tables as long as the metadata describes them. The
additions here are the English columns, `Status`, `Variant_Of`, `Conjugation_Class`, `Auxiliary`, the
expressions' `Genre` and `Topic_ID`, `Example_IDs` on senses (the expressions that use a word in that
sense, found automatically), and the `variants.csv`, `paradigms.csv` and `topics.csv` tables. The
expressions follow the pattern of the TextCorpus module: each one points to its document in
`contributions.csv` and has its line there as `Position`. The lines of the stories, poems and articles
used in the course are not included (the dataset has no permission to publish them); only the sayings and
phrases taken from them are. Verb paradigms have no CLDF component of their own.

## How the data is recorded

- **Varieties.** Each Ticinese variety is a row in `languages.csv`, all with Glottocode `lomb1257`
  (Lombard) and ISO 639-3 `lmo`; Glottolog has no finer codes for them. An entry belongs to exactly one
  variety. A regional form of a Rögn word is its own entry, linked by `Variant_Of`.
- **Sources.** Every row cites where it was found, in the `Source` column, as `key[l.N]`: the BibTeX key
  of the document and the line in its extracted text (kept, with the documents, in the private source repository).
- **Decisions.** Every table has a `Status` column whose allowed values are fixed in the metadata, so the
  validator rejects anything else (`pending` rows are the ones marked ⚠ on the pages):

  | Table | Status values |
  |---|---|
  | entries | `accepted`, `pending` (needs review), `inferred` (infinitive worked out, not stated), `rejected` |
  | senses | `attested`, `supplied` (Italian added because the lesson gives only the dialect), `confirmed` (supplied, then checked by the owner), `pending`, `rejected` |
  | examples | `accepted`, `pending`, `rejected` |
  | variants | `accepted`, `pending`, `typo`, `rejected` |
  | paradigms | `attested` (found in a document), `inferred` (predicted from the patterns), `rejected` |

  The reason goes in `Comment`. Nothing is deleted: a typo or a wrong entry is marked `rejected` or
  `typo`, keeps its sources, and stops appearing in the pages. For example, the owner's spreadsheet has
  `semper` for *sempre*; [`../etc/decisions.csv`](../etc/decisions.csv) records it as a typo, so the
  dataset has the entry `sempru` and the variant `sempru-semper` with kind and status `typo`.
- **IDs** use only letters, digits and hyphens, as CLDF requires, and are made from the headword
  (`sempru`), with the variety appended outside Rögn (`semper-ticinese`) and a number for homographs
  (the verb `vert` and the colour `vert` are separate entries). As the dataset is regenerated, an ID stays
  the same as long as the data it comes from does.

## Working with it

```sh
cd pipeline
.venv/bin/cldf validate ../cldf/Dictionary-metadata.json                       # check conformance
.venv/bin/cldf createdb ../cldf/Dictionary-metadata.json cache/cldf.sqlite  # query it with SQL
```

`build_all.sh` builds the dataset with cldfbench, validates it, and stops if it is not valid, before any
page is written from it. The SQLite file is a disposable copy and not kept in git. cldfbench also records
provenance in the metadata and lists the Python packages used in `requirements.txt`.

---

The section below is generated from the metadata by `cldf markdown` on every build.
