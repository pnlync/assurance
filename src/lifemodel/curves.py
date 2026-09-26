"""Discount curves. Implements SPEC §2.5."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

CURVES_CSV = Path(__file__).resolve().parents[2] / "data" / "processed" / "curves.csv"


@dataclass(frozen=True)
class Curve:
    """Annually compounded spot curve r(m), m = 1…M, observed at the valuation date (SPEC §2.5)."""

    spot: np.ndarray  # spot[m - 1] = r(m)

    @classmethod
    def flat(cls, rate: float, max_maturity: int = 150) -> "Curve":
        """A flat curve, used for pricing economics and the golden fixture. Implements SPEC §2.5."""
        return cls(np.full(max_maturity, rate, dtype=float))

    @classmethod
    def eiopa(cls, date: str, csv_path: Path = CURVES_CSV) -> "Curve":
        """EIOPA EUR risk-free spot curve without VA observed at `date` (e.g. "2022-12-31"). Implements SPEC §2.5, §3."""
        curves = pd.read_csv(csv_path)
        c = curves[curves["date"] == date].sort_values("maturity")
        if c.empty:
            raise KeyError(f"No curve for {date} in {csv_path}")
        return cls(c["spot"].to_numpy(float))

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

    def forward_from(self, years: int) -> "Curve":
        """The curve seen `years` later with nothing changed: DF_s(m) = DF(m + years) / DF(years). SPEC §2.5, §11.3.

        Used for the locked-in curve L at duration k+1 (v_{k+1+j} = DF_L(k+2+j) / DF_L(k+1+j)).
        """
        if years == 0:
            return self
        m = np.arange(1, len(self.spot) - years + 1)
        df_s = self.df(m + years) / self.df(years)
        return Curve(df_s ** (-1.0 / m) - 1.0)

    def rolled_forward(self) -> "Curve":
        """Curve observed one year earlier, used one year later: DF_f(m) = DF(m+1) / DF(1). Implements SPEC §2.5."""
        m = np.arange(1, len(self.spot))
        df_f = self.df(m + 1) / self.df(1)
        return Curve(df_f ** (-1.0 / m) - 1.0)
