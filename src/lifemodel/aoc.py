"""Annual roll-forward and analysis of change, 2023–2025, for Solvency II and IFRS 17. Implements SPEC §11.

Each step changes one thing and revalues (SPEC §11.1):
S0 opening → S1 expected (roll forward one year) → S2 actual deaths → S3 actual lapses → S4 new assumptions →
S5 closing economics (year-end curve).
"""

import numpy as np
import pandas as pd

from lifemodel.basis import Basis
from lifemodel.curves import Curve
from lifemodel.ifrs17 import ModelPoints, coverage_units, risk_adjustment, scenario_multipliers
from lifemodel.portfolio import sum_assured_schedule
from lifemodel.projection import cash_flow_items, rates, value
from lifemodel.solvency2 import risk_margin, scr_path

ISSUE_YEAR = 2023


def year_sets(book: pd.DataFrame, experience: pd.DataFrame, year: int):
    """IF0 (in force at start), D (died in the year), IF1 (in force at end) as boolean masks over `book`."""
    e = experience[experience["year"] == year].set_index("policy_id")
    in0 = book["policy_id"].isin(e.index).to_numpy()
    died = book["policy_id"].map(e["died"]).fillna(0).to_numpy().astype(bool)
    lapsed = book["policy_id"].map(e["lapsed"]).fillna(0).to_numpy().astype(bool)
    maintenance = book["policy_id"].map(e["actual_maintenance"]).fillna(0).to_numpy()
    return in0, died, in0 & ~died & ~lapsed, maintenance


def step_values(book, masks, k, b0: Basis, b1: Basis, c0: Curve, c1: Curve, include_overhead: bool):
    """Per-policy contributions to S0…S5 plus X and EC (arrays over the book; 0 outside the relevant set). SPEC §11.1."""
    in0, died, in1, _ = masks
    c0f = c0.rolled_forward()
    q, w = rates(book, b0)
    cf = cash_flow_items(book, b0, include_overhead)
    s = cf["sum_assured"]
    v_b0_c0 = value(book, b0, c0, k, include_overhead)[:, k]
    v_b0_c0f = value(book, b0, c0f, k + 1, include_overhead)[:, k + 1]
    v_b1_c0f = value(book, b1, c0f, k + 1, include_overhead)[:, k + 1]
    v_b1_c1 = value(book, b1, c1, k + 1, include_overhead)[:, k + 1]
    x = -cf["premium"] + cf["commission"][:, k] + cf["expenses"][:, k]
    ec = q[:, k] * (s[:, k] + cf["claim_expense"][:, k])
    return {
        "S0": in0 * v_b0_c0,
        "X": in0 * x,
        "EC": in0 * ec,
        "S1": in0 * (1 - q[:, k]) * (1 - w[:, k]) * v_b0_c0f,
        "S2": (in0 & ~died) * (1 - w[:, k]) * v_b0_c0f,
        "S3": in1 * v_b0_c0f,
        "S4": in1 * v_b1_c0f,
        "S5": in1 * v_b1_c1,
        "actual_claims": died * (s[:, k] + cf["claim_expense"][:, k]),
    }


def be_walk(parts: dict, v_k: float) -> dict:
    """Walk lines from the step values (already summed over a set of policies). Implements SPEC §11.1."""
    lines = {
        "opening": parts["S0"],
        "expected_cash_flows": -parts["X"] - parts["EC"],
        "unwind": (parts["S0"] - parts["X"]) * (1 / v_k - 1),
        "mortality_experience": parts["S2"] - parts["S1"],
        "lapse_experience": parts["S3"] - parts["S2"],
        "assumption_change": parts["S4"] - parts["S3"],
        "economic": parts["S5"] - parts["S4"],
        "closing": parts["S5"],
    }
    lines["identity_error"] = parts["S1"] - ((parts["S0"] - parts["X"]) / v_k - parts["EC"])
    lines["walk_error"] = (sum(lines[key] for key in ("opening", "expected_cash_flows", "unwind",
                                                      "mortality_experience", "lapse_experience",
                                                      "assumption_change", "economic")) - lines["closing"])
    return lines


def solvency2_year(book, experience, year, b0, b1, c0, c1) -> dict:
    """Solvency II BEL walk (with overhead), SCR and RM at both ends of the year. Implements SPEC §11.1–§11.2."""
    k = year - ISSUE_YEAR
    masks = year_sets(book, experience, year)
    parts = {key: float(val.sum()) for key, val in step_values(book, masks, k, b0, b1, c0, c1, True).items()}
    walk = be_walk(parts, float(c0.df(1)))
    in0, died, in1, maintenance = masks
    walk["claims_a_minus_e"] = parts["actual_claims"] - parts["EC"]
    expected_maint = in0 * b0.maintenance * (1 + b0.inflation) ** k
    walk["maintenance_a_minus_e"] = float(maintenance.sum() - expected_maint.sum())
    p0, p1 = book[in0].reset_index(drop=True), book[in1].reset_index(drop=True)
    scr0 = scr_path(p0, b0, c0, k)["scr_life"].to_numpy()
    scr1 = scr_path(p1, b1, c1, k + 1)["scr_life"].to_numpy()
    rm0, rm1 = risk_margin(scr0, c0), risk_margin(scr1, c1)
    walk.update(scr_open=scr0[0], scr_close=scr1[0], rm_open=rm0.current, rm_close=rm1.current,
                rm2027_open=rm0.rule_2027, rm2027_close=rm1.rule_2027)
    return {"year": year, **walk}


def _group_sum(values: np.ndarray, labels: np.ndarray, names) -> pd.Series:
    return pd.Series(values).groupby(labels).sum().reindex(names, fill_value=0.0)


