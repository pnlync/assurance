"""Projection engine: rates, cash flows, backward valuation and forward projection. Implements SPEC §2 and §6."""

import numpy as np
import pandas as pd

from lifemodel.basis import Basis
from lifemodel.curves import Curve
from lifemodel.portfolio import sum_assured_schedule


def policy_term(policies: pd.DataFrame) -> int:
    """n, the common policy term (SPEC §2.1: n = 20 for every policy)."""
    terms = policies["term"].unique()
    if len(terms) != 1:
        raise ValueError("SPEC §2.1 assumes one common term for all policies.")
    return int(terms[0])


def rates(policies: pd.DataFrame, basis: Basis):
    """q_t and w_t, each shape (N, n). Implements SPEC §6.1, §2.6, §2.7."""
    n = policy_term(policies)
    t = np.arange(n)[None, :]
    age = policies["issue_age"].to_numpy(float)[:, None] + t
    female = (policies["sex"] == "F").to_numpy()[:, None]
    smoker = policies["smoker"].to_numpy(bool)[:, None]
    q = np.minimum(1.0, basis.mortality_multiplier * basis.mortality_table.q(age, t, female, smoker))

    by_year = np.array(basis.lapse_by_policy_year)
    w_row = np.array([by_year[k] if k < len(by_year) else basis.lapse_ultimate for k in range(n)])
    w_row = np.minimum(1.0, basis.lapse_multiplier * w_row)
    w_row[n - 1] = 0.0  # no lapse at the end of the final year
    w = np.broadcast_to(w_row, q.shape).copy()
    return q, w


def cash_flow_items(policies: pd.DataFrame, basis: Basis, include_overhead: bool = True):
    """Per-policy cash-flow items by policy year, per policy in force at t. Implements SPEC §6.2, §2.2, §2.8, §4.1.

    Returns a dict with premium (N,), commission, expenses, sum_assured, claim_expense (each (N, n)).
    """
    n = policy_term(policies)
    t = np.arange(n)
    inflation_index = (1.0 + basis.inflation) ** t  # index for policy year t

    premium = policies["premium"].to_numpy(float)
    commission = np.zeros((len(policies), n))
    commission[:, 0] = basis.commission_first_year * premium

    per_year = basis.maintenance + (basis.overhead if include_overhead else 0.0)
    expenses = np.broadcast_to(per_year * inflation_index, (len(policies), n)).copy()
    expenses[:, 0] += basis.acquisition

    claim_expense = np.broadcast_to(basis.claim_expense * inflation_index, (len(policies), n)).copy()
    return {
        "premium": premium,
        "commission": commission,
        "expenses": expenses,
        "sum_assured": sum_assured_schedule(policies),
        "claim_expense": claim_expense,
    }


def value(policies, basis, curve: Curve, start_duration: int = 0, include_overhead: bool = True):
    """V_t by backward recursion for t ≥ start_duration, shape (N, n+1); earlier columns are NaN. Implements SPEC §6.3, §2.4.

    V_t = −P + comm_t + exp_t + v_t [ q_t (S_t + CE_t) + (1 − q_t)(1 − w_t) V_{t+1} ],  V_n = 0.
    Positive = liability; negative = expected future profit.
    """
    n = policy_term(policies)
    q, w = rates(policies, basis)
    cf = cash_flow_items(policies, basis, include_overhead)
    v = curve.one_year_factors(n - start_duration)  # v[j] discounts policy year start_duration + j

    V = np.full((len(policies), n + 1), np.nan)
    V[:, n] = 0.0
    for t in range(n - 1, start_duration - 1, -1):
        outgo_now = -cf["premium"] + cf["commission"][:, t] + cf["expenses"][:, t]
        death_claim = q[:, t] * (cf["sum_assured"][:, t] + cf["claim_expense"][:, t])
        continuing = (1.0 - q[:, t]) * (1.0 - w[:, t]) * V[:, t + 1]
        V[:, t] = outgo_now + v[t - start_duration] * (death_claim + continuing)
    return V


def project(policies: pd.DataFrame, basis: Basis, include_overhead: bool = True):
    """Forward projection from issue: in-force ℓ_t, expected deaths and lapses, expected cash flows. Implements SPEC §6.4, §2.3.

    All arrays are per policy issued (weighted by ℓ_t); shape (N, n) except in_force (N, n+1).
    """
    n = policy_term(policies)
    q, w = rates(policies, basis)
    cf = cash_flow_items(policies, basis, include_overhead)

    in_force = np.ones((len(policies), n + 1))
    for t in range(n):
        in_force[:, t + 1] = in_force[:, t] * (1.0 - q[:, t]) * (1.0 - w[:, t])
    l = in_force[:, :n]
    deaths = l * q
    return {
        "q": q,
        "w": w,
        "in_force": in_force,
        "deaths": deaths,
        "lapses": l * (1.0 - q) * w,
        "premiums": l * cf["premium"][:, None],        # at time t
        "commission": l * cf["commission"],            # at time t
        "expenses": l * cf["expenses"],                # at time t
        "claims": deaths * cf["sum_assured"],          # at time t+1
        "claim_expenses": deaths * cf["claim_expense"],  # at time t+1
    }


def forward_pv(policies: pd.DataFrame, basis: Basis, curve: Curve, include_overhead: bool = True) -> np.ndarray:
    """PV at issue of the projected cash flows, discounted on `curve`; must equal V_0. Implements SPEC §6.5."""
    n = policy_term(policies)
    p = project(policies, basis, include_overhead)
    df = curve.df(np.arange(n + 1))
    at_start = (-p["premiums"] + p["commission"] + p["expenses"]) @ df[:n]
    at_end = (p["claims"] + p["claim_expenses"]) @ df[1:]
    return at_start + at_end
