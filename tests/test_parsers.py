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
