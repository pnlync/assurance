"""Analysis-of-change identities (SPEC §11, §13.2) on a small synthetic book with the fixture basis."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from lifemodel.aoc import ifrs17_year, solvency2_year
from lifemodel.curves import Curve
from lifemodel.ifrs17 import ModelPoints, csm_expected_runoff, initial_recognition, scenario_multipliers
from lifemodel.portfolio import generate_portfolio
from lifemodel.simulate import simulate

TRUTH = {"mortality_multiplier": 1.3, "lapse_multiplier": 1.2,
         "lapse_channel_factor": {"broker": 1.1, "direct": 0.8}, "maintenance_expense_multiplier": 1.06}


@pytest.fixture(scope="module")
def setup(fixture_basis):
    book = generate_portfolio(n=4_000, seed=11)
    rate = 0.8 + 0.06 * (book["issue_age"] - 25) + 0.6 * book["smoker"]  # one rate per combination
    book = book.assign(premium=rate * book["sa"] / 1000 + fixture_basis.policy_fee)
    experience = simulate(book, fixture_basis, TRUTH, seed=5)
    curves = {2022: Curve(np.linspace(0.030, 0.028, 150)), 2023: Curve(np.linspace(0.033, 0.025, 150)),
              2024: Curve(np.linspace(0.022, 0.024, 150)), 2025: Curve(np.linspace(0.020, 0.033, 150))}
    b1 = replace(fixture_basis, lapse_multiplier=1.2, maintenance=63.6, mortality_multiplier=1.05)
    return book, experience, curves, b1


def test_solvency2_walk_reconciles(setup, fixture_basis):
    book, experience, curves, b1 = setup
    for year in (2023, 2024, 2025):
        r = solvency2_year(book, experience, year, fixture_basis, b1 if year == 2025 else fixture_basis,
                           curves[year - 1], curves[year])
        scale = abs(r["opening"])
        assert abs(r["identity_error"]) < 1e-8 * scale and abs(r["walk_error"]) < 1e-8 * scale
        if year < 2025:
            assert r["assumption_change"] == pytest.approx(0.0, abs=1e-6)


def test_ifrs17_walks_reconcile(setup, fixture_basis):
    book, experience, curves, b1 = setup
    locked = curves[2022]
    init = initial_recognition(book, fixture_basis, locked, scenario_multipliers(2_000))
    mult = scenario_multipliers(2_000)
    mp0, mp1 = ModelPoints(book, fixture_basis), ModelPoints(book, b1)
    opening = init.groups.set_index("group")[["csm", "loss_component"]]
    for year in (2023, 2024, 2025):
        t = ifrs17_year(book, experience, year, init.policy_group, opening, fixture_basis,
                        b1 if year == 2025 else fixture_basis, curves[year - 1], curves[year], locked,
                        mp0, mp1 if year == 2025 else mp0, mult)
        scale = t["be_opening"].abs().max()
        for col in ("be_identity_error", "be_walk_error", "ra_walk_error", "csm_walk_error"):
            assert t[col].abs().max() < 1e-8 * scale, col
        assert (t["csm_closing"] >= -1e-9).all() and (t["lc_closing"] >= -1e-9).all()
        # the RA at the start of 2023 equals the RA at initial recognition (same curve, same scenarios)
        if year == 2023:
            ra_init = init.groups.set_index("group")["ra"]
            np.testing.assert_allclose(t.set_index("group")["ra_opening"], ra_init[t["group"]], rtol=1e-10)
        opening = t.set_index("group")[["csm_closing", "lc_closing"]].rename(
            columns={"csm_closing": "csm", "lc_closing": "loss_component"})


def test_csm_releases_sum_to_csm0_plus_accretion():
    """SPEC §13.2: with no experience or assumption change, Σ releases = CSM_0 + Σ accretion."""
    curve = Curve(np.linspace(0.02, 0.035, 60))
    cu = np.linspace(1_000_000, 100_000, 20)
    run = csm_expected_runoff(5_000.0, cu, curve)
    assert run["release"].sum() == pytest.approx(5_000.0 + run["accretion"].sum(), rel=1e-12)
    assert run["closing"].iloc[-1] == pytest.approx(0.0, abs=1e-9)
