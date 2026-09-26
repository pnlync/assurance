"""Parsers for the manual downloads in data/raw/. Implements SPEC §3."""

import io
import re
import zipfile
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


EIOPA_SHEET = "RFR_spot_no_VA"
EIOPA_CURRENCY_COLUMN = "Euro"
EIOPA_DATES = ("2022-12-31", "2023-12-31", "2024-12-31", "2025-12-31")


def _eiopa_workbook(date: str) -> bytes:
    """The Term_Structures workbook for a reference date, read from inside whichever zip in data/raw/ holds it."""
    stamp = date.replace("-", "")
    for zpath in sorted(RAW.glob("*.zip")):
        with zipfile.ZipFile(zpath) as z:
            for name in z.namelist():
                if re.search(rf"EIOPA_RFR_{stamp}_Term_Structures\.xlsx$", name):
                    return z.read(name)
    raise FileNotFoundError(f"No EIOPA Term_Structures workbook for {date} in {RAW}; see data/raw/README.md")


def parse_eiopa_curve(date: str) -> pd.DataFrame:
    """EUR basic risk-free spot curve without VA at one reference date: (date, maturity, spot). Implements SPEC §3.

    Sheet RFR_spot_no_VA: a header row holds the currency names (column "Euro"); column 1 holds the maturity labels
    1, 2, …, 150 below the parameter block (Coupon_freq, LLP, UFR, …), which is skipped.
    """
    sheet = pd.read_excel(io.BytesIO(_eiopa_workbook(date)), sheet_name=EIOPA_SHEET, header=None)
    header_row, euro_col = next(
        (r, c) for r in range(10) for c in range(sheet.shape[1]) if sheet.iat[r, c] == EIOPA_CURRENCY_COLUMN
    )
    label = pd.to_numeric(sheet.iloc[header_row + 1 :, 1], errors="coerce")
    rows = label.dropna().index
    curve = pd.DataFrame(
        {"date": date, "maturity": label[rows].astype(int), "spot": sheet.loc[rows, euro_col].astype(float)}
    )
    if list(curve["maturity"]) != list(range(1, len(curve) + 1)) or len(curve) < 60:
        raise ValueError(f"Unexpected maturity labels in the {date} EIOPA curve.")
    return curve.reset_index(drop=True)


def build_curves() -> Path:
    """Write data/processed/curves.csv for the four year-end dates. Implements SPEC §3."""
    out = PROCESSED / "curves.csv"
    pd.concat([parse_eiopa_curve(d) for d in EIOPA_DATES]).to_csv(out, index=False)
    return out


CSO_FILES = {"M": "ILT2015-2017_TBL1.xlsx", "F": "ILT2015-2017_TBL2.xlsx"}


def parse_cso_ilt17(sex: str) -> pd.DataFrame:
    """CSO Irish Life Table No. 17 (2015–2017) for one sex: (sex, age, qx). Comparison chart only. Implements SPEC §3."""
    raw = pd.read_excel(_find_raw(CSO_FILES[sex]), header=None)
    header_row = raw.index[raw[4].astype(str).str.startswith("qx")][0]
    body = raw.iloc[header_row + 1 :, [0, 4]]
    body.columns = ["age", "qx"]
    body = body[pd.to_numeric(body["age"], errors="coerce").notna()]
    table = pd.DataFrame({"sex": sex, "age": body["age"].astype(int), "qx": body["qx"].astype(float)})
    if table["age"].iloc[0] != 0 or not table["age"].diff().dropna().eq(1).all():
        raise ValueError(f"Unexpected age column in {CSO_FILES[sex]}.")
    return table.reset_index(drop=True)


def build_cso() -> Path:
    """Write data/processed/mortality_cso_ilt17.csv. Implements SPEC §3."""
    out = PROCESSED / "mortality_cso_ilt17.csv"
    pd.concat([parse_cso_ilt17(s) for s in CSO_FILES]).to_csv(out, index=False)
    return out


def build_all() -> list[Path]:
    """Run every parser whose raw inputs are present."""
    return [build_cmi00(), build_curves(), build_cso()]


if __name__ == "__main__":
    for path in build_all():
        print(path)
