"""Experience study and assumption review. Implements SPEC §8.2–§8.4.

Works only from the simulated experience and the basis. It must NEVER read the hidden truth file (SPEC §0 rule 8).
"""

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from lifemodel.basis import ASSUMPTIONS_DIR

Z95 = 1.96
FULL_CREDIBILITY = (1.645 / 0.05) ** 2  # 1082.41 claims: 90% probability of being within 5% (SPEC §4.7)
AGE_BANDS = [(25, 34, "25-34"), (35, 44, "35-44"), (45, 54, "45-54"), (55, 200, "55+")]
SA_BANDS = [(0, 150_000, "<150k"), (150_000, 300_000, "150-300k"), (300_000, 500_000, "300-500k"),
            (500_000, np.inf, "500k+")]
CUTS = ("total", "year", "t", "age_band", "sex", "smoker", "product", "channel", "sa_band")


def add_bands(exp: pd.DataFrame) -> pd.DataFrame:
    """Attained-age band and SA band columns (SPEC §8.2)."""
    attained = exp["issue_age"] + exp["t"]
    age_band = pd.Series(pd.NA, index=exp.index, dtype="object")
    for lo, hi, label in AGE_BANDS:
        age_band[(attained >= lo) & (attained <= hi)] = label
    sa_band = pd.Series(pd.NA, index=exp.index, dtype="object")
    for lo, hi, label in SA_BANDS:
        sa_band[(exp["sa"] >= lo) & (exp["sa"] < hi)] = label
    return exp.assign(age_band=age_band, sa_band=sa_band, total="all")


def ae_table(exp: pd.DataFrame, cut: str) -> pd.DataFrame:
    """Deaths by count and amount, lapses by count, with 95% CIs, for one cut. Implements SPEC §8.2–§8.3."""
    e = exp.assign(
        e_deaths=exp["q_basis"] * exp["exposed_death"],
        a_amount=exp["died"] * exp["sa_t"],
        e_amount=exp["q_basis"] * exp["sa_t"] * exp["exposed_death"],
        var_amount=exp["q_basis"] * (1 - exp["q_basis"]) * exp["sa_t"] ** 2 * exp["exposed_death"],
        e_lapses=exp["w_basis"] * exp["exposed_lapse"],
    )
    g = e.groupby(cut).agg(
        exposure=("exposed_death", "sum"), deaths=("died", "sum"), e_deaths=("e_deaths", "sum"),
        a_amount=("a_amount", "sum"), e_amount=("e_amount", "sum"), var_amount=("var_amount", "sum"),
        lapse_exposure=("exposed_lapse", "sum"), lapses=("lapsed", "sum"), e_lapses=("e_lapses", "sum"),
    )
    g["ae_deaths"] = g["deaths"] / g["e_deaths"]
    half = Z95 * np.sqrt(g["deaths"]) / g["e_deaths"]
    g["ae_deaths_lo"], g["ae_deaths_hi"] = g["ae_deaths"] - half, g["ae_deaths"] + half
    g["ae_amount"] = g["a_amount"] / g["e_amount"]
    half = Z95 * np.sqrt(g["var_amount"]) / g["e_amount"]
    g["ae_amount_lo"], g["ae_amount_hi"] = g["ae_amount"] - half, g["ae_amount"] + half
    g["ae_lapses"] = g["lapses"] / g["e_lapses"]
    half = Z95 * np.sqrt(g["lapses"]) / g["e_lapses"]
    g["ae_lapses_lo"], g["ae_lapses_hi"] = g["ae_lapses"] - half, g["ae_lapses"] + half
    g = g.drop(columns=["var_amount"]).reset_index().rename(columns={cut: "segment"})
    g.insert(0, "cut", cut)
    return g


def ae_study(exp: pd.DataFrame) -> pd.DataFrame:
    """A/E for every cut in SPEC §8.2, stacked."""
    banded = add_bands(exp)
    return pd.concat([ae_table(banded, cut) for cut in CUTS], ignore_index=True)


def credibility(actual_claims: float) -> float:
    """Limited-fluctuation credibility Z = min(1, √(A / 1082.41)). Implements SPEC §4.7."""
    return float(min(1.0, np.sqrt(actual_claims / FULL_CREDIBILITY)))


