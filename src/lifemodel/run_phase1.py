"""Build every Phase 1 real-basis output: rate table, priced book, sensitivities, charts 1–2. Implements SPEC §7."""

from pathlib import Path

from lifemodel import charts
from lifemodel.basis import load_basis
from lifemodel.pricing import premium_from_rate, profit_test, solve_unisex_rate
from lifemodel.portfolio import generate_portfolio, make_policy
from lifemodel.pricing_analysis import apply_rates, margin_by_sa, rate_table, sensitivities, sex_mix_sensitivity
from lifemodel.projection import project

ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / "outputs" / "tables"
PROCESSED = ROOT / "data" / "processed"
NOTE = "Synthetic book, illustrative assumptions. Mortality: CMI 00 × 0.712. Unisex rates priced for 60% male."
REFERENCE = dict(issue_age=35, sex="M", smoker=False)  # reference life for charts 1–2 (the F1 life)


def main():
    basis = load_basis("basis_2022")
    TABLES.mkdir(parents=True, exist_ok=True)

    rates = rate_table(basis)
    rates.to_csv(TABLES / "rate_table.csv", index=False)
    apply_rates(generate_portfolio(), rates, basis).to_csv(PROCESSED / "portfolio.csv", index=False)

    references = {}
    for product in ("LTA", "MP"):
        sa = basis.reference_sa[product]
        rate = solve_unisex_rate(product, REFERENCE["issue_age"], REFERENCE["smoker"], basis)
        references[product] = make_policy(product, REFERENCE["issue_age"], REFERENCE["sex"], REFERENCE["smoker"],
                                          sa, premium_from_rate(rate, sa, basis))
    labels = {"LTA": "Level term, €250k", "MP": "Mortgage protection, €300k loan"}
    ref_note = NOTE + " Reference life: male, 35, non-smoker."
    charts.cashflows_reference({labels[p]: project(pol, basis) for p, pol in references.items()}, ref_note)
    charts.profit_reserve_emergence({labels[p]: profit_test(pol, basis) for p, pol in references.items()}, ref_note)

    by_sa = margin_by_sa("LTA", 35, False, basis)
    by_sa.to_csv(TABLES / "margin_by_sa_lta35ns.csv", index=False)
    charts.margin_by_sa(by_sa, NOTE + " Rates solved at €250k.", basis.policy_fee)

    sensitivities(basis).to_csv(TABLES / "pricing_sensitivities.csv")
    mix = sex_mix_sensitivity(basis)
    mix.to_csv(TABLES / "sex_mix_sensitivity.csv", index=False)
    charts.sex_mix(mix, NOTE, basis.male_share)
    print("Phase 1 outputs written to outputs/")


if __name__ == "__main__":
    main()
