"""Parser checks against the raw downloads (SPEC §3). Skipped when data/raw/ is not populated."""

import numpy as np
import pytest

from lifemodel import parsers
from lifemodel.tables import Cmi00Mortality

try:
    parsers._find_raw("TMN00.xls")
    HAVE_CMI = True
except FileNotFoundError:
    HAVE_CMI = False


@pytest.mark.skipif(not HAVE_CMI, reason="CMI 00 tables not downloaded")
def test_cmi00_tables():
    tidy = parsers.parse_cmi00_table("TMN00")
    row35 = tidy[tidy["age"] == 35].set_index("duration")["qx"]
    # Values read off the source spreadsheet, age 35: durations 0 and 5+
    assert row35[0] == pytest.approx(0.000261) and row35[5] == pytest.approx(0.000531)
    assert tidy["qx"].between(0, 1).all()


@pytest.mark.skipif(not HAVE_CMI, reason="CMI 00 tables not downloaded")
def test_cmi00_lookup_and_ordering(tmp_path, monkeypatch):
    monkeypatch.setattr(parsers, "PROCESSED", tmp_path)
    table = Cmi00Mortality(parsers.build_cmi00())
    ages = np.arange(25, 75)
    # every attained age and duration the book needs (issue 25–55, term 20)
    for dur in range(20):
        assert not np.isnan(table.q(ages, dur, False, False)).any()
    # select effect: q rises with duration at a fixed attained age; smokers > non-smokers; males > females
    q = lambda d, f=False, s=False: table.q(40, d, f, s)
    assert q(0) < q(4) < q(5) == q(12)
    assert q(5, s=True) > q(5) and q(5, f=True) < q(5)


def _have(fn, *args):
    try:
        fn(*args)
        return True
    except FileNotFoundError:
        return False


HAVE_EIOPA = _have(parsers._eiopa_workbook, "2022-12-31")
HAVE_CSO = _have(parsers._find_raw, parsers.CSO_FILES["M"])


@pytest.mark.skipif(not HAVE_EIOPA, reason="EIOPA curves not downloaded")
@pytest.mark.parametrize("date, spot_1y", [
    # 1-year EUR spot without VA, read off each source workbook
    ("2022-12-31", 0.03176),
    ("2025-12-31", 0.02076),
])
def test_eiopa_curve(date, spot_1y):
    curve = parsers.parse_eiopa_curve(date)
    assert curve["maturity"].iloc[0] == 1 and curve["maturity"].iloc[-1] == 150
    assert curve["spot"].iloc[0] == pytest.approx(spot_1y)
    assert curve["spot"].between(-0.02, 0.10).all()


@pytest.mark.skipif(not HAVE_EIOPA, reason="EIOPA curves not downloaded")
def test_all_four_curves_and_loader(tmp_path, monkeypatch):
    from lifemodel.curves import Curve
    monkeypatch.setattr(parsers, "PROCESSED", tmp_path)
    csv = parsers.build_curves()
    for date in parsers.EIOPA_DATES:
        c = Curve.eiopa(date, csv)
        assert len(c.spot) == 150 and 0 < c.df(20) < 1


@pytest.mark.skipif(not HAVE_CSO, reason="CSO tables not downloaded")
def test_cso_ilt17():
    for sex, q40 in (("M", 0.001189), ("F", 0.000611)):
        t = parsers.parse_cso_ilt17(sex)
        assert t["age"].iloc[0] == 0 and t["qx"].between(0, 1).all()
        assert t.loc[t["age"] == 40, "qx"].iloc[0] == pytest.approx(q40, rel=1e-3)
