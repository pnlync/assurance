"""Golden values from SPEC §13.3. NEVER edit these numbers to make a test pass (SPEC §0 rule 2)."""

import numpy as np
import pytest

from lifemodel.portfolio import sum_assured_schedule
from lifemodel.pricing import profit_test
from lifemodel.projection import project, value

MONEY = 1e-3  # absolute tolerance on money amounts
RATE = 1e-6   # absolute tolerance on rates, probabilities and ratios

F1_ROWS = [  # t, q_t, w_t, ℓ_t, V_t (best estimate incl. overhead), reserve _tV, profit vector Pr_t
    (0, 0.00073466, 0.06, 1.00000000, -689.2270, 0.0000, -518.5997),
    (1, 0.00079344, 0.09, 0.93930942, -1307.8794, 0.0000, 318.9174),
    (2, 0.00085691, 0.08, 0.85409336, -1130.7856, 0.0000, 301.0474),
    (3, 0.00092547, 0.07, 0.78509256, -939.5680, 0.0000, 194.1685),
    (4, 0.00099950, 0.06, 0.72946037, -738.2090, 94.3750, 47.7670),
    (5, 0.00107946, 0.05, 0.68500739, -531.5046, 330.8408, 58.5227),
    (10, 0.00158608, 0.05, 0.52669747, 400.0117, 1195.9478, 112.1288),
    (15, 0.00233048, 0.05, 0.40377030, 812.5284, 1261.6641, 123.4474),
    (19, 0.00317059, 0.00, 0.32543335, 311.4070, 392.6221, 83.6515),
]


# ---------- F1 ----------

def test_f1_rate_and_premium(f1_rate, f1):
    assert f1_rate == pytest.approx(2.077131, abs=RATE)
    assert f1["premium"].iloc[0] == pytest.approx(579.2828, abs=MONEY)


def test_f1_profit_measures(f1, fixture_basis):
    pt = profit_test(f1, fixture_basis)
    assert pt.margin == pytest.approx(0.10, abs=RATE)
    assert pt.npv == pytest.approx(408.1656, abs=MONEY)
    assert pt.irr == pytest.approx(0.302477, abs=RATE)
    assert pt.discounted_payback == 4


@pytest.mark.parametrize("t, q, w, l, v, res, pr", F1_ROWS)
def test_f1_table(f1, fixture_basis, flat3, t, q, w, l, v, res, pr):
    p = project(f1, fixture_basis)
    pt = profit_test(f1, fixture_basis)
    assert p["q"][0, t] == pytest.approx(q, abs=RATE)
    assert p["w"][0, t] == pytest.approx(w, abs=RATE)
    assert p["in_force"][0, t] == pytest.approx(l, abs=RATE)
    assert value(f1, fixture_basis, flat3)[0, t] == pytest.approx(v, abs=MONEY)
    assert pt.reserves[t] == pytest.approx(res, abs=MONEY)
    assert pt.profit_vector[t] == pytest.approx(pr, abs=MONEY)


def test_f1_in_force_at_maturity(f1, fixture_basis):
    assert project(f1, fixture_basis)["in_force"][0, 20] == pytest.approx(0.32440200, abs=RATE)


def test_f1_ifrs17_value_without_overhead(f1, fixture_basis, flat3):
    assert value(f1, fixture_basis, flat3, include_overhead=False)[0, 0] == pytest.approx(-856.8743, abs=MONEY)


# ---------- F2 ----------

def test_f2_sum_assured_schedule(f2):
    s = sum_assured_schedule(f2)[0]
    assert s[0] == pytest.approx(250_000.0000, abs=MONEY)
    assert s[1] == pytest.approx(241_604.5624, abs=MONEY)
    assert s[10] == pytest.approx(149_203.4770, abs=MONEY)
    assert s[19] == pytest.approx(17_687.9208, abs=MONEY)


def test_f2_rate_premium_and_value(f2_rate, f2, fixture_basis, flat3):
    assert f2_rate == pytest.approx(1.467883, abs=RATE)
    assert f2["premium"].iloc[0] == pytest.approx(426.9708, abs=MONEY)
    assert profit_test(f2, fixture_basis).margin == pytest.approx(0.10, abs=RATE)
    assert value(f2, fixture_basis, flat3)[0, 0] == pytest.approx(-627.6326, abs=MONEY)


# ---------- Solvency II (F1, F2, F3) ----------

from lifemodel.solvency2 import bel, risk_margin, scr_path, stress_losses  # noqa: E402