def assumption_review(exp: pd.DataFrame, old_basis_name: str = "basis_2022") -> dict:
    """Proposed changes at 31 Dec 2025 with reasons. Implements SPEC §8.4."""
    total = ae_table(add_bands(exp), "total").iloc[0]
    old = yaml.safe_load((ASSUMPTIONS_DIR / f"{old_basis_name}.yaml").read_text())
    z_mort = credibility(total["deaths"])
    z_lapse = credibility(total["lapses"])
    old_mort_adj = old["mortality"].get("experience_adjustment", 1.0)
    new_mort_adj = old_mort_adj * (1 + z_mort * (total["ae_deaths"] - 1))
    new_lapse = old["lapse"]["multiplier"] * (1 + z_lapse * (total["ae_lapses"] - 1))
    maint_ratio = exp["actual_maintenance"].sum() / exp["expected_maintenance"].sum()
    new_maint = old["expenses"]["maintenance"] * maint_ratio
    by_channel = ae_table(add_bands(exp), "channel").set_index("segment")["ae_lapses"]
    return {
        "mortality": dict(deaths=int(total["deaths"]), expected=float(total["e_deaths"]), ae=float(total["ae_deaths"]),
                          ci=[float(total["ae_deaths_lo"]), float(total["ae_deaths_hi"])], z=z_mort,
                          old=old_mort_adj, new=float(new_mort_adj)),
        "lapse": dict(lapses=int(total["lapses"]), expected=float(total["e_lapses"]), ae=float(total["ae_lapses"]),
                      ci=[float(total["ae_lapses_lo"]), float(total["ae_lapses_hi"])], z=z_lapse,
                      old=old["lapse"]["multiplier"], new=float(new_lapse)),
        "maintenance": dict(ratio=float(maint_ratio), old=old["expenses"]["maintenance"], new=float(new_maint)),
        "lapse_by_channel": {k: float(v) for k, v in by_channel.items()},
    }


def write_basis_2025(review: dict, old_basis_name: str = "basis_2022", path: Path = None) -> Path:
    """Write assumptions/basis_2025.yaml from the review, with a reasons block. Never hand-edited (SPEC §4.8)."""
    path = path or ASSUMPTIONS_DIR / "basis_2025.yaml"
    cfg = yaml.safe_load((ASSUMPTIONS_DIR / f"{old_basis_name}.yaml").read_text())
    m, l, e = review["mortality"], review["lapse"], review["maintenance"]
    cfg["name"] = "basis_2025"
    cfg["mortality"]["experience_adjustment"] = round(m["new"], 6)
    cfg["lapse"]["multiplier"] = round(l["new"], 6)
    cfg["expenses"]["maintenance"] = round(e["new"], 4)
    cfg["reasons"] = {
        "mortality": (f"2023-25 deaths {m['deaths']} vs expected {m['expected']:.1f}: A/E {m['ae']:.1%} "
                      f"(95% CI {m['ci'][0]:.1%}-{m['ci'][1]:.1%}). Credibility Z = {m['z']:.3f}, so the level moves "
                      f"only part of the way: adjustment {m['old']:.4f} -> {m['new']:.4f}."),
        "lapse": (f"Lapses {l['lapses']} vs expected {l['expected']:.1f}: A/E {l['ae']:.1%} "
                  f"(95% CI {l['ci'][0]:.1%}-{l['ci'][1]:.1%}), Z = {l['z']:.2f}; multiplier {l['old']:.4f} -> "
                  f"{l['new']:.4f}. Judgement: only policy years 1-3 were observed; the excess is assumed to persist "
                  "at all durations (early lapses in protection are driven by affordability and broker re-broking, "
                  "which do not obviously fade). To be revisited as later durations emerge."),
        "maintenance": (f"Expense investigation: actual maintenance cost {e['ratio']:.1%} of assumed; "
                        f"{e['old']:.2f} -> {e['new']:.2f} p.a. Company accounts, not a sample, so no credibility "
                        "weighting."),
        "channel": ("Lapse A/E broker " + f"{review['lapse_by_channel'].get('broker', float('nan')):.1%}, direct "
                    f"{review['lapse_by_channel'].get('direct', float('nan')):.1%}. Not built into the basis; "
                    "pricing recommendation only (commission clawback or channel-specific rates)."),
    }
    path.write_text("# GENERATED by lifemodel.experience.write_basis_2025 (SPEC §8.4). Do not edit by hand.\n"
                    + yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
    return path
