# Phase 0 summary — setup and parsers

Status: **accepted** (parsers produce tidy CSVs; fixture unit tests pass). 35 tests pass.

## Built
- Repo, uv environment (Python 3.12), layout per SPEC Appendix A.
- `parsers.py` → `data/processed/`:
  - `mortality_cmi00.csv` — TMN00/TMS00/TFN00/TFS00, attained ages 17–120, select durations 0–4 plus ultimate (duration 5 = "5+"); select rates exist up to age 90, so select rates are used for the whole book (ages 25–74). Recorded for the assumption register.
  - `curves.csv` — EIOPA EUR spot without VA, maturities 1–150, at 2022-12-31, 2023-12-31, 2024-12-31, 2025-12-31 (read directly from the downloaded zips).
  - `mortality_cso_ilt17.csv` — CSO Irish Life Tables No. 17, ages 0–105, male and female (comparison only).
- `Cmi00Mortality` table class and `Curve.eiopa(date)` loader.

## Key numbers
EUR spot (no VA):

| Maturity | 2022-12-31 | 2023-12-31 | 2024-12-31 | 2025-12-31 |
|---|---|---|---|---|
| 1 | 3.18% | 3.36% | 2.24% | 2.08% |
| 10 | 3.09% | 2.39% | 2.27% | 2.86% |
| 20 | 2.77% | 2.41% | 2.26% | 3.21% |

Insured (CMI 00 ultimate × X = 0.712, non-smoker) ÷ Irish population (CSO ILT17): about 0.42–0.52 for males and 0.51–0.68 for females at ages 30–60.

## Open questions
None. `market_quotes.csv` is still to come (needed for §7.1 only).
