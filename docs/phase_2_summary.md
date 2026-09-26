# Phase 2 summary — experience study and Solvency II

Status: **accepted.** In-force identity, A/E self-test (≥17/20 seeds), truth guard, `basis_2025.yaml` written with reasons, F1/F2/F3 Solvency II golden values and the RM identity all pass (51 tests). Rebuild with `uv run python -m lifemodel.run_phase2` (≈ 3 s; needs `run_phase1` first).

## Built
| Module | SPEC | Content |
|---|---|---|
| `simulate.py` | §8.1 | Bernoulli deaths then lapses from `truth.yaml` (seed 2025); the only reader of the truth |
| `experience.py` | §8.2–8.4 | A/E by count, amount and lapse for 9 cuts with 95% CIs; credibility; review → `basis_2025.yaml` |
| `solvency2.py` | §9 | six stress losses per policy per future year, SCR run-off with Art. 136 correlation, BEL, RM current / 2027 + identity |
| `run_phase2.py` | §8.5, §9.6 | tables in `outputs/tables/`, charts 03, 04, 06 |

Guard for SPEC §0 rule 8: a test parses `experience.py` and fails if it opens `truth.yaml`, calls the truth loader or imports the simulator.

## Experience 2023–25 (50,000 policies issued 1 Jan 2023)
| Year | In force at start | Deaths | Lapses |
|---|---|---|---|
| 2023 | 50,000 | 12 | 3,689 |
| 2024 | 46,299 | 29 | 4,932 |
| 2025 | 41,338 | 34 | 4,003 |

- **Mortality**: 75 deaths vs 65.0 expected, A/E 115.4%, 95% CI 89%–141%. Credibility Z = 0.263, so the level moves from 1.000 to 1.040 × X. The truth is 110%: the study points the right way but cannot confirm it. The unrecognised excess will keep appearing as experience losses in the analysis of change. At about 25–35 deaths a year, full credibility (1,082 deaths) would take decades — why insurers lean on reinsurer and industry data.
- Year-1 deaths are low (A/E 69%) — select effect plus noise with 12 deaths.
- **Lapse**: 12,624 vs 10,468 expected, A/E 120.6% (CI 118.5%–122.7%), Z = 1 → multiplier 1.206, applied to all future durations (documented judgement: only policy years 1–3 observed).
- **Channel**: broker 132.8%, direct 92.7%. Not built into the basis; pricing recommendation (commission clawback / channel pricing).
- **Maintenance expense**: 106% of assumed → €60 → €63.60 (company accounts; no credibility weighting).

## Solvency II
At issue (EIOPA 31 Dec 2022, basis_2022 with overhead), €m:

| | BEL | Life SCR | RM current | RM 2027 | RM cut | Day-1 own funds (current → 2027) |
|---|---|---|---|---|---|---|
| Level term | −31.5 | 28.1 | 16.0 | 10.0 | 37.5% | 15.5 → 21.5 |
| Mortgage protection | −17.8 | 21.6 | 10.4 | 6.7 | 35.2% | 7.4 → 11.1 |
| Total | −49.3 | 49.4 | 25.6 | 16.3 | 36.3% | 23.7 → 33.0 |

- SCR by risk (total): mortality 24.2, lapse 20.0 (mass lapse binds), expense 9.0, catastrophe 22.2; diversification −26.0.
- SCR rises in year 1 (LTA 28.1 → 30.4): acquisition costs are sunk, so the future profit exposed to mass lapse is at its largest.
- RM ratio 0.637 equals the identity value; mortgage protection gains less because its SCR runs off faster.
- RM sensitivity to ±100bp (SCR path fixed): current −6.3% / +7.0%, 2027 −5.5% / +6.0% — the new formula is less rate-sensitive.

At 31 Dec 2025 (37,301 policies in force, EIOPA 31 Dec 2025), €m:

| | BEL | Life SCR | RM current | RM 2027 |
|---|---|---|---|---|
| basis_2022 | −38.9 | 39.8 | 17.9 | 11.7 |
| basis_2025 | −32.1 | 37.3 | 16.5 | 10.8 |

The assumption review raises BEL by €6.7m (less future profit, mainly higher lapses and expenses) and lowers SCR and RM (less future profit to lose in a mass lapse).

## Open questions
None.
