"""Assumption bases loaded from assumptions/*.yaml. Implements SPEC §4."""

from dataclasses import dataclass, replace
from pathlib import Path

import yaml

from lifemodel.tables import Cmi00Mortality, FixtureMortality

ASSUMPTIONS_DIR = Path(__file__).resolve().parents[2] / "assumptions"
PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"


@dataclass(frozen=True)
class Basis:
    """One assumption basis (SPEC §4.1 structure). Shocked or derived bases are made with `replace`."""

    name: str
    mortality_table: object          # has .q(age, duration, female, smoker)
    mortality_multiplier: float
    lapse_by_policy_year: tuple      # policy years 1, 2, …; later years use lapse_ultimate
    lapse_ultimate: float
    lapse_multiplier: float
    acquisition: float
    maintenance: float
    overhead: float
    claim_expense: float
    inflation: float
    commission_first_year: float
    policy_fee: float
    # Reserving basis (SPEC §4.2)
    reserve_mortality_multiplier: float
    reserve_include_lapses: bool
    reserve_interest: float
    # Pricing economics (SPEC §4.3)
    earned_rate: float
    risk_discount_rate: float
    target_margin: float
    unisex_female_share: float
    reference_sa: dict

    def reserving_basis(self) -> "Basis":
        """Reserving basis: mortality × 110%, no lapses; expenses unchanged. Implements SPEC §4.2."""
        return replace(
            self,
            name=f"{self.name}_reserving",
            mortality_multiplier=self.mortality_multiplier * self.reserve_mortality_multiplier,
            lapse_multiplier=self.lapse_multiplier if self.reserve_include_lapses else 0.0,
        )


def _mortality_from_config(cfg: dict):
    """Build the base table and level multiplier X from the yaml mortality block. Implements SPEC §4.1, §13.3."""
    if cfg["table"] == "fixture":
        table = FixtureMortality(
            base_q=cfg["base_q"],
            base_age=cfg["base_age"],
            growth=cfg["growth"],
            female_factor=cfg["female_factor"],
            smoker_factor=cfg["smoker_factor"],
        )
        return table, cfg["multiplier"]
    if cfg["table"] == "cmi00":
        table = Cmi00Mortality(PROCESSED_DIR / "mortality_cmi00.csv")
        x = level_multiplier(cfg["improvement_rate"], cfg["table_centre_year"], cfg["issue_year"])
        return table, x
    raise ValueError(f"Unknown mortality table {cfg['table']!r}")


def level_multiplier(improvement_rate: float, table_centre_year: float, issue_year: float) -> float:
    """X = (1 − r)^(issue_year − table_centre_year). Implements SPEC §4.1."""
    return (1.0 - improvement_rate) ** (issue_year - table_centre_year)


def load_basis(name: str) -> Basis:
    """Load assumptions/<name>.yaml into a Basis. Implements SPEC §4."""
    cfg = yaml.safe_load((ASSUMPTIONS_DIR / f"{name}.yaml").read_text())
    table, x = _mortality_from_config(cfg["mortality"])
    exp = cfg["expenses"]
    return Basis(
        name=cfg["name"],
        mortality_table=table,
        mortality_multiplier=x,
        lapse_by_policy_year=tuple(cfg["lapse"]["by_policy_year"]),
        lapse_ultimate=cfg["lapse"]["ultimate"],
        lapse_multiplier=cfg["lapse"]["multiplier"],
        acquisition=exp["acquisition"],
        maintenance=exp["maintenance"],
        overhead=exp["overhead"],
        claim_expense=exp["claim"],
        inflation=exp["inflation"],
        commission_first_year=cfg["commission"]["first_year"],
        policy_fee=cfg["premium"]["policy_fee"],
        reserve_mortality_multiplier=cfg["reserving"]["mortality_multiplier"],
        reserve_include_lapses=cfg["reserving"]["include_lapses"],
        reserve_interest=cfg["reserving"]["interest"],
        earned_rate=cfg["pricing"]["earned_rate"],
        risk_discount_rate=cfg["pricing"]["risk_discount_rate"],
        target_margin=cfg["pricing"]["target_margin"],
        unisex_female_share=cfg["pricing"]["unisex_female_share"],
        reference_sa=dict(cfg["pricing"]["reference_sa"]),
    )
