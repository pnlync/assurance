"""Parsers for the manual downloads in data/raw/. Implements SPEC §3."""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

CMI00_TABLES = ("TMN00", "TMS00", "TFN00", "TFS00")
CMI00_SELECT_PERIOD = 5  # "five years select": durations 0–4 select, column "Durations 5+" ultimate


def _find_raw(name: str) -> Path:
    """Locate a raw file case-insensitively (downloads may be lower-case)."""
    matches = [p for p in RAW.iterdir() if p.name.lower() == name.lower()]
    if not matches:
        raise FileNotFoundError(f"{name} not found in {RAW}; see data/raw/README.md")
    return matches[0]


def parse_cmi00_table(table: str) -> pd.DataFrame:
    """One CMI 00 table as tidy rows (table, age, duration, qx). Implements SPEC §3.

    The source gives q_[x−t]+t by attained age x (rows) and duration t (columns 0–4, then 5+ ultimate).
    duration = 5 means "5 and over". Select columns are blank at the oldest ages, where only ultimate rates exist.
    """
    raw = pd.read_excel(_find_raw(f"{table}.xls"), header=None)
    header_row = raw.index[raw[0].astype(str).str.strip() == "Age x"][0]
    body = raw.iloc[header_row + 1 :, :7].dropna(subset=[0])
    body.columns = ["age"] + list(range(CMI00_SELECT_PERIOD + 1))
    tidy = body.melt(id_vars="age", var_name="duration", value_name="qx").dropna(subset=["qx"])
    tidy.insert(0, "table", table)
    return tidy.astype({"age": int, "duration": int, "qx": float}).sort_values(["age", "duration"])


def build_cmi00() -> Path:
    """Write data/processed/mortality_cmi00.csv from the four CMI 00 tables. Implements SPEC §3."""
    out = PROCESSED / "mortality_cmi00.csv"
    pd.concat([parse_cmi00_table(t) for t in CMI00_TABLES]).to_csv(out, index=False)
    return out


if __name__ == "__main__":
    print(build_cmi00())
