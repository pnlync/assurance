"""IFRS 17 general measurement model: grouping, FCF, Monte Carlo RA, CSM and coverage units. Implements SPEC §4.4, §10.

Valuation engine for the RA: within one (product, sex, smoker, issue age, loan rate) combination every cash flow
is affine in the sum assured (premium, commission, claims ∝ SA; expenses fixed), so V_i = V(SA=0) + SA_i · slope.
Two model points per combination therefore reproduce every policy exactly (SPEC §10.3 allows grouped model points
if grouped and seriatim BE agree within 0.1%; here they agree to rounding — tested).
"""

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from lifemodel.basis import Basis
from lifemodel.curves import Curve
from lifemodel.experience import SA_BANDS
from lifemodel.projection import cash_flow_items, policy_term, project, rates
from lifemodel.portfolio import sum_assured_schedule
from lifemodel.solvency2 import COC_CURRENT, scr_path

RA_SCENARIOS = 10_000
RA_SEED = 17
Z_995 = 2.5758293035489
SIGMA = np.log(np.array([1.15, 1.5, 1.10])) / Z_995  # each risk's 99.5th percentile = the Solvency II stress
RA_CORRELATION = np.array([[1.0, 0.0, 0.25], [0.0, 1.0, 0.5], [0.25, 0.5, 1.0]])  # mortality, lapse, expense
RA_LEVEL = 0.75
RA_LEVELS_REPORTED = (0.65, 0.75, 0.85)
G2_STRESS = dict(mortality=1.15, lapse=1.5)  # "no significant possibility of becoming onerous" test (SPEC §10.1)
IFRS_AGE_BANDS = [(25, 34, "25-34"), (35, 44, "35-44"), (45, 55, "45-55")]
SA_UNIT = 100_000.0
COMBO_KEYS = ["product", "sex", "smoker", "issue_age"]


def cell_labels(policies: pd.DataFrame) -> pd.Series:
    """IFRS 17 cell: portfolio (product) × smoker × issue-age band × SA band; not split by sex (para 20). SPEC §10.1."""
    age = pd.Series("", index=policies.index)
    for lo, hi, label in IFRS_AGE_BANDS:
        age[(policies["issue_age"] >= lo) & (policies["issue_age"] <= hi)] = label
    sa = pd.Series("", index=policies.index)
    for lo, hi, label in SA_BANDS:
        sa[(policies["sa"] >= lo) & (policies["sa"] < hi)] = label
    smoker = np.where(policies["smoker"], "S", "NS")
    return policies["product"] + "|" + smoker + "|" + age + "|" + sa


def scenario_multipliers(n: int = RA_SCENARIOS, seed: int = RA_SEED) -> np.ndarray:
    """(n, 3) mean-one lognormal multipliers for mortality, lapse and expense. Implements SPEC §10.3."""
    rng = np.random.default_rng(seed)
    z = rng.multivariate_normal(np.zeros(3), RA_CORRELATION, size=n)
    return np.exp(SIGMA * z - SIGMA**2 / 2)


