"""Real-basis pricing outputs: rate table, fee effect, sensitivities, sex mix. Implements SPEC §7.2, §7.4."""

from dataclasses import replace

import numpy as np
import pandas as pd

from lifemodel.basis import Basis
from lifemodel.pricing import pooled_margin, premium_from_rate, solve_unisex_rate

ISSUE_AGES = range(25, 56)
PRODUCTS = ("LTA", "MP")
SA_GRID = (50_000, 75_000, 100_000, 150_000, 200_000, 250_000, 350_000, 500_000, 750_000, 1_000_000)
MALE_SHARE_GRID = (0.30, 0.40, 0.50, 0.60, 0.70)


def rate_table(basis: Basis) -> pd.DataFrame:
    """Unisex rate per 1,000 SA for every (product, smoker, issue age) cell. Implements SPEC §7.2."""
    rows = [
        {"product": product, "smoker": smoker, "issue_age": age,
         "rate_per_1000": solve_unisex_rate(product, age, smoker, basis)}
        for product in PRODUCTS for smoker in (False, True) for age in ISSUE_AGES
    ]
    table = pd.DataFrame(rows)
    table["reference_sa"] = table["product"].map(basis.reference_sa)
    table["reference_premium"] = table["rate_per_1000"] * table["reference_sa"] / 1000 + basis.policy_fee
    return table


def apply_rates(policies: pd.DataFrame, rates: pd.DataFrame, basis: Basis) -> pd.DataFrame:
    """Set each policy's premium = rate(cell) × SA / 1000 + fee. Implements SPEC §5, §7.2."""
    keyed = rates.set_index(["product", "smoker", "issue_age"])["rate_per_1000"]
    idx = pd.MultiIndex.from_frame(policies[["product", "smoker", "issue_age"]])
    rate = keyed.reindex(idx).to_numpy()
    if np.isnan(rate).any():
        raise ValueError("Some policies have no rate-table cell.")
    return policies.assign(premium=rate * policies["sa"].to_numpy() / 1000 + basis.policy_fee)


def margin_by_sa(product, issue_age, smoker, basis: Basis, sa_grid=SA_GRID) -> pd.DataFrame:
    """Pooled margin by SA, with the €60 fee vs a fee-free rate solved at the same reference SA. Implements SPEC §7.4."""
    no_fee = replace(basis, policy_fee=0.0)
    rate_fee = solve_unisex_rate(product, issue_age, smoker, basis)
    rate_nofee = solve_unisex_rate(product, issue_age, smoker, no_fee)
    rows = []
    for sa in sa_grid:
        rows.append({
            "sa": sa,
            "margin_with_fee": pooled_margin(product, issue_age, smoker, premium_from_rate(rate_fee, sa, basis), basis, sa),
            "margin_no_fee": pooled_margin(product, issue_age, smoker, premium_from_rate(rate_nofee, sa, no_fee), no_fee, sa),
        })
    return pd.DataFrame(rows)


def _scale_expenses(basis: Basis, factor: float) -> Basis:
    return replace(basis, acquisition=basis.acquisition * factor, maintenance=basis.maintenance * factor,
                   overhead=basis.overhead * factor, claim_expense=basis.claim_expense * factor)


def sensitivity_bases(basis: Basis) -> dict:
    """Experience scenarios at fixed premium (SPEC §7.4). Reserves stay on the unshocked basis."""
    return {
        "Base": basis,
        "Mortality +10%": replace(basis, mortality_multiplier=basis.mortality_multiplier * 1.10),
        "Mortality -10%": replace(basis, mortality_multiplier=basis.mortality_multiplier * 0.90),
        "Lapse +20%": replace(basis, lapse_multiplier=basis.lapse_multiplier * 1.20),
        "Lapse -20%": replace(basis, lapse_multiplier=basis.lapse_multiplier * 0.80),
        "Expenses +10%": _scale_expenses(basis, 1.10),
        "Earned rate +1pp": replace(basis, earned_rate=basis.earned_rate + 0.01),
        "Earned rate -1pp": replace(basis, earned_rate=basis.earned_rate - 0.01),
        "RDR +2pp": replace(basis, risk_discount_rate=basis.risk_discount_rate + 0.02),
        "RDR -2pp": replace(basis, risk_discount_rate=basis.risk_discount_rate - 0.02),
    }


def sensitivities(basis: Basis, cells=(("LTA", 35, False), ("MP", 35, False), ("LTA", 50, False))) -> pd.DataFrame:
    """Pooled margin at the priced premium under each scenario, for reference cells. Implements SPEC §7.4."""
    rows = []
    for product, age, smoker in cells:
        premium = premium_from_rate(solve_unisex_rate(product, age, smoker, basis), basis.reference_sa[product], basis)
        for name, b in sensitivity_bases(basis).items():
            rows.append({"cell": f"{product} {age} {'S' if smoker else 'NS'}", "scenario": name,
                         "margin": pooled_margin(product, age, smoker, premium, b, reserve_basis=basis)})
    table = pd.DataFrame(rows).pivot(index="scenario", columns="cell", values="margin")
    return table.loc[list(sensitivity_bases(basis))]


def sex_mix_sensitivity(basis: Basis, cells=(("LTA", 30, False), ("LTA", 40, False), ("LTA", 50, False),
                                              ("LTA", 40, True), ("MP", 40, False))) -> pd.DataFrame:
    """Pooled margin of the priced unisex rate at other male shares, and the rate each mix would need. Implements SPEC §7.4."""
    rows = []
    for product, age, smoker in cells:
        sa = basis.reference_sa[product]
        priced = premium_from_rate(solve_unisex_rate(product, age, smoker, basis), sa, basis)
        for m in MALE_SHARE_GRID:
            rows.append({
                "cell": f"{product} {age} {'S' if smoker else 'NS'}", "male_share": m,
                "margin_at_priced_rate": pooled_margin(product, age, smoker, priced, basis, male_share=m),
                "rate_needed": solve_unisex_rate(product, age, smoker, basis, male_share=m),
            })
    return pd.DataFrame(rows)
