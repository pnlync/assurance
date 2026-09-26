# Raw data (manual downloads, SPEC §3)

Not committed. Save each file into this folder with the name shown (case does not matter).

- [x] **CMI 00 series** — `TMN00.xls`, `TMS00.xls`, `TFN00.xls`, `TFS00.xls`
      https://www.actuaries.org.uk/learn-and-develop/continuous-mortality-investigation/cmi-mortality-and-morbidity-tables/00-series-tables
- [ ] **CSO Irish Life Tables No. 17** — only Table 1 (male) and Table 2 (female); keep the CSO file names
      `ILT2015-2017_TBL1.xlsx`, `ILT2015-2017_TBL2.xlsx` — the "(XLS 26KB)" links under each table on
      https://www.cso.ie/en/releasesandpublications/er/ilt/irishlifetablesno172015-2017/
- [ ] **EIOPA risk-free rates** — the four monthly zip files, saved as downloaded (no need to unzip):

  | Reference date | Where on the EIOPA page | File |
  |---|---|---|
  | 31 Dec 2022 | "Monthly Technical information 2023" → December 2022 | `December 2022.zip` |
  | 31 Dec 2023 | "Monthly Technical information 2024" → December 2023 | `EIOPA_RFR_20231231.zip` |
  | 31 Dec 2024 | "Monthly Technical information 2025" → December 2024 | `EIOPA_RFR_20241231.zip` |
  | 31 Dec 2025 | "Monthly Technical information 2026" → December 2025 | `EIOPA_RFR_20251231.zip` |

  https://www.eiopa.europa.eu/tools-and-data/risk-free-interest-rate-term-structures_en
- [ ] **`market_quotes.csv`** — Irish comparison-site quotes (e.g. bonkers.ie, or a broker site); columns:
      `age, sex, smoker, sa, term, monthly_low, monthly_high, source, date`
      Suggested rows: ages 30 / 40 / 50 × smoker yes/no, male, SA 250000, term 20 (6 rows; add female rows if easy).
