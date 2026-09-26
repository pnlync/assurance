"""Sanity checks on the real-basis rate table (SPEC §7.2). Skipped until the CMI 00 data are parsed."""

import pytest

from lifemodel.parsers import PROCESSED

pytestmark = pytest.mark.skipif(not (PROCESSED / "mortality_cmi00.csv").exists(), reason="CMI 00 not parsed")


@pytest.fixture(scope="module")
def real_basis():
    from lifemodel.basis import load_basis
    return load_basis("basis_2022")


def test_rate_table_shape(real_basis):
    from lifemodel.pricing_analysis import rate_table
    t = rate_table(real_basis)
    assert len(t) == 2 * 2 * 31 and (t["rate_per_1000"] > 0).all()
    for (product, smoker), cell in t.groupby(["product", "smoker"]):
        assert cell.sort_values("issue_age")["rate_per_1000"].is_monotonic_increasing  # older costs more
    wide = t.pivot_table(index=["product", "issue_age"], columns="smoker", values="rate_per_1000")
    assert (wide[True] > wide[False]).all()  # smokers cost more
    lta = t[t["product"] == "LTA"].set_index(["smoker", "issue_age"])["rate_per_1000"]
    mp = t[t["product"] == "MP"].set_index(["smoker", "issue_age"])["rate_per_1000"]
    assert (mp < lta).all()  # decreasing cover is cheaper per 1,000 of initial SA


def test_priced_book(real_basis):
    from lifemodel.portfolio import generate_portfolio
    from lifemodel.pricing_analysis import apply_rates, rate_table
    book = apply_rates(generate_portfolio(n=3_000), rate_table(real_basis), real_basis)
    assert book["premium"].notna().all() and (book["premium"] > real_basis.policy_fee).all()


def test_market_reasonableness_structure(real_basis):
    """Model premiums lie within 0.5–2.0× the quote mid (SPEC §7.1); implied X is on the grid."""
    import pandas as pd
    from lifemodel.parsers import RAW
    from lifemodel.pricing_analysis import market_reasonableness
    path = RAW / "market_quotes.csv"
    if not path.exists():
        pytest.skip("market quotes not collected")
    table, implied_x = market_reasonableness(pd.read_csv(path).head(2), real_basis, x_grid=[0.45, 0.712])
    assert not table["flag_outside_0.5_2.0"].any()
    assert implied_x in (0.45, 0.712)
