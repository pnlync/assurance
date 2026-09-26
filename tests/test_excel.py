"""SPEC §13.4: the Excel single-policy model, evaluated formula by formula, agrees with Python within €0.01."""

import sys
from pathlib import Path

import pytest

from lifemodel.parsers import PROCESSED

pytestmark = pytest.mark.skipif(not (PROCESSED / "mortality_cmi00.csv").exists(), reason="CMI 00 not parsed")


@pytest.fixture(scope="module")
def workbook(tmp_path_factory):
    from pycel import ExcelCompiler
    from lifemodel.excel_build import build
    path = tmp_path_factory.mktemp("xl") / "check.xlsx"
    info = build(path)
    sys.path.insert(0, str(Path(__file__).parent))  # for the IRR plugin
    return ExcelCompiler(filename=str(path), plugins=["excel_functions"]), info


@pytest.mark.parametrize("sheet", ["Check_F1", "Check_Reference"])
def test_excel_reconciles(workbook, sheet):
    xl, info = workbook
    cell = info["max_diff_cells"][sheet]
    assert xl.evaluate(f"{sheet}!{cell}") < 0.01
    row = int(cell[1:]) + 1
    assert xl.evaluate(f"{sheet}!B{row}") == "YES"


def test_excel_f1_matches_golden(workbook):
    xl, _ = workbook
    assert xl.evaluate("F1!C2") == pytest.approx(579.2828, abs=1e-3)
    assert xl.evaluate("F1!C3") == pytest.approx(408.1656, abs=1e-3)
    assert xl.evaluate("F1!F4") == pytest.approx(-689.2270, abs=1e-3)
    assert xl.evaluate("F1!I2") == pytest.approx(461.1183, abs=1e-3)
