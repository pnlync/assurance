# Phase 3 summary — IFRS 17, analysis of change, core result table

Status: **accepted.** F3 CSM golden values, Monte Carlo RA within tolerance, model points = seriatim, every BE/RA/CSM walk reconciles (checked in the run and in tests), core result table and charts 05, 07, 08 produced. 57 tests pass. Rebuild with `uv run python -m lifemodel.run_phase3` (≈ 35 s; needs phases 1–2).

## Built
| Module | SPEC | Content |
|---|---|---|
| `ifrs17.py` | §10 | cells, G1/G2/G3, Monte Carlo RA (10,000 scenarios, seed 17), CoC comparison, CSM₀/LC₀, coverage units, expected CSM run-off, onerous-premium factor |
| `aoc.py` | §11 | step values S0–S5, BE walk (SII with overhead, IFRS without), RA at four points, CSM with locked-in measures, loss component, P&L |
| `run_phase3.py` | §12 | tables, 2025 counterfactual (no assumption change), repricing, core result table |

**Model points.** Within a (product, sex, smoker, issue age) combination every cash flow is affine in SA, so two model points per combination reproduce each policy's value exactly. A test compares against seriatim values at issue and at duration 3 (relative 1e-10). This makes 10,000 RA scenarios on 50,000 policies take seconds.

## Initial recognition, 1 Jan 2023 (locked-in curve EIOPA 31 Dec 2022; basis without overhead), €m
| Group | Policies | BE | RA (75%) | CSM | Loss comp. |
|---|---|---|---|---|---|
| LTA-G1 onerous | 933 | −0.01 | 0.03 | 0 | 0.02 |
| LTA-G2 | 23,035 | −35.53 | 3.81 | 31.71 | 0 |
| LTA-G3 | 1,254 | −0.14 | 0.06 | 0.08 | 0 |
| MP-G1 onerous | 590 | −0.01 | 0.02 | 0 | 0.02 |
| MP-G2 | 23,781 | −21.89 | 2.92 | 18.97 | 0 |
| MP-G3 | 407 | −0.08 | 0.03 | 0.05 | 0 |
| **Total** | 50,000 | −57.65 | 6.88 | 50.81 | 0.04 |

- Onerous cells are all small-cover (< €150k), young cells: LTA NS 25–34, MP NS 25–34 and 35–44, MP S 25–34. Same cause as the Phase 1 fee finding — the €60 fee does not cover per-policy costs on small premiums.
- RA at 65% / 75% / 85%: €3.9m / €6.9m / €10.8m.
- Cost-of-capital RA (6% × Σ SCR × DF on the IFRS basis): €26.6m, beyond every simulated scenario (implied confidence > 99.99%). The two methods measure different things: the SCR includes mass lapse and a catastrophe shock and is a 99.5% one-year charge held for every future year, while the Monte Carlo RA covers only uncertainty in the mortality, lapse and expense levels. Choosing the method alone would change the RA by a factor of about 4.
- Onerous-premium factor: premiums would have to fall by 19% (factor 0.808) before G2 + G3 have no CSM left.
- Expected CSM release: mortgage protection 46% in five years, level term 31% (coverage units = expected SA in force).

## Roll-forward 2023–25, €m
Solvency II BEL (with overhead):

| | 2023 | 2024 | 2025 |
|---|---|---|---|
| Opening | −49.30 | −71.83 | −52.44 |
| Expected cash flows | −21.53 | +19.53 | +15.78 |
| Unwind | −2.08 | −1.53 | −0.65 |
| Mortality experience | −0.01 | +0.02 | +0.01 |
| Lapse experience | +1.15 | +1.02 | +0.72 |
| Assumption change | 0 | 0 | +6.76 |
| Economic (curve) | −0.06 | +0.36 | −2.30 |
| Closing | −71.83 | −52.44 | −32.12 |

Year 1 "expected cash flows" is negative: commission and acquisition are paid at the start, so the remaining book is worth more afterwards (V₁ more negative than V₀).

IFRS 17 CSM (all groups):

| | 2023 | 2024 | 2025 |
|---|---|---|---|
| Opening | 50.81 | 46.02 | 41.61 |
| Accretion (locked-in) | +1.61 | +1.57 | +1.26 |
| Mortality experience | +0.01 | −0.02 | −0.01 |
| Lapse experience | −1.27 | −1.15 | −0.85 |
| Assumption change | 0 | 0 | −6.99 |
| RA change (future service) | +0.11 | +0.13 | +0.41 |
| To loss component | +0.01 | +0.01 | +0.10 |
| Release to profit | −5.27 | −4.95 | −3.93 |
| Closing | 46.02 | 41.61 | 31.59 |
| Loss component, closing | 0.05 | 0.06 | 0.15 |
| Insurance service result | 6.33 | 3.41 | 2.61 |

- Same lapse variance, two frameworks: in Solvency II the lost future profit hits own funds at once (BEL +€1.15m in 2023); in IFRS 17 it reduces the CSM (−€1.27m) and so lowers profit gradually over the remaining coverage.
- Excess deaths show up as claims A − E in the P&L (−€1.2m in 2023 when deaths were light, then +€1.6m in each of 2024 and 2025): the part of the mortality excess not recognised in the basis keeps appearing as experience losses.
- Interest-rate movements go to finance income/expense, never to the CSM (locked-in accretion).

## Core result table, 31 Dec 2025 (same book and curve; basis_2022 vs basis_2025)
| Metric | basis_2022 | basis_2025 | Change |
|---|---|---|---|
| Premium adequacy (book, premium-weighted) | 100% | 96.6% | −3.4 pts |
| Premium adequacy LTA 35 NS / MP 35 NS / LTA 50 NS | 100% | 96.1% / 94.7% / 97.6% | |
| New-business margin at current rates LTA 35 / MP 35 / LTA 50 | 10.0% | 6.3% / 6.0% / 7.4% | |
| Solvency II BEL | −€38.9m | −€32.1m | +€6.7m (+17%) |
| Life SCR | €39.8m | €37.3m | −6% |
| Risk margin, current / 2027 | €17.9m / €11.7m | €16.5m / €10.8m | −8% / −7% |
| IFRS 17 CSM | €37.7m | €31.6m | −€6.1m (−16%) |
| IFRS 17 loss component | €0.06m | €0.15m | +€0.10m |

**Repricing for 2026** (rate table on basis_2025 vs basis_2022): level term +2.0% to +6.9% (non-smoker mean +4.2%), mortgage protection +3.9% to +8.4% (non-smoker mean +6.3%). Mortgage protection needs more because the lapse increase hurts it more (Phase 1 sensitivity).

Mechanics worth stating: the review lowers SCR and RM because higher lapses and costs leave less future profit to lose in a mass lapse; the loss is the BEL and CSM, not the capital.

## Simplifications (documented, per SPEC)
- RA of a group is its own quantile; total RA is the sum of group RAs (no diversification credit between groups).
- Loss component: no systematic allocation to insurance revenue; favourable changes reverse it first (SPEC §11.3).
- Coverage units undiscounted; the whole RA change is in the insurance service result (para 81 option).

## Open questions
None.
