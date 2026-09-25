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
