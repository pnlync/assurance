"""Synthetic policy data and sum-assured schedules. Implements SPEC §5."""

import numpy as np
import pandas as pd

N_POLICIES = 50_000
SEED = 2023
TERM = 20
MP_LOAN_RATE = 0.04
ISSUE_DATE = "2023-01-01"


def make_policy(product, issue_age, sex, smoker, sa, premium=np.nan, term=TERM, loan_rate=MP_LOAN_RATE):
    """A one-row policy table, e.g. the reference policies and the golden fixtures. Implements SPEC §5."""
    return pd.DataFrame(
        {
            "policy_id": ["REF"],
            "product": [product],
            "issue_age": [issue_age],
            "sex": [sex],
            "smoker": [bool(smoker)],
            "channel": ["broker"],
            "sa": [float(sa)],
            "term": [term],
            "loan_rate": [loan_rate if product == "MP" else np.nan],
            "premium": [float(premium)],
        }
    )


def generate_portfolio(n=N_POLICIES, seed=SEED):
    """The synthetic book of n policies issued on 1 Jan 2023 (premium filled later from the rate table). Implements SPEC §5."""
    rng = np.random.default_rng(seed)
    product = np.where(rng.random(n) < 0.5, "LTA", "MP")
    issue_age = rng.integers(25, 56, size=n)  # 25–55 inclusive
    sex = np.where(rng.random(n) < 0.5, "M", "F")
    smoker = rng.random(n) < 0.20
    channel = np.where(rng.random(n) < 0.70, "broker", "direct")

    lta_sa = np.clip(250_000 * np.exp(0.5 * rng.standard_normal(n)), 50_000, 1_000_000)
    mp_loan = np.clip(300_000 * np.exp(0.4 * rng.standard_normal(n)), 100_000, 800_000)
    sa = np.round(np.where(product == "LTA", lta_sa, mp_loan), -3)

    return pd.DataFrame(
        {
            "policy_id": [f"TL{i:06d}" for i in range(1, n + 1)],
            "product": product,
            "issue_age": issue_age,
            "sex": sex,
            "smoker": smoker,
            "channel": channel,
            "sa": sa,
            "term": TERM,
            "loan_rate": np.where(product == "MP", MP_LOAN_RATE, np.nan),
            "issue_date": ISSUE_DATE,
            "premium": np.nan,
        }
    )


def sum_assured_schedule(policies: pd.DataFrame) -> np.ndarray:
    """S_t for t = 0 … n−1, shape (N, n). LTA: S_t = SA. MP: S_t = SA (1 − v^(n−t)) / (1 − v^n). Implements SPEC §5."""
    n = int(policies["term"].max())
    t = np.arange(n)
    sa = policies["sa"].to_numpy(float)[:, None]
    is_mp = (policies["product"] == "MP").to_numpy()[:, None]
    v = 1.0 / (1.0 + np.nan_to_num(policies["loan_rate"].to_numpy(float))[:, None])
    with np.errstate(divide="ignore", invalid="ignore"):
        mp_factor = (1.0 - v ** (n - t)) / (1.0 - v**n)
    return np.where(is_mp, sa * mp_factor, sa * np.ones_like(mp_factor))
