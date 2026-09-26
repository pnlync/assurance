# Phase 1 summary — engine and pricing

Status: **all built and tested except three items that need the owner: market quotes (§7.1), CM1 past paper (§7.5), Excel reconciliation (§13.4).** 38 tests pass. Rebuild all outputs with `uv run python -m lifemodel.run_phase1` (≈ 8 s).

## Order of work (decision)
Phase 0 parsers need the manual downloads in `data/raw/`. The F1/F2 golden tests need only the fixture basis (SPEC §13.3), so the engine and pricing were built first and the parsers will follow when the data arrives. Phase 1 is accepted only once the real-basis items below are also done.

## Built
| Module | SPEC | Content |
|---|---|---|
| `basis.py` | §4 | `Basis` dataclass, yaml loader, reserving basis, level multiplier X |
| `tables.py` | §13.3 | fixture mortality (CMI 00 parser pending) |
| `curves.py` | §2.5 | spot curve, DF, one-year factors, rolled-forward curve |
| `portfolio.py` | §5 | 50,000-policy generator (seed 2023), MP sum-assured schedule |
| `projection.py` | §6 | rates, cash-flow items, backward `value`, forward `project`, forward PV |
| `pricing.py` | §7.2–7.5 | reserves, profit vector/signature, NPV, margin, IRR, payback, rate solver, exam mode |

Assumption files: `assumptions/fixture.yaml`, `assumptions/basis_2022.yaml`.

## Tests — 29 passed
- Golden F1: rate 2.077131, premium 579.2828, NPV 408.1656, IRR 0.302477, payback 4; q, w, ℓ, V, reserves, profit vector at every tabulated t; ℓ_20; IFRS 17 V_0 −856.8743.
- Golden F2: S_0, S_1, S_10, S_19; rate 1.467883; premium 426.9708; V_0 −627.6326.
- Unit/identity: rates in [0, 1] and caps; ℓ non-increasing; V_n = 0; forward PV = V_0 on a non-flat curve (rel 1e-10); zeroised reserves; reserves lower NPV; exam mode = profit test; rolled-forward curve; portfolio rules; full-book valuation < 5 s (≈ 0.02 s).

## Key numbers (fixture basis, F1)
- First-year profit −518.60 (commission + acquisition): new-business strain.
- Reserves zero for t = 1–3, peak 1,359.90 at t = 13 (start of policy year 14), back to 0 at maturity (hump shape).
- NPV 408.17 with reserves vs 547.01 without: the 138.84 difference is the cost of holding reserves earning 3% against an 8% RDR.
- MP premium 426.97 vs LTA 579.28 for the same life: ≈ 26% cheaper because cover runs off.

## Real-basis results (basis_2022: CMI 00 × 0.712, unisex at 60% male)
Outputs: `outputs/tables/` (rate_table, margin_by_sa_lta35ns, pricing_sensitivities, sex_mix_sensitivity), `outputs/charts/` (01, 02, 02b, 02c). Priced book: `data/processed/portfolio.csv`, total annual premium €32.1m; median premium LTA €495, MP €369.

Unisex rates per 1,000 SA (non-smoker / smoker):

| Age | LTA | MP |
|---|---|---|
| 25 | 0.715 / 0.944 | 0.542 / 0.681 |
| 35 | 1.042 / 1.688 | 0.706 / 1.000 |
| 45 | 2.224 / 4.486 | 1.242 / 2.306 |
| 55 | 6.147 / 12.943 | 3.120 / 6.688 |

**Policy fee (chart 02b).** With the €60 fee the LTA age-35 margin is −54% at €50k and breaks even only at about €177k; without a fee it is −190% at €50k. The fee helps but is too small for the per-policy costs (acquisition €250, maintenance €60 + overhead €15 p.a., inflating; commission is also paid on the fee). A fee of about €150 p.a. makes the margin roughly flat across €50k–€1m (7–10%). The basis keeps €60 (§4.1); this is reported as a pricing recommendation, not built in.

**Sensitivities at fixed premium** (pooled margin, reserves held on the unshocked basis):

| Scenario | LTA 35 NS | LTA 50 NS | MP 35 NS |
|---|---|---|---|
| Base | 10.0% | 10.0% | 10.0% |
| Mortality +10% | 6.7% | 5.3% | 7.1% |
| Lapse +20% | 9.8% | 11.4% | 8.7% |
| Lapse −20% | 10.1% | 8.4% | 11.3% |
| Expenses +10% | 6.4% | 8.8% | 5.7% |
| Earned rate −1pp | 9.0% | 6.9% | 9.6% |
| RDR +2pp | 8.8% | 7.6% | 8.1% |

Lapse direction differs by cell: for LTA 50 higher lapses *raise* the margin (later years are loss-making and reserves are released on lapse with no surrender value), while for MP 35 they cut it (lost future profit). Level-term reserves are hump-shaped (peak ≈ €860 at policy year 14 for the reference life); MP reserves are zero throughout because level premiums exceed the falling cost of cover in every future year.

## Still to do for Phase 1 acceptance (owner)
- `data/raw/market_quotes.csv` → §7.1 reasonableness table.
- A CM1 / CT5 past-paper term-assurance profit test with its examiners' report → §7.5 reproduction.
- `excel/single_policy_check.xlsx` for F1 → §13.4 reconciliation.

## Open questions
None.

## Decision — unisex pricing (SPEC 1.3–1.4)
- Irish quote sites have no sex field: since 21 Dec 2012 EU insurers must price unisex (CJEU C-236/09, Test-Achats). Rates are solved on a pooled male/female margin (total NPV ÷ total EPV of premiums, `solve_unisex_rate`); valuation and experience work stay sex-specific. Observed risk characteristic ≠ permitted pricing factor.
- Male share: the unisex price anti-selects towards men, so pricing assumes 60% male (book 55% + prudence), not 50/50. Illustrative judgement.
- Cross-subsidy at the 60% pricing mix (LTA €250k, 20y, 40 NS, €35.31/month): men earn well below 10%, women well above.
- Sex-mix sensitivity (pooled margin at the priced rate), male share 30% / 50% / 60% / 70%: age 30 NS 13.6 / 11.2 / 10.0 / 8.8%; age 50 NS 18.6 / 12.9 / 10.0 / 7.1%. Older ages are more exposed because the male/female mortality gap widens.
- The male and female margins happen to look symmetric around 10% only because their EPVs of premiums differ by under 1% (lapses, not deaths, drive persistency); the calibration is pooled, not a simple average.
- IFRS 17: cells are not split by sex, using the para 20 option (permitted, not required; not by analogy). Onerousness is judged on FCF + RA, not on the pricing margin.
