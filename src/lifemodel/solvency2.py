"""Solvency II: BEL, selected life-underwriting stresses, SCR run-off and risk margin. Implements SPEC §4.5 and §9.

Parameters are those of SPEC §4.5 (Delegated Regulation (EU) 2015/35; risk margin as amended by
Delegated Regulation (EU) 2026/269, applying from 30 January 2027).
"""

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from lifemodel.basis import Basis
from lifemodel.curves import Curve
from lifemodel.portfolio import sum_assured_schedule
from lifemodel.projection import cash_flow_items, policy_term, project, rates, value

MORTALITY_SHOCK = 0.15      # Art. 137: q × 1.15, permanent
LAPSE_UP = 1.5              # Art. 142: w × 1.5, capped at 1
LAPSE_DOWN = 0.5            # Art. 142: w − min(0.5 w, 0.20)
LAPSE_DOWN_CAP = 0.20
MASS_LAPSE = 0.40           # Art. 142: 40% of policies discontinue immediately
EXPENSE_SHOCK = 0.10        # Art. 140: expenses × 1.10
INFLATION_SHOCK = 0.01      # Art. 140: expense inflation + 1 percentage point
CAT_SHOCK = 0.0015          # Art. 143: q + 0.0015 for the next 12 months
RISKS = ("mortality", "lapse", "expense", "cat")
CORRELATION = np.array([    # Art. 136, order (mortality, lapse, expense, cat)
    [1.00, 0.00, 0.25, 0.25],
    [0.00, 1.00, 0.50, 0.25],
    [0.25, 0.50, 1.00, 0.25],
    [0.25, 0.25, 0.25, 1.00],
])
COC_CURRENT = 0.06          # risk margin cost of capital, current rules
COC_2027 = 0.0475           # Delegated Regulation (EU) 2026/269
RM_DECAY = 0.96             # 2027 time-dependent weight max(0.96^t, 0.5)
RM_FLOOR = 0.5


def expense_shocked_basis(basis: Basis) -> Basis:
    """All expense items × 1.10 and inflation + 1pp; commission not shocked. Implements SPEC §4.5 (Art. 140)."""
    f = 1.0 + EXPENSE_SHOCK
    return replace(basis, acquisition=basis.acquisition * f, maintenance=basis.maintenance * f,
                   overhead=basis.overhead * f, claim_expense=basis.claim_expense * f,
                   inflation=basis.inflation + INFLATION_SHOCK)


def stress_losses(policies, basis: Basis, curve: Curve, start_duration: int = 0, include_overhead: bool = True):
    """Per-policy stress losses at each future time t ≥ start_duration, each (N, n), floored at 0. Implements SPEC §9.2.

    Returns a dict with the base V (N, n+1) and the losses: mortality, lapse_up, lapse_down, mass, expense, cat.
    Each permanent shock needs one backward recursion under the shocked basis, which gives every t at once.
    """
    k = start_duration
    q, w = rates(policies, basis)
    kw = dict(start_duration=k, include_overhead=include_overhead)
    V = value(policies, basis, curve, **kw)

    V_mort = value(policies, replace(basis, mortality_multiplier=basis.mortality_multiplier * (1 + MORTALITY_SHOCK)),
                   curve, **kw)
    V_up = value(policies, basis, curve, w=np.minimum(LAPSE_UP * w, 1.0), **kw)
    V_dn = value(policies, basis, curve, w=w - np.minimum(LAPSE_DOWN * w, LAPSE_DOWN_CAP), **kw)
    V_exp = value(policies, expense_shocked_basis(basis), curve, **kw)

    n = policy_term(policies)
    cf = cash_flow_items(policies, basis, include_overhead)
    v = np.full(n, np.nan)
    v[k:] = curve.one_year_factors(n - k)
    now = V[:, :n]
    later = V[:, 1:]
    zero = np.zeros_like(now)
    losses = {
        "mortality": np.maximum(V_mort[:, :n] - now, 0),
        "lapse_up": np.where(now < 0, np.maximum(V_up[:, :n] - now, 0), zero),
        "lapse_down": np.where(now > 0, np.maximum(V_dn[:, :n] - now, 0), zero),
        "mass": MASS_LAPSE * np.maximum(-now, 0),
        "expense": np.maximum(V_exp[:, :n] - now, 0),
        "cat": np.maximum(v * CAT_SHOCK * ((cf["sum_assured"] + cf["claim_expense"]) - (1 - w) * later), 0),
    }
    losses = {name: np.where(np.arange(n) >= k, loss, np.nan) for name, loss in losses.items()}
    return {"V": V, **losses}


