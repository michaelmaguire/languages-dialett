"""Where everything lives. The layout follows cldfbench (https://github.com/cldf/cldfbench):

  raw/    source data, never changed: the course documents, the owner's spreadsheet and notes
  etc/    curation: lesson classification, translations, verb details, corrections, decisions
  cldf/   the CLDF dataset, regenerated from raw/ + etc/ by `cldfbench makecldf` on every build
"""
from pathlib import Path

PIPELINE = Path(__file__).resolve().parent
ROOT = PIPELINE.parent                       # the repository root (the cldfbench dataset)
RAW = ROOT / "raw"
ETC = ROOT / "etc"
CLDF = ROOT / "cldf"
CACHE = PIPELINE / "cache"
DATA = PIPELINE / "data"
# The text of the documents and everything that quotes it at length stay with the documents in the
# private raw/ submodule (owner, 2026-10-28: no permission to publish the material itself):
# lesson_text/ and extract_index.json (step 1), the full extracted_pairs.csv and unparsed_lines.csv (step 2).
# pipeline/data/ keeps a public extracted_pairs.csv without the lines of stories, poems and articles.
PRIVATE = RAW / "extracted"
TEXT = PRIVATE / "lesson_text"
TEMPLATES = PIPELINE / "templates"
# raw/ is a git submodule of this GitHub repo (private for now): the pages link to the documents there,
# since GitHub does not follow relative links into a submodule
RAW_URL = "https://github.com/michaelmaguire/languages-dialett-raw"


def extraction(name):
    """Step 2's output: the full private copy in raw/extracted/ when the submodule is there, else the public
    one in pipeline/data/ (which gives the same dataset, since what it leaves out is never published)."""
    private = PRIVATE / name
    return private if private.exists() else DATA / name


def raw_available():
    """True when the source documents are present. raw/ is a git submodule
    (michaelmaguire/languages-dialett-raw) that may be private: without it, steps 1-2 cannot run and
    the build starts from what they last saved in pipeline/data/ (see pipeline/README.md)."""
    return RAW.is_dir() and any(p.suffix.lower() in (".docx", ".pdf") for p in RAW.iterdir())
