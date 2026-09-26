"""Unit tests and identities for the engine and pricing (SPEC §13.1, §6.5)."""

import numpy as np
import pytest
from dataclasses import replace

from lifemodel.basis import level_multiplier
from lifemodel.curves import Curve
from lifemodel.portfolio import generate_portfolio, sum_assured_schedule
from lifemodel.pricing import profit_test, profit_test_exam_mode
from lifemodel.projection import cash_flow_items, forward_pv, project, rates, value


def test_rates_in_unit_interval_and_capped(fixture_basis):
    book = generate_portfolio(n=2_000).assign(premium=500.0)
    extreme = replace(fixture_basis, mortality_multiplier=5_000.0, lapse_multiplier=30.0)
    for basis in (fixture_basis, extreme):
        q, w = rates(book, basis)
        assert ((q >= 0) & (q <= 1)).all() and ((w >= 0) & (w <= 1)).all()
    q, w = rates(book, extreme)
    assert q.max() == 1.0 and w.max() == 1.0
    assert (w[:, -1] == 0).all()


def test_in_force_non_increasing(f1, fixture_basis):
    l = project(f1, fixture_basis)["in_force"][0]
    assert (np.diff(l) <= 0).all()


def test_value_at_maturity_is_zero(f1, fixture_basis, flat3):
    assert value(f1, fixture_basis, flat3)[0, -1] == 0.0


@pytest.mark.parametrize("include_overhead", [True, False])
def test_forward_pv_equals_backward_v0(f1, f2, fixture_basis, include_overhead):
    curve = Curve(np.linspace(0.01, 0.035, 60))  # non-flat, to exercise the curve logic
    for policy in (f1, f2):
        v0 = value(policy, fixture_basis, curve, include_overhead=include_overhead)[0, 0]
        fwd = forward_pv(policy, fixture_basis, curve, include_overhead)[0]
        assert fwd == pytest.approx(v0, rel=1e-10)


def test_start_duration_matches_full_recursion_on_flat_curve(f1, fixture_basis, flat3):
    full = value(f1, fixture_basis, flat3)[0]
    from_5 = value(f1, fixture_basis, flat3, start_duration=5)[0]
    assert np.isnan(from_5[:5]).all()
    np.testing.assert_allclose(from_5[5:], full[5:], rtol=1e-12)


def test_mp_schedule_properties(f2):
    s = sum_assured_schedule(f2)[0]
    assert s[0] == f2["sa"].iloc[0] and s[-1] > 0 and (np.diff(s) < 0).all()


def test_zeroised_reserves(f1, f2, fixture_basis):
    for policy in (f1, f2):
        res = profit_test(policy, fixture_basis).reserves
        assert (res >= 0).all() and res[0] == 0 and res[-1] == 0


def test_reserves_defer_profit(f1, fixture_basis):
    """Holding reserves earning 3% < RDR 8% lowers NPV (SPEC §7.3)."""
    pt = profit_test(f1, fixture_basis)
    assert pt.npv < pt.npv_no_reserves


def test_exam_mode_reproduces_profit_test(f1, fixture_basis):
    pt = profit_test(f1, fixture_basis)
    q, w = rates(f1, fixture_basis)
    cf = cash_flow_items(f1, fixture_basis)
    pr, sig, npv = profit_test_exam_mode(
        cf["premium"][0], cf["commission"][0], cf["expenses"][0], q[0], w[0],
        cf["sum_assured"][0], cf["claim_expense"][0], pt.reserves,
        fixture_basis.earned_rate, fixture_basis.risk_discount_rate,
    )
    np.testing.assert_allclose(pr, pt.profit_vector, rtol=1e-12)
    assert npv == pytest.approx(pt.npv, rel=1e-12)


def test_rolled_forward_curve():
    c = Curve(np.linspace(0.01, 0.035, 60))
    f = c.rolled_forward()
    m = np.arange(1, 30)
    np.testing.assert_allclose(f.df(m), c.df(m + 1) / c.df(1), rtol=1e-12)


def test_level_multiplier():
    assert level_multiplier(0.015, 2000.5, 2023) == pytest.approx(0.985**22.5)


def test_portfolio_generator():
    book = generate_portfolio()
    assert len(book) == 50_000 and book["policy_id"].iloc[-1] == "TL050000"
    assert book["issue_age"].between(25, 55).all()
    lta, mp = book[book["product"] == "LTA"], book[book["product"] == "MP"]
    assert lta["sa"].between(50_000, 1_000_000).all() and mp["sa"].between(100_000, 800_000).all()
    assert (book["sa"] % 1_000 == 0).all()
    assert mp["loan_rate"].eq(0.04).all() and lta["loan_rate"].isna().all()
    assert abs(book["smoker"].mean() - 0.20) < 0.01
    assert abs((book["sex"] == "M").mean() - 0.55) < 0.01
    assert abs((book["channel"] == "broker").mean() - 0.70) < 0.01
    assert generate_portfolio().equals(book)  # reproducible


def test_full_book_valuation_speed(fixture_basis, flat3):
    import time
    book = generate_portfolio().assign(premium=500.0)
    start = time.perf_counter()
    value(book, fixture_basis, flat3)
    assert time.perf_counter() - start < 5.0


def test_unisex_rate_between_female_and_male(fixture_basis):
    """Unisex rate lies between the single-sex rates and the pooled margin hits the target (SPEC §7.2)."""
    from lifemodel.portfolio import make_policy
    from lifemodel.pricing import pooled_margin, premium_from_rate, solve_rate, solve_unisex_rate
    b = fixture_basis
    male, female = solve_rate("LTA", 40, "M", False, b), solve_rate("LTA", 40, "F", False, b)
    unisex = solve_unisex_rate("LTA", 40, False, b)
    assert female < unisex < male
    p = premium_from_rate(unisex, 250_000, b)
    m = profit_test(make_policy("LTA", 40, "M", False, 250_000, p), b)
    f = profit_test(make_policy("LTA", 40, "F", False, 250_000, p), b)
    pooled = (b.male_share * m.npv + (1 - b.male_share) * f.npv) / (
        b.male_share * m.epv_premiums + (1 - b.male_share) * f.epv_premiums)
    assert pooled == pytest.approx(b.target_margin, abs=1e-9)
    assert m.margin < b.target_margin < f.margin  # men are cross-subsidised by women
    # more men than priced for → lower margin
    assert pooled_margin("LTA", 40, False, p, b, male_share=0.70) < b.target_margin < pooled_margin(
        "LTA", 40, False, p, b, male_share=0.50)


def test_exam_mode_appendix_b_worked_example():
    """SPEC Appendix B toy profit test, replacing the CM1 past-paper check (SPEC §7.5, v1.5)."""
    q = [0.0010, 0.0011, 0.0012]
    w = [0.10, 0.10, 0.0]
    pr, sig, npv = profit_test_exam_mode(
        premium=180.0, commission=[0, 0, 0], expenses=[100.0, 15.0, 15.0], q=q, w=w,
        sum_assured=[100_000.0] * 3, claim_expense=[0, 0, 0], reserves=[0, 0, 0, 0],
        earned_rate=0.03, rdr=0.08,
    )
    np.testing.assert_allclose(sig, [-17.60, 53.90, 40.37], atol=0.005)
    assert npv == pytest.approx(61.97, abs=0.005)
    in_force = np.concatenate([[1.0], np.cumprod((1 - np.array(q)) * (1 - np.array(w)))])[:3]
    epv_premiums = 180.0 * (in_force @ 1.08 ** -np.arange(3.0))
    assert npv / epv_premiums == pytest.approx(0.136, abs=0.0005)
