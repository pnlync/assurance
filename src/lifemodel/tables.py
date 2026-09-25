"""Base mortality tables: q_base(age, duration, sex, smoker). Implements SPEC §3 and §13.3."""

from dataclasses import dataclass

import numpy as np


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
