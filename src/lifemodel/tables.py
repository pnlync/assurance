"""Base mortality tables: q_base(age, duration, sex, smoker). Implements SPEC §3 and §13.3."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FixtureMortality:
    """Golden-test mortality (SPEC §13.3): q_x = base_q × growth^(x − base_age), × female / smoker factors.

    No select effect; capped at 1.
    """

    base_q: float
    base_age: float
    growth: float
    female_factor: float
    smoker_factor: float

    def q(self, age, duration, female, smoker):
        """Base q for arrays of attained age, select duration, female flag and smoker flag. Implements SPEC §13.3."""
        q = self.base_q * self.growth ** (np.asarray(age, dtype=float) - self.base_age)
        q = q * np.where(female, self.female_factor, 1.0) * np.where(smoker, self.smoker_factor, 1.0)
        return np.minimum(q, 1.0)


class Cmi00Mortality:
    """CMI 00 series temporary-assurance tables, five years select. Implements SPEC §3, §6.1.

    q(attained age, duration) uses the select rate for durations 0–4 and the ultimate rate from duration 5.
    Tables: TMN00 / TMS00 / TFN00 / TFS00 (male/female × non-smoker/smoker).
    """

    SELECT_PERIOD = 5

    def __init__(self, csv_path: Path):
        tidy = pd.read_csv(csv_path)
        self.min_age = int(tidy["age"].min())
        self.max_age = int(tidy["age"].max())
        n_ages = self.max_age - self.min_age + 1
        # grid[table index, age − min_age, duration 0…5]; table index = 2·female + smoker
        self.grid = np.full((4, n_ages, self.SELECT_PERIOD + 1), np.nan)
        for i, name in enumerate(("TMN00", "TMS00", "TFN00", "TFS00")):
            t = tidy[tidy["table"] == name]
            self.grid[i, t["age"] - self.min_age, t["duration"]] = t["qx"]

    def q(self, age, duration, female, smoker):
        """Base q for arrays of attained age, select duration, female flag and smoker flag. Implements SPEC §6.1."""
        age = np.asarray(age, dtype=int)
        if age.min() < self.min_age or age.max() > self.max_age:
            raise ValueError(f"Attained age outside the CMI 00 range {self.min_age}–{self.max_age}.")
        table = 2 * np.asarray(female, dtype=int) + np.asarray(smoker, dtype=int)
        dur = np.minimum(np.asarray(duration, dtype=int), self.SELECT_PERIOD)
        table, age, dur = np.broadcast_arrays(table, age, dur)
        q = self.grid[table, age - self.min_age, dur]
        if np.isnan(q).any():
            raise ValueError("No CMI 00 select rate for some age/duration combination.")
        return q
