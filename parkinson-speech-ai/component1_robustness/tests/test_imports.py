"""Every component1_robustness module must import with absolute imports."""

import importlib
import pkgutil
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).resolve().parents[1]
MODULES = sorted(
    f"component1_robustness.{m.name}"
    for m in pkgutil.iter_modules([str(PACKAGE_DIR)])
    if not m.ispkg
)


def test_module_list_not_empty():
    assert "component1_robustness.pipeline" in MODULES


@pytest.mark.parametrize("module_name", MODULES)
def test_module_imports(module_name: str):
    importlib.import_module(module_name)


@pytest.mark.parametrize("module_name", MODULES)
def test_no_relative_or_src_imports(module_name: str):
    source = (PACKAGE_DIR / f"{module_name.split('.')[-1]}.py").read_text(encoding="utf-8")
    assert "from .." not in source
    assert "from ." not in source
    assert "python -m src." not in source