def ifrs17_year(book, experience, year, groups: pd.Series, opening: pd.DataFrame, b0, b1, c0, c1,
                locked_in: Curve, mp0: ModelPoints, mp1: ModelPoints, multipliers) -> pd.DataFrame:
    """IFRS 17 roll-forward by group for one year: BE, RA and CSM walks and P&L. Implements SPEC §11.3.

    `opening` is indexed by group with columns csm, loss_component. Returns one row per group.
    """
    k = year - ISSUE_YEAR
    masks = year_sets(book, experience, year)
    in0, died, in1, maintenance = masks
    labels = groups.to_numpy()
    names = opening.index
    cur = step_values(book, masks, k, b0, b1, c0, c1, include_overhead=False)
    lock = step_values(book, masks, k, b0, b1, locked_in.forward_from(k), locked_in.forward_from(k), False)
    # locked-in S1–S4 use curve L at duration k+1: step_values rolls its c0 forward once, so pass L seen at k
    agg = {key: _group_sum(val, labels, names) for key, val in cur.items()}
    agg_l = {key: _group_sum(val, labels, names) for key, val in lock.items()}
    v_k = float(c0.df(1))

    # Risk adjustment at the four points of SPEC §11.3 (common random numbers across all four)
    q, w = rates(book, b0)
    survive = (1 - q[:, k]) * (1 - w[:, k])
    lab = pd.Series(labels, index=book.index)

    def ra(mp, mask, weights, duration, curve):
        pv, got = mp.group_pv(book[mask], weights[mask], lab[mask], curve, duration, multipliers)
        return pd.Series(risk_adjustment(pv), index=got).reindex(names, fill_value=0.0)

    ones = np.ones(len(book))
    ra0 = ra(mp0, in0, ones, k, c0)
    ra_e = ra(mp0, in0, survive, k + 1, c1)
    ra_a = ra(mp0, in1, ones, k + 1, c1)
    ra1 = ra(mp1, in1, ones, k + 1, c1)

    # Coverage units: actual for the current year, expected (on B1) for later years
    s = sum_assured_schedule(book)
    cu_now = _group_sum(in0 * s[:, k], labels, names)
    cu_future = coverage_units(book[in1], b1, np.ones(in1.sum()), lab[in1], k + 1).sum().reindex(names, fill_value=0.0)

    expected_maint = in0 * b0.maintenance * (1 + b0.inflation) ** k
    rows = []
    for g in names:
        m_mort = agg_l["S2"][g] - agg_l["S1"][g]
        m_lapse = agg_l["S3"][g] - agg_l["S2"][g]
        m_assum = agg_l["S4"][g] - agg_l["S3"][g]
        d_ra_if = ra_a[g] - ra_e[g]
        d_ra_as = ra1[g] - ra_a[g]
        csm0, lc0 = opening.loc[g, "csm"], opening.loc[g, "loss_component"]
        accretion = csm0 * (locked_in.df(k) / locked_in.df(k + 1) - 1)
        adjustment = -(m_mort + m_lapse + m_assum + d_ra_if + d_ra_as)
        reversal = lc_increase = 0.0
        if lc0 > 0:
            if adjustment >= 0:
                reversal = min(lc0, adjustment)
                pre = csm0 + accretion + adjustment - reversal
            else:
                lc_increase, pre = -adjustment, csm0 + accretion
        else:
            pre = csm0 + accretion + adjustment
            if pre < 0:
                lc_increase, pre = -pre, 0.0
        total_cu = cu_now[g] + cu_future[g]
        release = pre * cu_now[g] / total_cu if total_cu > 0 else pre
        csm1 = pre - release
        be = be_walk({key: agg[key][g] for key in agg}, v_k)
        claims_ame = agg["actual_claims"][g] - agg["EC"][g]
        maint_ame = float(_group_sum(maintenance - expected_maint, labels, names)[g])
        ra_release = ra0[g] - ra_e[g]
        insurance_service_result = (release + ra_release - claims_ame - maint_ame - lc_increase + reversal)
        finance_expense = (be["unwind"] + be["economic"]
                           + (be["mortality_experience"] + be["lapse_experience"] + be["assumption_change"]
                              - (m_mort + m_lapse + m_assum))
                           + accretion)
        rows.append({
            "year": year, "group": g,
            **{f"be_{key}": val for key, val in be.items()},
            "ra_opening": ra0[g], "ra_release": -ra_release, "ra_future_service_experience": d_ra_if,
            "ra_assumption_change": d_ra_as, "ra_closing": ra1[g],
            "ra_walk_error": ra0[g] - ra_release + d_ra_if + d_ra_as - ra1[g],
            "csm_opening": csm0, "csm_accretion": accretion,
            "csm_adj_mortality": -m_mort, "csm_adj_lapse": -m_lapse, "csm_adj_assumptions": -m_assum,
            "csm_adj_ra": -(d_ra_if + d_ra_as), "csm_lc_absorbed": pre - (csm0 + accretion + adjustment),
            "csm_release": -release, "csm_closing": csm1,
            "csm_walk_error": csm0 + accretion + adjustment + (pre - (csm0 + accretion + adjustment)) - release - csm1,
            "lc_opening": lc0, "lc_increase": lc_increase, "lc_reversal": -reversal,
            "lc_closing": lc0 + lc_increase - reversal,
            "cu_current": cu_now[g], "cu_future": cu_future[g],
            "claims_a_minus_e": claims_ame, "maintenance_a_minus_e": maint_ame,
            "insurance_service_result": insurance_service_result,
            "insurance_finance_expense": finance_expense,
        })
    return pd.DataFrame(rows)