@pytest.mark.parametrize("fixture_name, expected", [
    ("f1", dict(mortality=461.1183, lapse_up=105.0972, lapse_down=0.0, mass=275.6908, expense=180.3446, cat=366.2321)),
    ("f2", dict(mortality=280.8733, lapse_up=240.1787, lapse_down=0.0, mass=251.0531, expense=180.3446, cat=366.1397)),
])
def test_sii_losses_at_issue(request, fixture_basis, flat3, fixture_name, expected):
    losses = stress_losses(request.getfixturevalue(fixture_name), fixture_basis, flat3)
    for risk, amount in expected.items():
        assert losses[risk][0, 0] == pytest.approx(amount, abs=MONEY), risk


@pytest.fixture(scope="module")
def f3(f1, f2):
    import pandas as pd
    return pd.concat([f1, f2], ignore_index=True)


def test_f3_scr(f3, fixture_basis, flat3):
    path = scr_path(f3, fixture_basis, flat3)
    row0 = path.iloc[0]
    for risk, amount in dict(mortality=741.9916, lapse=526.7438, expense=360.6892, cat=732.3718,
                             lapse_up=345.2758, lapse_down=0.0, mass=526.7438).items():
        assert row0[risk] == pytest.approx(amount, abs=MONEY), risk
    assert path["scr_life"][0] == pytest.approx(1554.0120, abs=MONEY)
    assert path["scr_life"][1] == pytest.approx(1742.0748, abs=MONEY)
    assert path["scr_life"][10] == pytest.approx(738.8610, abs=MONEY)


def test_f3_bel_and_risk_margin(f3, fixture_basis, flat3):
    assert bel(f3, fixture_basis, flat3) == pytest.approx(-1316.8596, abs=MONEY)
    rm = risk_margin(scr_path(f3, fixture_basis, flat3)["scr_life"].to_numpy(), flat3)
    assert rm.current == pytest.approx(822.3561, abs=MONEY)
    assert rm.rule_2027 == pytest.approx(526.5710, abs=MONEY)
    assert rm.ratio == pytest.approx(0.64031996, abs=RATE)
    assert rm.identity_ratio == pytest.approx(rm.ratio, rel=1e-10)
    assert 0.3958 <= rm.ratio <= 0.7917


# ---------- IFRS 17 (F3) ----------

def test_f3_ifrs17_fixed_ra(f3, fixture_basis, flat3):
    from lifemodel.ifrs17 import coverage_units, csm_expected_runoff
    from lifemodel.projection import value
    import pandas as pd
    ra = 0.25 * scr_path(f3, fixture_basis, flat3)["scr_life"][0]
    assert ra == pytest.approx(388.5030, abs=MONEY)
    be = value(f3, fixture_basis, flat3, include_overhead=False)[:, 0].sum()
    fcf = be + ra
    assert fcf == pytest.approx(-1263.6512, abs=MONEY)
    csm0 = max(0.0, -fcf)
    assert csm0 == pytest.approx(1263.6512, abs=MONEY)
    cu = coverage_units(f3, fixture_basis, [1, 1], pd.Series(["g", "g"]), 0)["g"].to_numpy()
    assert cu[0] == pytest.approx(500_000.0, abs=MONEY)
    assert cu[1] == pytest.approx(461_768.7943, abs=MONEY)
    assert cu[19] == pytest.approx(87_114.5756, abs=MONEY)
    run = csm_expected_runoff(csm0, cu, flat3)
    np.testing.assert_allclose(run["release"][:3], [133.6955, 127.1770, 116.9930], atol=MONEY)
    assert run["closing"].iloc[-1] == pytest.approx(0.0, abs=MONEY)
    assert run["release"].sum() == pytest.approx(1607.9465, abs=MONEY)


def test_f3_monte_carlo_ra(f3, fixture_basis, flat3):
    """10,000 scenarios, seed 17: RA_75 within ±5% of the 200,000-scenario reference 233.5 (SPEC §13.3)."""
    import pandas as pd
    from lifemodel.ifrs17 import ModelPoints, risk_adjustment, scenario_multipliers
    mp = ModelPoints(f3, fixture_basis)
    pv, _ = mp.group_pv(f3, [1, 1], pd.Series(["g", "g"]), flat3, 0, scenario_multipliers())
    assert risk_adjustment(pv, 0.75)[0] == pytest.approx(233.5, rel=0.05)
    assert risk_adjustment(pv, 0.65)[0] == pytest.approx(134.5, rel=0.05)
    assert risk_adjustment(pv, 0.85)[0] == pytest.approx(357.5, rel=0.05)