class ModelPoints:
    """Two model points (SA = 0 and SA = 100,000) per (product, sex, smoker, issue age) combination."""

    def __init__(self, policies: pd.DataFrame, basis: Basis):
        fee = basis.policy_fee
        rate = (policies["premium"] - fee) * 1000 / policies["sa"]
        combos = policies.assign(rate=rate).groupby(COMBO_KEYS, sort=True).agg(
            rate=("rate", "mean"), rate_spread=("rate", lambda r: r.max() - r.min()),
            loan_rate=("loan_rate", "first"), term=("term", "first")).reset_index()
        if (combos["rate_spread"] > 1e-9).any():
            raise ValueError("Premium rate is not unique within a combination; the affine model-point trick fails.")
        self.combos = combos
        self.basis = basis
        points = pd.concat([combos.assign(sa=0.0), combos.assign(sa=SA_UNIT)], ignore_index=True)
        points["premium"] = points["rate"] * points["sa"] / 1000 + fee
        points["channel"] = "direct"  # irrelevant to the basis
        self.points = points
        self.n = policy_term(points)
        q, w = rates(points, basis)  # includes basis multipliers
        self.q, self.w = q, w
        self.cf_no_overhead = cash_flow_items(points, basis, include_overhead=False)
        index = pd.MultiIndex.from_frame(combos[COMBO_KEYS])
        self._lookup = pd.Series(np.arange(len(combos)), index=index)

    def combo_of(self, policies: pd.DataFrame) -> np.ndarray:
        """Combination index of each policy."""
        return self._lookup.reindex(pd.MultiIndex.from_frame(policies[COMBO_KEYS])).to_numpy()

    def values(self, curve: Curve, start: int, multipliers: np.ndarray, premium_factor: float = 1.0):
        """V at duration `start` for every scenario, IFRS 17 basis (no overhead). Returns (V0, slope), each (S, C).

        multipliers (S, 3): mortality on q, lapse on w (both capped at 1), expense on attributable expenses and
        claim expenses (not commission). Same recursion as SPEC §2.4, vectorised over scenarios.
        """
        m, l, e = (multipliers[:, i][:, None] for i in range(3))
        cf = self.cf_no_overhead
        premium = premium_factor * cf["premium"][None, :]
        commission = premium_factor * cf["commission"]
        v = curve.one_year_factors(self.n - start)
        V = np.zeros((len(multipliers), len(self.points)))
        for t in range(self.n - 1, start - 1, -1):
            q = np.minimum(1.0, m * self.q[None, :, t])
            w = np.minimum(1.0, l * self.w[None, :, t])
            V = (-premium + commission[None, :, t] + e * cf["expenses"][None, :, t]
                 + v[t - start] * (q * (cf["sum_assured"][None, :, t] + e * cf["claim_expense"][None, :, t])
                                   + (1 - q) * (1 - w) * V))
        c = len(self.combos)
        return V[:, :c], (V[:, c:] - V[:, :c]) / SA_UNIT

    def aggregation(self, policies: pd.DataFrame, weights, labels: pd.Series):
        """Matrices W0, W1 (C, G) so that PV_group = V0 @ W0 + slope @ W1; plus the group names."""
        weights = np.asarray(weights, float)
        names = np.array(sorted(labels.unique()))
        g = np.searchsorted(names, labels.to_numpy())
        c = self.combo_of(policies)
        W0 = np.zeros((len(self.combos), len(names)))
        W1 = np.zeros_like(W0)
        np.add.at(W0, (c, g), weights)
        np.add.at(W1, (c, g), weights * policies["sa"].to_numpy(float))
        return W0, W1, names

    def group_pv(self, policies, weights, labels, curve, start, multipliers, premium_factor=1.0):
        """(S, G) present values by group and the group names."""
        V0, slope = self.values(curve, start, multipliers, premium_factor)
        W0, W1, names = self.aggregation(policies, weights, labels)
        return V0 @ W0 + slope @ W1, names


def risk_adjustment(pv: np.ndarray, level: float = RA_LEVEL) -> np.ndarray:
    """RA = Q_level(PV) − mean(PV) per column. Implements SPEC §10.3."""
    return np.quantile(pv, level, axis=0) - pv.mean(axis=0)


BASE = np.ones((1, 3))


def coverage_units(policies, basis: Basis, weights, labels, start: int):
    """Expected coverage units CU_j = Σ ω ℓ(j) S_j for j ≥ start, by group: DataFrame (years × groups). SPEC §10.4."""
    l = project(policies, basis)["in_force"]
    rel = l[:, start:-1] / l[:, [start]]
    s = sum_assured_schedule(policies)[:, start:]
    cu = rel * s * np.asarray(weights, float)[:, None]
    frame = pd.DataFrame(cu.T, index=np.arange(start, policy_term(policies)))
    return frame.T.groupby(labels.to_numpy()).sum().T


def csm_expected_runoff(csm0: float, cu: np.ndarray, locked_in: Curve, start: int = 0) -> pd.DataFrame:
    """CSM roll-forward with no experience: accrete at locked-in forward rate, release by CU share. SPEC §10.4, §11.3."""
    rows, csm = [], csm0
    cu = np.asarray(cu, float)
    for i, k in enumerate(range(start, start + len(cu))):
        accretion = csm * (locked_in.df(k) / locked_in.df(k + 1) - 1)
        pre = csm + accretion
        release = pre * cu[i] / cu[i:].sum()
        rows.append({"year": k + 1, "opening": csm, "accretion": accretion, "release": release,
                     "closing": pre - release})
        csm = pre - release
    return pd.DataFrame(rows)


@dataclass
class InitialRecognition:
    cells: pd.DataFrame
    groups: pd.DataFrame
    policy_group: pd.Series
    pv_scenarios: np.ndarray   # (S, G) group PVs at issue, for percentile reporting
    group_names: np.ndarray


