"""Apply renames of source documents in raw/ to the rest of the repository.

The pipeline refers to documents by file name: etc/lesson_sources.csv, citations in the other
curation files (`frasi fatte.docx[l.139]`), the extraction cache, the AUTHORS table in lexicon.py and
the docs. When raw/fetch_mail_attachments.py renames files in raw/ (adding the e-mail's date and
time: `2024-05-29-1014-frasi fatte.docx`), it logs each rename in raw/renamed_files.csv
(old,new,date,email). This tool reads that log and replaces every old name with the new one in

    etc/ (all .csv and .md files), pipeline/*.py, pipeline/README.md, pipeline/templates/,
    CLAUDE.md, ATTRIBUTIONS.md
    raw/extracted/lesson_text/<name>.txt and raw/extracted/extract_index.json (private), so that step 1
    does not extract (or OCR) the renamed files again.

Generated files (cldf/, the pages, pipeline/data/) are not touched: rebuild with build_all.sh.

    .venv/bin/python tool_rename_sources.py              # apply ../raw/renamed_files.csv
    .venv/bin/python tool_rename_sources.py --dry-run    # only count what would change
    .venv/bin/python tool_rename_sources.py LOG.csv      # another log

Running it again is harmless: an old name that no longer appears is simply not found.
A name is replaced only where it is not part of a longer name: `l Condizionale Presente.docx`
is not touched inside `Il Condizionale Presente.docx`, nor `frasi fatte.docx` inside
`2024-05-29-1014-frasi fatte.docx`.
"""

import argparse
import csv
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "raw" / "renamed_files.csv"
CACHE = ROOT / "raw" / "extracted"           # step 1's text and index, kept with the documents


def text_files():
    """The hand-written files that may mention a document by name."""
    files = list((ROOT / "etc").rglob("*.csv")) + list((ROOT / "etc").rglob("*.md"))
    files += list((ROOT / "pipeline").glob("*.py")) + list((ROOT / "pipeline" / "templates").glob("*"))
    files += [ROOT / "pipeline" / "README.md", ROOT / "CLAUDE.md", ROOT / "ATTRIBUTIONS.md"]
    this = Path(__file__).resolve()
    return [f for f in files if f.is_file() and f.resolve() != this]


def name_pattern(old):
    """Matches `old` only as a whole name: not preceded by a letter, digit or '-' (which would make
    it the end of a longer name), nor followed by a letter or digit."""
    return re.compile(r"(?<![\w-])" + re.escape(old) + r"(?!\w)")


def git_mv(old, new):
    """Rename a file, with `git mv` if git tracks it (keeps its history), else a plain rename."""
    # run git in the file's own folder: the cached texts are inside the raw/ submodule, its own repository
    if subprocess.run(["git", "-C", str(old.parent), "mv", "--", str(old), str(new)],
                      capture_output=True, check=False).returncode != 0:
        old.rename(new)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("log", nargs="?", type=Path, default=LOG, help=f"rename log (default {LOG})")
    ap.add_argument("-n", "--dry-run", action="store_true", help="count only, change nothing")
    args = ap.parse_args()
    if not args.log.exists():
        sys.exit(f"no rename log at {args.log}")

    # NFC everywhere, so that "ü" written as one character or as u + accent compare equal.
    nfc = lambda s: unicodedata.normalize("NFC", s)
    renames = [(nfc(r["old"]), nfc(r["new"])) for r in csv.DictReader(args.log.open(encoding="utf-8"))]
    raw = ROOT / "raw"
    if any(raw.iterdir()):  # warn about a log that does not match raw/ (when it is checked out)
        renamed_again = {old for old, _ in renames}  # a file renamed twice: only its last name exists
        for _, new in renames:
            if new not in renamed_again and not (raw / new).exists():
                print(f"warning: raw/{new} does not exist (renamed again since?)")

    # --- Names in the hand-written files ---
    total = 0
    for path in text_files():
        # newline="" keeps line endings as they are (lesson_sources.csv has CRLF, from csv.writer).
        with open(path, encoding="utf-8", newline="") as f:
            text = nfc(f.read())
        changed, n_file = text, 0
        for old, new in renames:
            changed, n = name_pattern(old).subn(lambda m, new=new: new, changed)
            n_file += n
        if n_file:
            total += n_file
            print(f"  {n_file:4d}  {path.relative_to(ROOT)}")
            if not args.dry_run:
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(changed)
    print(f"{total} mentions {'to replace' if args.dry_run else 'replaced'}")

    # --- The extraction cache: text files and the index step 1 checks before extracting ---
    index_path = CACHE / "extract_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    index = {nfc(k): v for k, v in index.items()}
    moved = 0
    for old, new in renames:
        src, dst = CACHE / "lesson_text" / f"{old}.txt", CACHE / "lesson_text" / f"{new}.txt"
        if src.exists() and not dst.exists():
            moved += 1
            if not args.dry_run:
                git_mv(src, dst)
        if old in index and new not in index:
            index[new] = index.pop(old)
    if not args.dry_run:
        index_path.write_text(json.dumps(dict(sorted(index.items())), ensure_ascii=False, indent=1),
                              encoding="utf-8")
    print(f"{moved} cached texts {'to rename' if args.dry_run else 'renamed'} in raw/extracted/lesson_text")
    if not args.dry_run:
        print("Now rebuild: pipeline/build_all.sh")


if __name__ == "__main__":
    main()
