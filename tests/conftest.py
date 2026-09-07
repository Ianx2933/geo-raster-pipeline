"""Load numbered scripts without running them."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def modules():
    """Import the production entry points."""
    result = {}
    for name, filename in (("warp", "01_reproject.py"), ("contours", "02_contours.py"),
                           ("slope", "05_slope.py")):
        spec = importlib.util.spec_from_file_location(name, ROOT / "src" / filename)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result[name] = module
    return result


@pytest.fixture
def dem():
    """Use a committed synthetic DEM."""
    return ROOT / "tests" / "fixtures" / "tiny_dem.tif"
