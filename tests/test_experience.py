"""Simulation and experience-study checks (SPEC §8, §13.2)."""

from pathlib import Path

import numpy as np
import pytest

from lifemodel.basis import load_basis
from lifemodel.experience import ae_table, add_bands, assumption_review, credibility
from lifemodel.portfolio import generate_portfolio
from lifemodel.simulate import in_force_after, simulate

NEUTRAL_TRUTH = {"mortality_multiplier": 1.0, "lapse_multiplier": 1.0,
                 "lapse_channel_factor": {"broker": 1.0, "direct": 1.0}, "maintenance_expense_multiplier": 1.0}


@pytest.fixture(scope="module")
def small_book(fixture_basis):
    return generate_portfolio(n=20_000).assign(premium=500.0)


def test_experience_code_never_reads_truth():
    """Guard for SPEC §0 rule 8: the study cannot open truth.yaml or use the simulator's truth loader."""
    import ast
    tree = ast.parse((Path(__file__).parents[1] / "src" / "lifemodel" / "experience.py").read_text())
    strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    names = [n.id for n in ast.walk(tree) if isinstance(n, ast.Name)] + \
            [n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)]
    modules = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any("truth.yaml" in s or s == "truth" for s in strings)
    assert "load_truth" not in names and "true_rates" not in names
    assert "lifemodel.simulate" not in modules


def test_in_force_identity(small_book, fixture_basis):
    exp = simulate(small_book, fixture_basis, NEUTRAL_TRUTH, seed=7)
    for year in (2023, 2024):
        start = (exp["year"] == year).sum()
        e = exp[exp["year"] == year]
        end = (exp["year"] == year + 1).sum()
        assert start == e["died"].sum() + e["lapsed"].sum() + end
    assert in_force_after(small_book, exp, 2025).sum() == len(exp[exp.year == 2025]) - exp[exp.year == 2025][["died", "lapsed"]].sum().sum()
    assert not ((exp["died"] == 1) & (exp["lapsed"] == 1)).any()


def test_ae_self_test(small_book, fixture_basis):
    """Truth = basis: total mortality A/E inside its 95% CI in at least 17 of 20 seeds (SPEC §13.2)."""
    inside = 0
    for seed in range(20):
        row = ae_table(add_bands(simulate(small_book, fixture_basis, NEUTRAL_TRUTH, seed=seed)), "total").iloc[0]
        inside += row["ae_deaths_lo"] <= 1.0 <= row["ae_deaths_hi"]
    assert inside >= 17


def test_credibility():
    assert credibility(1082.41) == pytest.approx(1.0)
    assert credibility(5000) == 1.0
    assert credibility(200) == pytest.approx(np.sqrt(200 / 1082.41))


def test_review_recovers_lapse_truth(small_book, fixture_basis):
    truth = dict(NEUTRAL_TRUTH, lapse_multiplier=1.2)
    review = assumption_review(simulate(small_book, fixture_basis, truth, seed=3), old_basis_name="fixture")
    assert review["lapse"]["z"] == 1.0
    assert review["lapse"]["ci"][0] <= 1.2 <= review["lapse"]["ci"][1]
