#!/usr/bin/env python3
"""Step 3: build the CLDF dataset in ../cldf from ../raw (via steps 1-2) and ../etc.

This runs the dataset's makecldf (../cldfbench_rogn.py) through cldfbench's Python interface. It is the
same as `cldfbench makecldf cldfbench_rogn.py`, except that the command line also insists on a local copy
of the Glottolog catalogue, which this dataset does not use: its language codes are set in lexicon.py.
"""
import argparse, logging, sys

from paths import ROOT

sys.path.insert(0, str(ROOT))
from cldfbench_rogn import Dataset  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
Dataset()._cmd_makecldf(argparse.Namespace(log=logging.getLogger("cldfbench")))
