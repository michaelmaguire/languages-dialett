"""The Python code passes ruff (settings in ruff.toml; owner, 2026-10-29)."""
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import ROOT


def test_compiles():
    """Every Python file compiles (ruff 0.17 passed a file with a syntax error, 2026-10-29)."""
    import py_compile
    bad = []
    for f in sorted([*ROOT.glob("*.py"), *(ROOT / "pipeline").glob("*.py"), *(ROOT / "tests").glob("*.py")]):
        try:
            py_compile.compile(str(f), doraise=True)
        except py_compile.PyCompileError as e:
            bad.append(str(e))
    if bad:
        pytest.fail("\n".join(bad), pytrace=False)


def test_ruff():
    ruff = Path(sys.executable).parent / "ruff"
    if not ruff.exists():
        pytest.skip("ruff is not installed in the venv (pipeline/requirements.txt)")
    r = subprocess.run([str(ruff), "check", "--output-format", "concise", "."], cwd=ROOT,
                       capture_output=True, text=True, check=False)
    if r.returncode:
        pytest.fail("ruff found problems:\n" + r.stdout, pytrace=False)