def initial_recognition(book: pd.DataFrame, basis: Basis, locked_in: Curve,
                        multipliers: np.ndarray = None) -> InitialRecognition:
    """Cells, onerous classification, groups, FCF, RA, CSM_0 and LC_0 at 1 Jan 2023. Implements SPEC §10.1–10.5, §10.7."""
    multipliers = scenario_multipliers() if multipliers is None else multipliers
    mp = ModelPoints(book, basis)
    ones = np.ones(len(book))
    cells = cell_labels(book)
    pv_cells, cell_names = mp.group_pv(book, ones, cells, locked_in, 0, multipliers)
    be_cells, _ = mp.group_pv(book, ones, cells, locked_in, 0, BASE)
    stressed = np.array([[G2_STRESS["mortality"], G2_STRESS["lapse"], 1.0]])
    be_stress, _ = mp.group_pv(book, ones, cells, locked_in, 0, stressed)
    ra_cells = risk_adjustment(pv_cells)
    table = pd.DataFrame({"cell": cell_names, "be": be_cells[0], "ra": ra_cells, "be_stressed": be_stress[0]})
    table["group"] = np.select(
        [table["be"] + table["ra"] > 0, table["be_stressed"] + table["ra"] < 0], ["G1", "G2"], "G3")
    table["portfolio"] = table["cell"].str.split("|").str[0]
    table["group"] = table["portfolio"] + "-" + table["group"]
    counts = cells.value_counts()
    table["policies"] = table["cell"].map(counts)

    policy_group = cells.map(table.set_index("cell")["group"])
    pv_groups, group_names = mp.group_pv(book, ones, policy_group, locked_in, 0, multipliers)
    be_groups, _ = mp.group_pv(book, ones, policy_group, locked_in, 0, BASE)
    groups = pd.DataFrame({"group": group_names, "be": be_groups[0]})
    for p in RA_LEVELS_REPORTED:
        groups[f"ra_{int(p * 100)}"] = risk_adjustment(pv_groups, p)
    groups["ra"] = groups[f"ra_{int(RA_LEVEL * 100)}"]
    groups["fcf"] = groups["be"] + groups["ra"]
    groups["csm"] = np.maximum(0.0, -groups["fcf"])
    groups["loss_component"] = np.maximum(0.0, groups["fcf"])
    groups["policies"] = groups["group"].map(policy_group.value_counts())
    prem = book["premium"].to_numpy()
    df = locked_in.df(np.arange(policy_term(book) + 1))
    l = project(book, basis)["in_force"][:, :-1]
    pv_prem = (l * prem[:, None]) @ df[:-1]
    groups["pv_premiums"] = groups["group"].map(pd.Series(pv_prem).groupby(policy_group.to_numpy()).sum())
    # Cost-of-capital comparison: 6% × Σ SCR_life(j) DF(j+1) on the IFRS basis, and its implied confidence level
    ra_coc, implied = [], []
    for name, pv in zip(group_names, pv_groups.T):
        part = book[policy_group.to_numpy() == name]
        path = scr_path(part, basis, locked_in, include_overhead=False)
        coc = COC_CURRENT * float(path["scr_life"].to_numpy() @ locked_in.df(np.arange(len(path)) + 1))
        ra_coc.append(coc)
        implied.append(float((pv <= pv.mean() + coc).mean()))
    groups["ra_coc"], groups["ra_coc_confidence"] = ra_coc, implied
    return InitialRecognition(table, groups, policy_group, pv_groups, group_names)


def onerous_premium_factor(book, basis: Basis, locked_in: Curve, init: InitialRecognition) -> float:
    """Uniform premium factor f at which the combined FCF of G2 + G3 reaches 0 (RA held at base). SPEC §10.6."""
    mp = ModelPoints(book, basis)
    profitable = init.policy_group.str.endswith(("G2", "G3"))
    ra = init.groups.loc[init.groups["group"].str.endswith(("G2", "G3")), "ra"].sum()
    part = book[profitable.to_numpy()]
    labels = pd.Series("profitable", index=part.index)

    def fcf(f):
        pv, _ = mp.group_pv(part, np.ones(len(part)), labels, locked_in, 0, BASE, premium_factor=f)
        return float(pv[0, 0]) + ra

    return brentq(fcf, 0.05, 1.0, xtol=1e-10)