def in_force_from(policies, basis: Basis, start_duration: int) -> np.ndarray:
    """ℓ_i(j): probability that a policy in force at the valuation date is still in force j years later, (N, n−k+1)."""
    l = project(policies, basis)["in_force"]
    return l[:, start_duration:] / l[:, [start_duration]]


def scr_path(policies, basis: Basis, curve: Curve, start_duration: int = 0, weights=None,
             include_overhead: bool = True) -> pd.DataFrame:
    """Portfolio SCR components and SCR_life at each future time j after the valuation date. Implements SPEC §9.3.

    Each risk at j = Σ_i ω_i ℓ_i(j) loss_i(k+j); lapse = max(up, down, mass); SCR_life = √(xᵀ Corr x).
    """
    k = start_duration
    n = policy_term(policies)
    weights = np.ones(len(policies)) if weights is None else np.asarray(weights, float)
    losses = stress_losses(policies, basis, curve, k, include_overhead)
    l = in_force_from(policies, basis, k)[:, : n - k] * weights[:, None]

    def total(name):
        return (l * losses[name][:, k:]).sum(axis=0)

    path = pd.DataFrame({"j": np.arange(n - k)})
    path["mortality"] = total("mortality")
    path["lapse_up"], path["lapse_down"], path["mass"] = total("lapse_up"), total("lapse_down"), total("mass")
    path["lapse"] = path[["lapse_up", "lapse_down", "mass"]].max(axis=1)
    path["expense"] = total("expense")
    path["cat"] = total("cat")
    x = path[list(RISKS)].to_numpy()
    path["scr_life"] = np.sqrt(np.einsum("ji,ik,jk->j", x, CORRELATION, x))
    return path


def bel(policies, basis: Basis, curve: Curve, start_duration: int = 0, weights=None, include_overhead=True) -> float:
    """BEL = Σ ω_i V_i(k) on the Solvency II basis. Implements SPEC §9.1."""
    weights = np.ones(len(policies)) if weights is None else np.asarray(weights, float)
    return float(weights @ value(policies, basis, curve, start_duration, include_overhead)[:, start_duration])


@dataclass
class RiskMargin:
    """Risk margin under current and 2027 rules (SPEC §4.5, §9.4)."""

    current: float
    rule_2027: float
    ratio: float
    identity_ratio: float


def risk_margin(scr: np.ndarray, curve: Curve) -> RiskMargin:
    """RM_old = 6% Σ SCR(j) DF(j+1); RM_2027 = 4.75% Σ max(0.96^j, 0.5) SCR(j) DF(j+1). Implements SPEC §4.5, §9.4.

    Also returns the identity RM_new/RM_old = (19/24) Σ π_j max(0.96^j, 0.5) (Said & Chaayra, 2026).
    """
    scr = np.asarray(scr, float)
    j = np.arange(len(scr))
    df = curve.df(j + 1)
    weight = np.maximum(RM_DECAY ** j, RM_FLOOR)
    rm_old = COC_CURRENT * float(scr @ df)
    rm_new = COC_2027 * float((weight * scr) @ df)
    pi = scr * df / float(scr @ df)
    identity = COC_2027 / COC_CURRENT * float(pi @ weight)
    return RiskMargin(rm_old, rm_new, rm_new / rm_old, identity)
