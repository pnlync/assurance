"""Excel functions missing from pycel, used only to evaluate the reconciliation workbook in tests."""

import numpy as np
from scipy.optimize import brentq


def irr(values, guess=None):
    """Excel IRR: r with Σ v_k / (1 + r)^k = 0, k = 0, 1, …"""
    flat = np.array([v for row in values for v in row], dtype=float)
    k = np.arange(len(flat))
    return brentq(lambda r: float(flat @ (1 + r) ** -k.astype(float)), -0.99, 10.0, xtol=1e-14)
