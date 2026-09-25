"""Pricing and profit testing. Implements SPEC §7."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from lifemodel.basis import Basis
from lifemodel.curves import Curve
from lifemodel.portfolio import make_policy
from lifemodel.projection import cash_flow_items, project, rates, value


@dataclass
class ProfitTest:
    """Profit-test results for one policy (SPEC §7.3). Arrays are indexed by policy year t = 0 … n−1."""

    premium: float
    reserves: np.ndarray          # _tV for t = 0 … n (length n+1)
    profit_vector: np.ndarray     # Pr_t, per policy in force at t, received at t+1
    profit_signature: np.ndarray  # Π_t = ℓ_t Pr_t
    npv: float
    epv_premiums: float
    margin: float
    irr: float
    discounted_payback: float     # first time t+1 at which cumulative discounted Π ≥ 0 (NaN if never)
    npv_no_reserves: float


def profit_vector(premium, commission, expenses, q, w, sum_assured, claim_expense, reserves, earned_rate):
    """Pr_t = (_tV + P − comm_t − exp_t)(1 + i) − q_t (S_t + CE_t) − (1 − q_t)(1 − w_t) _{t+1}V. Implements SPEC §7.3."""
    return (
        (reserves[:-1] + premium - commission - expenses) * (1.0 + earned_rate)
        - q * (sum_assured + claim_expense)
        - (1.0 - q) * (1.0 - w) * reserves[1:]
    )


def profit_measures(signature, premium, in_force, rdr):
    """NPV, EPV of premiums, margin, IRR and discounted payback from a profit signature. Implements SPEC §7.3."""
    n = len(signature)
    t = np.arange(n)
    disc_end = (1.0 + rdr) ** -(t + 1.0)
    npv = float(signature @ disc_end)
    epv_premiums = float((in_force[:n] * premium) @ ((1.0 + rdr) ** -t.astype(float)))
    cumulative = np.cumsum(signature * disc_end)
    paid_back = np.nonzero(cumulative >= 0)[0]
    payback = float(paid_back[0] + 1) if len(paid_back) else np.nan
    return npv, epv_premiums, npv / epv_premiums, irr(signature), payback


def irr(signature) -> float:
    """IRR solving Σ Π_t (1 + IRR)^−(t+1) = 0; NaN if there is no sign change. Implements SPEC §7.3."""
    t = np.arange(len(signature))

    def npv_at(r):
        return float(signature @ (1.0 + r) ** -(t + 1.0))

    lo, hi = -0.99, 10.0
    if np.sign(npv_at(lo)) == np.sign(npv_at(hi)):
        return np.nan
    return brentq(npv_at, lo, hi, xtol=1e-14)


def reserves(policy: pd.DataFrame, basis: Basis) -> np.ndarray:
    """Zeroised prospective reserves on the reserving basis: _tV = max(0, V^R_t), _0V = _nV = 0. Implements SPEC §7.3, §4.2."""
    reserving = basis.reserving_basis()
    v_r = value(policy, reserving, Curve.flat(basis.reserve_interest), include_overhead=True)[0]
    res = np.maximum(0.0, v_r)
    res[0] = 0.0
    res[-1] = 0.0
    return res


def profit_test(policy: pd.DataFrame, basis: Basis, hold_reserves: bool = True) -> ProfitTest:
    """Profit test of a single policy on the pricing basis, including overhead. Implements SPEC §7.3."""
    if len(policy) != 1:
        raise ValueError("profit_test works on one policy at a time.")
    q, w = rates(policy, basis)
    cf = cash_flow_items(policy, basis, include_overhead=True)
    in_force = project(policy, basis)["in_force"][0]
    premium = float(cf["premium"][0])
    n = q.shape[1]

    def run(res):
        pr = profit_vector(
            premium, cf["commission"][0], cf["expenses"][0], q[0], w[0],
            cf["sum_assured"][0], cf["claim_expense"][0], res, basis.earned_rate,
        )
        return pr, in_force[:n] * pr

    res = reserves(policy, basis) if hold_reserves else np.zeros(n + 1)
    pr, sig = run(res)
    npv, epv, margin, irr_, payback = profit_measures(sig, premium, in_force, basis.risk_discount_rate)
    _, sig0 = run(np.zeros(n + 1))
    npv0 = float(sig0 @ (1.0 + basis.risk_discount_rate) ** -(np.arange(n) + 1.0))
    return ProfitTest(premium, res, pr, sig, npv, epv, margin, irr_, payback, npv0)


def premium_from_rate(rate: float, sa: float, basis: Basis) -> float:
    """P = rate × SA / 1000 + fee. Implements SPEC §4.1."""
    return rate * sa / 1000.0 + basis.policy_fee


def solve_rate(product, issue_age, sex, smoker, basis: Basis, sa=None) -> float:
    """Rate per 1,000 SA giving the target profit margin for a reference policy. Implements SPEC §7.2."""
    sa = basis.reference_sa[product] if sa is None else sa

    def margin_gap(rate):
        policy = make_policy(product, issue_age, sex, smoker, sa, premium_from_rate(rate, sa, basis))
        return profit_test(policy, basis).margin - basis.target_margin

    return brentq(margin_gap, 0.0, 200.0, xtol=1e-12)


def profit_test_exam_mode(premium, commission, expenses, q, w, sum_assured, claim_expense, reserves, earned_rate, rdr):
    """Profit test on an explicitly supplied basis and reserve vector (CM1 / CT5 past papers). Implements SPEC §7.5.

    All per-year inputs are arrays of length n (reserves: length n+1). Returns (profit vector, signature, NPV).
    """
    q, w = np.asarray(q, float), np.asarray(w, float)
    in_force = np.concatenate([[1.0], np.cumprod((1.0 - q) * (1.0 - w))])
    pr = profit_vector(premium, np.asarray(commission, float), np.asarray(expenses, float), q, w,
                       np.asarray(sum_assured, float), np.asarray(claim_expense, float),
                       np.asarray(reserves, float), earned_rate)
    sig = in_force[:-1] * pr
    npv = float(sig @ (1.0 + rdr) ** -(np.arange(len(sig)) + 1.0))
    return pr, sig, npv
