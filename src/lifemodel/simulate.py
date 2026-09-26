"""Simulation of 2023–2025 experience from the hidden truth basis. Implements SPEC §8.1.

This is the ONLY module allowed to read assumptions/truth.yaml (SPEC §0 rule 8).
"""

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from lifemodel.basis import ASSUMPTIONS_DIR, Basis
from lifemodel.portfolio import sum_assured_schedule
from lifemodel.projection import rates

SEED = 2025
YEARS = (2023, 2024, 2025)
ATTRIBUTES = ["policy_id", "product", "issue_age", "sex", "smoker", "channel", "sa", "premium"]


def load_truth(path: Path = ASSUMPTIONS_DIR / "truth.yaml") -> dict:
    """The hidden truth parameters (SPEC §4.6)."""
    return yaml.safe_load(path.read_text())


def true_rates(policies: pd.DataFrame, basis: Basis, truth: dict):
    """True q and w: q × mortality multiplier; w × lapse multiplier × channel factor; both capped at 1. Implements SPEC §4.6."""
    q, w = rates(policies, basis)
    channel = policies["channel"].map(truth["lapse_channel_factor"]).to_numpy(float)[:, None]
    q_true = np.minimum(1.0, q * truth["mortality_multiplier"])
    w_true = np.minimum(1.0, w * truth["lapse_multiplier"] * channel)
    return q_true, w_true


def simulate(policies: pd.DataFrame, basis: Basis, truth: dict, seed: int = SEED, years=YEARS) -> pd.DataFrame:
    """One row per policy-year in force at the start of each calendar year. Implements SPEC §8.1.

    Death ~ Bernoulli(q_true); survivors lapse ~ Bernoulli(w_true) (none in the final policy year).
    Columns: attributes, year, t, sa_t, exposed_death, died, exposed_lapse, lapsed, q_basis, w_basis,
    actual_maintenance, expected_maintenance.
    """
    rng = np.random.default_rng(seed)
    q_basis, w_basis = rates(policies, basis)
    q_true, w_true = true_rates(policies, basis, truth)
    s = sum_assured_schedule(policies)
    n = q_basis.shape[1]
    in_force = np.ones(len(policies), dtype=bool)
    rows = []
    for t, year in enumerate(years):
        idx = np.nonzero(in_force)[0]
        died = rng.random(len(idx)) < q_true[idx, t]
        lapsed = ~died & (rng.random(len(idx)) < w_true[idx, t]) & (t < n - 1)
        expected_maint = basis.maintenance * (1 + basis.inflation) ** t
        frame = policies.iloc[idx][ATTRIBUTES].reset_index(drop=True)
        frame["year"], frame["t"] = year, t
        frame["sa_t"] = s[idx, t]
        frame["exposed_death"], frame["died"] = 1, died.astype(int)
        frame["exposed_lapse"], frame["lapsed"] = 1 - died.astype(int), lapsed.astype(int)
        frame["q_basis"], frame["w_basis"] = q_basis[idx, t], w_basis[idx, t]
        frame["expected_maintenance"] = expected_maint
        frame["actual_maintenance"] = truth["maintenance_expense_multiplier"] * expected_maint
        rows.append(frame)
        in_force[idx[died | lapsed]] = False
    return pd.concat(rows, ignore_index=True)


def in_force_after(policies: pd.DataFrame, experience: pd.DataFrame, year: int) -> np.ndarray:
    """Boolean mask of policies still in force at 31 Dec `year` (after that year's deaths and lapses)."""
    exits = experience[(experience["year"] <= year) & ((experience["died"] == 1) | (experience["lapsed"] == 1))]
    return ~policies["policy_id"].isin(exits["policy_id"]).to_numpy()
