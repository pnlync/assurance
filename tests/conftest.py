import pytest

from lifemodel.basis import load_basis
from lifemodel.curves import Curve
from lifemodel.portfolio import make_policy
from lifemodel.pricing import premium_from_rate, solve_rate


@pytest.fixture(scope="session")
def fixture_basis():
    return load_basis("fixture")


@pytest.fixture(scope="session")
def flat3():
    return Curve.flat(0.03)


@pytest.fixture(scope="session")
def f1_rate(fixture_basis):
    return solve_rate("LTA", 35, "M", False, fixture_basis)


@pytest.fixture(scope="session")
def f1(fixture_basis, f1_rate):
    """F1: LTA, male, non-smoker, age 35, SA 250,000, priced at the 10% margin (SPEC §13.3)."""
    return make_policy("LTA", 35, "M", False, 250_000, premium_from_rate(f1_rate, 250_000, fixture_basis))


@pytest.fixture(scope="session")
def f2_rate(fixture_basis):
    return solve_rate("MP", 35, "M", False, fixture_basis, sa=250_000)


@pytest.fixture(scope="session")
def f2(fixture_basis, f2_rate):
    """F2: MP, same life, initial SA 250,000, loan rate 4% (SPEC §13.3)."""
    return make_policy("MP", 35, "M", False, 250_000, premium_from_rate(f2_rate, 250_000, fixture_basis))
