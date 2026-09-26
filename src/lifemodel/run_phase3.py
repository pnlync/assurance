"""Build every Phase 3 output: IFRS 17 at issue, roll-forward and AoC 2023–25, core result table, repricing.
Implements SPEC §10, §11, §12. Needs run_phase1 and run_phase2 first."""

from pathlib import Path

import numpy as np
import pandas as pd

from lifemodel import charts
from lifemodel.aoc import ifrs17_year, solvency2_year
from lifemodel.basis import load_basis
from lifemodel.curves import Curve
from lifemodel.ifrs17 import (ModelPoints, coverage_units, csm_expected_runoff, initial_recognition,
                              onerous_premium_factor, scenario_multipliers)
from lifemodel.pricing import pooled_margin, premium_from_rate, solve_unisex_rate
from lifemodel.pricing_analysis import rate_table

ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / "outputs" / "tables"
PROCESSED = ROOT / "data" / "processed"
NOTE = "Synthetic book, simulated 2023–25 experience, illustrative assumptions."
REFERENCE_CELLS = (("LTA", 35, False), ("MP", 35, False), ("LTA", 50, False))


def opening_from(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.set_index("group")[["csm_closing", "lc_closing"]].rename(
        columns={"csm_closing": "csm", "lc_closing": "loss_component"})


def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    b22, b25 = load_basis("basis_2022"), load_basis("basis_2025")
    book = pd.read_csv(PROCESSED / "portfolio.csv")
    experience = pd.read_parquet(PROCESSED / "actual_experience.parquet")
    curves = {y: Curve.eiopa(f"{y}-12-31") for y in (2022, 2023, 2024, 2025)}
    locked_in = curves[2022]

    # §10 initial recognition
    init = initial_recognition(book, b22, locked_in)
    init.cells.to_csv(TABLES / "ifrs17_cells.csv", index=False)
    init.groups.to_csv(TABLES / "ifrs17_groups_initial.csv", index=False)
    factor = onerous_premium_factor(book, b22, locked_in, init)
    pd.DataFrame([{"onerous_premium_factor": factor}]).to_csv(TABLES / "ifrs17_onerous_premium_factor.csv", index=False)

    # Expected CSM release pattern by product (no experience), SPEC §10.7
    ones = np.ones(len(book))
    cu = coverage_units(book, b22, ones, init.policy_group, 0)
    runoffs = []
    for g, row in init.groups.set_index("group").iterrows():
        if row["csm"] > 0:
            runoffs.append(csm_expected_runoff(row["csm"], cu[g].to_numpy(), locked_in).assign(group=g))
    runoff = pd.concat(runoffs)
    runoff["product"] = runoff["group"].str.split("-").str[0]
    by_product = runoff.groupby(["product", "year"])[["opening", "accretion", "release", "closing"]].sum().reset_index()
    by_product.to_csv(TABLES / "ifrs17_expected_csm_release.csv", index=False)
    charts.csm_release(by_product, NOTE + " Expected at issue; coverage units = expected SA in force.")

    # §11 roll-forward 2023–2025
    multipliers = scenario_multipliers()
    mp22, mp25 = ModelPoints(book, b22), ModelPoints(book, b25)
    sii_rows, ifrs_frames = [], []
    opening = init.groups.set_index("group")[["csm", "loss_component"]]
    for year in (2023, 2024, 2025):
        b1, mp1 = (b25, mp25) if year == 2025 else (b22, mp22)
        sii_rows.append(solvency2_year(book, experience, year, b22, b1, curves[year - 1], curves[year]))
        frame = ifrs17_year(book, experience, year, init.policy_group, opening, b22, b1, curves[year - 1],
                            curves[year], locked_in, mp22, mp1, multipliers)
        ifrs_frames.append(frame)
        opening = opening_from(frame)
    sii = pd.DataFrame(sii_rows)
    ifrs = pd.concat(ifrs_frames, ignore_index=True)
    for name, err in (("SII identity", sii["identity_error"]), ("SII walk", sii["walk_error"]),
                      ("BE walk", ifrs["be_walk_error"]), ("RA walk", ifrs["ra_walk_error"]),
                      ("CSM walk", ifrs["csm_walk_error"])):
        scale = max(1.0, float(np.abs(sii["opening"]).max()))
        if np.abs(err).max() > 1e-8 * scale:
            raise AssertionError(f"{name} does not reconcile: max error {np.abs(err).max()}")
    sii.to_csv(TABLES / "aoc_solvency2_bel.csv", index=False)
    ifrs.to_csv(TABLES / "aoc_ifrs17_by_group.csv", index=False)
    ifrs_total = ifrs.drop(columns="group").groupby("year").sum().reset_index()
    ifrs_total.to_csv(TABLES / "aoc_ifrs17_total.csv", index=False)

    # 2025 counterfactual with no assumption change (B1 = B0), for the core result table
    opening_2025 = opening_from(ifrs_frames[1])
    no_change = ifrs17_year(book, experience, 2025, init.policy_group, opening_2025, b22, b22, curves[2024],
                            curves[2025], locked_in, mp22, mp22, multipliers)
    sii_no_change = solvency2_year(book, experience, 2025, b22, b22, curves[2024], curves[2025])

    # §12 core result table and repricing
    old_rates, new_rates = rate_table(b22), rate_table(b25)
    reprice = old_rates[["product", "smoker", "issue_age", "rate_per_1000"]].rename(columns={"rate_per_1000": "rate_2022"})
    reprice["rate_2025"] = new_rates["rate_per_1000"].to_numpy()
    reprice["increase"] = reprice["rate_2025"] / reprice["rate_2022"] - 1
    reprice.to_csv(TABLES / "repricing_2026.csv", index=False)
    keyed = new_rates.set_index(["product", "smoker", "issue_age"])["rate_per_1000"]
    required = keyed.reindex(pd.MultiIndex.from_frame(book[["product", "smoker", "issue_age"]])).to_numpy()
    required_premium = required * book["sa"].to_numpy() / 1000 + b25.policy_fee
    rows = [{"metric": "Premium adequacy, book (premium-weighted)", "basis_2022": 1.0,
             "basis_2025": book["premium"].sum() / required_premium.sum(), "unit": "ratio"}]
    for product, age, smoker in REFERENCE_CELLS:
        sa = b22.reference_sa[product]
        current = premium_from_rate(solve_unisex_rate(product, age, smoker, b22), sa, b22)
        needed = premium_from_rate(solve_unisex_rate(product, age, smoker, b25), sa, b25)
        cell = f"{product} {age} {'S' if smoker else 'NS'}"
        rows.append({"metric": f"Premium adequacy, {cell}", "basis_2022": 1.0, "basis_2025": current / needed,
                     "unit": "ratio"})
        rows.append({"metric": f"New-business margin at current rates, {cell}",
                     "basis_2022": pooled_margin(product, age, smoker, current, b22),
                     "basis_2025": pooled_margin(product, age, smoker, current, b25), "unit": "margin"})
    sii_new = sii.iloc[-1]
    for label, key in (("Solvency II BEL", "closing"), ("Solvency II life SCR", "scr_close"),
                       ("Risk margin (current, 6%)", "rm_close"), ("Risk margin (2027 rules)", "rm2027_close")):
        rows.append({"metric": label, "basis_2022": sii_no_change[key], "basis_2025": sii_new[key], "unit": "EUR"})
    rows.append({"metric": "IFRS 17 CSM", "basis_2022": no_change["csm_closing"].sum(),
                 "basis_2025": ifrs_frames[2]["csm_closing"].sum(), "unit": "EUR"})
    rows.append({"metric": "IFRS 17 loss component", "basis_2022": no_change["lc_closing"].sum(),
                 "basis_2025": ifrs_frames[2]["lc_closing"].sum(), "unit": "EUR"})
    core = pd.DataFrame(rows)
    core["change"] = core["basis_2025"] - core["basis_2022"]
    core.to_csv(TABLES / "core_result_table_2025.csv", index=False)
    charts.assumption_review_impact(core, NOTE + " At 31 Dec 2025: same book, same curve; only the basis differs.")
    charts.aoc_waterfall_2025(sii.iloc[-1], ifrs_total.iloc[-1], NOTE + " Year 2025, EIOPA curves 2024 → 2025.")
    print("Phase 3 outputs written to outputs/")


if __name__ == "__main__":
    main()
