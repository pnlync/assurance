"""Build every Phase 2 output: simulated experience, A/E study, basis_2025, Solvency II. Implements SPEC §8, §9."""

from pathlib import Path

import numpy as np
import pandas as pd

from lifemodel import charts
from lifemodel.basis import load_basis
from lifemodel.curves import Curve
from lifemodel.experience import add_bands, ae_study, ae_table, assumption_review, write_basis_2025
from lifemodel.simulate import in_force_after, load_truth, simulate
from lifemodel.solvency2 import RISKS, bel, risk_margin, scr_path

ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / "outputs" / "tables"
PROCESSED = ROOT / "data" / "processed"
NOTE = "Synthetic book, simulated 2023–25 experience, illustrative assumptions."


def load_book() -> pd.DataFrame:
    """The priced 50,000-policy book written by run_phase1."""
    return pd.read_csv(PROCESSED / "portfolio.csv")


def solvency_summary(book, basis, curve, k, label) -> tuple[pd.DataFrame, pd.DataFrame]:
    """BEL, SCR components, RM (current, 2027) by product and total, plus the SCR run-off. Implements SPEC §9.6."""
    rows, paths = [], []
    for product in ("LTA", "MP", "Total"):
        part = book if product == "Total" else book[book["product"] == product]
        path = scr_path(part, basis, curve, k)
        rm = risk_margin(path["scr_life"].to_numpy(), curve)
        up = risk_margin(path["scr_life"].to_numpy(), Curve(curve.spot + 0.01))
        dn = risk_margin(path["scr_life"].to_numpy(), Curve(curve.spot - 0.01))
        b = bel(part, basis, curve, k)
        row = {"valuation": label, "product": product, "policies": len(part), "bel": b,
               **{f"scr_{r}": path[r].iloc[0] for r in RISKS},
               "scr_lapse_up": path["lapse_up"].iloc[0], "scr_lapse_down": path["lapse_down"].iloc[0],
               "scr_mass_lapse": path["mass"].iloc[0], "scr_life": path["scr_life"].iloc[0],
               "diversification": path[list(RISKS)].iloc[0].sum() - path["scr_life"].iloc[0],
               "rm_current": rm.current, "rm_2027": rm.rule_2027, "rm_ratio": rm.ratio,
               "rm_identity": rm.identity_ratio,
               "rm_current_rates_up100": up.current, "rm_current_rates_dn100": dn.current,
               "rm_2027_rates_up100": up.rule_2027, "rm_2027_rates_dn100": dn.rule_2027,
               "own_funds_rm_current": -(b + rm.current), "own_funds_rm_2027": -(b + rm.rule_2027)}
        rows.append(row)
        paths.append(path.assign(valuation=label, product=product))
    return pd.DataFrame(rows), pd.concat(paths, ignore_index=True)


def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    basis = load_basis("basis_2022")
    book = load_book()

    # §8.1 simulation (the only step that sees the truth)
    experience = simulate(book, basis, load_truth())
    experience.to_parquet(PROCESSED / "actual_experience.parquet", index=False)

    # §8.2–8.4 experience study and assumption review (no truth from here on)
    study = ae_study(experience)
    study.to_csv(TABLES / "ae_study.csv", index=False)
    banded = add_bands(experience).assign(t_channel=lambda d: "PY" + (d["t"] + 1).astype(str) + " " + d["channel"])
    by_t_channel = ae_table(banded, "t_channel")
    by_t_channel.to_csv(TABLES / "ae_lapse_policy_year_channel.csv", index=False)
    review = assumption_review(experience)
    write_basis_2025(review)
    basis_2025 = load_basis("basis_2025")
    pd.DataFrame([
        {"assumption": "mortality level (× X)", "old": review["mortality"]["old"], "new": review["mortality"]["new"]},
        {"assumption": "lapse multiplier", "old": review["lapse"]["old"], "new": review["lapse"]["new"]},
        {"assumption": "maintenance expense €", "old": review["maintenance"]["old"], "new": review["maintenance"]["new"]},
    ]).to_csv(TABLES / "assumption_changes.csv", index=False)
    charts.mortality_ae(study, NOTE)
    charts.lapse_ae(by_t_channel, study, NOTE)

    # §9 Solvency II at issue and at 31 Dec 2025 (on both bases)
    issue, issue_paths = solvency_summary(book, basis, Curve.eiopa("2022-12-31"), 0, "2022-12-31 issue")
    in_force = book[in_force_after(book, experience, 2025)].reset_index(drop=True)
    curve_2025 = Curve.eiopa("2025-12-31")
    ye_old, ye_old_paths = solvency_summary(in_force, basis, curve_2025, 3, "2025-12-31 basis_2022")
    ye_new, ye_new_paths = solvency_summary(in_force, basis_2025, curve_2025, 3, "2025-12-31 basis_2025")
    summary = pd.concat([issue, ye_old, ye_new], ignore_index=True)
    summary.to_csv(TABLES / "solvency2_summary.csv", index=False)
    pd.concat([issue_paths, ye_old_paths, ye_new_paths]).to_csv(TABLES / "solvency2_scr_runoff.csv", index=False)
    charts.scr_and_risk_margin(issue, issue_paths, NOTE + " Solvency II at issue, EIOPA curve 31 Dec 2022.")
    print("Phase 2 outputs written to outputs/")


if __name__ == "__main__":
    main()
