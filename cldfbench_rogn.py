"""cldfbench dataset definition: how cldf/ is made from raw/ and etc/.

Run by pipeline/build_all.sh as `cldfbench makecldf cldfbench_rogn.py` (after the text extraction steps).
See https://github.com/cldf/cldfbench for the conventions this follows.
"""
import pathlib
import sys

from cldfbench import CLDFSpec, Dataset as BaseDataset

sys.path.insert(0, str(pathlib.Path(__file__).parent / "pipeline"))
import lexicon  # noqa: E402  (the conversion code lives with the rest of the pipeline)


class Dataset(BaseDataset):
    dir = pathlib.Path(__file__).parent
    id = "rogn"

    def cldf_specs(self):
        return CLDFSpec(dir=self.cldf_dir, module="Dictionary", metadata_fname="Dictionary-metadata.json")

    def cmd_download(self, args):
        """Nothing to download: raw/ holds the course documents, added by hand."""

    def cmd_makecldf(self, args):
        """Convert raw/ (via the extracted text in pipeline/cache and pipeline/data) plus etc/ to CLDF."""
        lexicon.make(args.writer)
