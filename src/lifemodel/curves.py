"""Discount curves. Implements SPEC §2.5."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Curve:
    """Annually compounded spot curve r(m), m = 1…M, observed at the valuation date (SPEC §2.5)."""

    spot: np.ndarray  # spot[m - 1] = r(m)

    @classmethod
    def flat(cls, rate: float, max_maturity: int = 150) -> "Curve":
        """A flat curve, used for pricing economics and the golden fixture. Implements SPEC §2.5."""
        return cls(np.full(max_maturity, rate, dtype=float))

    def df(self, m):
        """DF(m) = (1 + r(m))^(−m), DF(0) = 1. Implements SPEC §2.5."""
        m = np.asarray(m)
        r = np.concatenate([[0.0], self.spot])[m]
        return (1.0 + r) ** (-m.astype(float))

    def one_year_factors(self, n_years: int) -> np.ndarray:
        """v_j = DF(j+1) / DF(j) for j = 0 … n_years−1, measured from the valuation date. Implements SPEC §2.5."""
        m = np.arange(n_years + 1)
        dfs = self.df(m)
        return dfs[1:] / dfs[:-1]

    def rolled_forward(self) -> "Curve":
        """Curve observed one year earlier, used one year later: DF_f(m) = DF(m+1) / DF(1). Implements SPEC §2.5."""
        m = np.arange(1, len(self.spot))
        df_f = self.df(m + 1) / self.df(1)
        return Curve(df_f ** (-1.0 / m) - 1.0)
