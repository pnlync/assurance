# Life Protection Model — Build Specification

Version 1.4 · 26 Sep 2026 · Owner: Tom Zhang
Changes in 1.4: pricing male share 60% with anti-selection rationale and a mix sensitivity (§4.3, §7.4); book 55% male (§5); IFRS 17 para 20 wording (§10.1). Changes in 1.3: unisex pricing (EU gender directive, Test-Achats) in §4.3, §7.1, §7.2; IFRS 17 cells not split by sex (para 20) in §10.1. Changes in 1.2: raw file names in §3 match the actual downloads. Changes in 1.1: mortality level X set by documented judgement, market quotes used only as a reasonableness check (§4.1, §7.1); IFRS 17 portfolios split into LTA and MP (§10.1); Python 3.12 (§14).
Audience: the AI coding agent that implements the project, and the owner who reviews it.
Companion: the owner's Chinese guide ("Life Protection Project Guide") explains the concepts; this file defines exactly what to build.

---

## 0. Rules for the agent (read first)

1. Follow the conventions in §2 exactly. If anything here is ambiguous, contradictory or looks wrong, **stop and ask the owner**. Do not guess.
2. **Never edit the golden values in §13.3 or the tests that check them.** If a golden test fails, the implementation is wrong until proven otherwise. Report the discrepancy and your diagnosis.
3. Do not invent regulatory or accounting parameters. Every Solvency II / IFRS 17 parameter used in code must appear in §4 with its source.
4. All assumptions live in `assumptions/*.yaml`. No magic numbers in `src/` other than constants defined in this spec.
5. Every public function has a docstring that cites the spec section it implements, e.g. `"""Implements SPEC §6.3."""`.
6. Prefer readable, explicit code over clever code. The owner must be able to explain every line in an interview. Vectorise with numpy, but keep formulas recognisable.
7. Build phase by phase (§14). Do not start a phase until the previous phase's acceptance criteria pass.
8. The experience-study code (§8.2–8.4) must **never** read `truth.yaml`. Only the simulator (§8.1) may.
9. README, report and charts must only describe what is implemented and tested.
10. After each phase, write a short `docs/phase_N_summary.md`: what was built, test results, key numbers, open questions.

---

## 1. Purpose and scope

**Business question.** How should an Irish life insurer price a term-assurance book, monitor emerging mortality and lapse experience, and translate assumption changes into profitability, IFRS 17 earnings and Solvency II capital?

**Story.** 50,000 synthetic protection policies (level term assurance "LTA" and mortgage protection "MP"), all issued on 1 Jan 2023, priced on a best-estimate basis at end-2022. Three years of experience (2023–2025) are simulated from a hidden "truth" basis. At 31 Dec 2025 the insurer runs an experience study and updates its assumptions. The book is valued under Solvency II and IFRS 17 at issue and at each year-end; each year's movement is explained in an analysis of change; the 2027 Solvency II risk-margin reform is quantified; 2026 new-business premiums are re-priced.

**In scope.** Seriatim annual projection; pricing and profit testing with reserves; experience simulation and A/E study with credibility; Solvency II BEL, selected life-underwriting SCR stresses, risk margin (current and 2027 formula); IFRS 17 GMM (grouping, FCF, Monte Carlo RA, CSM, annual roll-forward); analysis of change 2023–2025; validation.

**Out of scope.** See §15.

---

## 2. Conventions

**2.1 Time.** Annual steps. Policy year t (t = 0, …, n−1) runs from time t to time t+1, time measured in years since issue. n = 20 for every policy.

**2.2 Cash-flow timing in policy year t** (policy in force at time t):
- at time t: premium P received; commission comm_t and expenses exp_t paid;
- during the year: death with probability q_t; claim S_t plus claim expense CE_t paid at time t+1;
- at time t+1: survivors lapse with probability w_t; no surrender value; w_{n−1} = 0.

**2.3 In-force probability.** ℓ_0 = 1; ℓ_{t+1} = ℓ_t (1 − q_t)(1 − w_t).

**2.4 Value** (sign: positive = liability, negative = expected future profit). V_t is the value at time t, before the time-t cash flows, of all future cash flows of one policy in force at t:

```
V_t = −P + comm_t + exp_t + v_t · [ q_t·(S_t + CE_t) + (1 − q_t)·(1 − w_t)·V_{t+1} ],   V_n = 0
```

v_t = one-year discount factor from t to t+1 on the valuation curve (§2.5). The value of a set of policies = Σ (in-force weight × V).

**2.5 Curves.** Spot rates r(m), annually compounded, maturities m = 1…M. DF(m) = (1 + r(m))^(−m), DF(0) = 1.
- A curve observed at date d discounts cash flows at d + m with DF(m).
- For a policy at duration k valued at date d with curve C: v_{k+j} = DF_C(j+1) / DF_C(j), j = 0, 1, …
- Rolled-forward curve (curve C observed at d0, used at d0 + 1 year as if nothing changed): DF_Cf(m) = DF_C(m+1) / DF_C(1).
- Locked-in curve L = EIOPA curve at 31 Dec 2022, observed at issue: v_t = DF_L(t+1) / DF_L(t) for policy year t.
- Pricing economics (§4.3) use flat rates.

**2.6 Units.** EUR. Rates are decimals. q and w are annual probabilities per 1 (not per 1,000). Mortality multipliers apply to q and the result is capped at 1. Lapse multipliers apply to w and the result is capped at 1.

**2.7 Ages.** x = age last birthday at issue; attained age in policy year t = x + t; select duration = t.

**2.8 Expense inflation.** Index for policy year t = (1 + infl)^t (t = 0 in the first policy year). The claim expense for a death in policy year t uses the policy-year-t index.

**2.9 Rounding.** Never round inside calculations. Round for display only.

**2.10 Dates.** Issue 2023-01-01 (valuation "at issue" uses the 2022-12-31 curve). Year-end valuations: 2023-12-31, 2024-12-31, 2025-12-31. A policy's duration at 31 Dec y is k = y − 2022 (completed policy years).

---

## 3. Data inputs

The owner downloads these manually into `data/raw/`. The agent writes the parsers.

| File | Source | Used for |
|---|---|---|
| `TMN00.xls`, `TMS00.xls`, `TFN00.xls`, `TFS00.xls` | IFoA, CMI "00" series tables (temporary assurances; male/female × non-smoker/smoker) | base mortality |
| `ILT2015-2017_TBL1.xlsx`, `ILT2015-2017_TBL2.xlsx` | CSO Irish Life Tables No. 17 (2015–2017), Tables 1 (male) and 2 (female) | comparison chart only |
| `EIOPA_RFR_20221231.zip`, `EIOPA_RFR_20231231.zip`, `EIOPA_RFR_20241231.zip`, `EIOPA_RFR_20251231.zip` | EIOPA monthly risk-free rate term structures (zips as downloaded; parser reads the Term_Structures workbook inside) | discount curves |
| `market_quotes.csv` | owner collects from Irish comparison websites | premium reasonableness check (§7.1) |

Parsing:
- CMI 00: store a tidy `data/processed/mortality_cmi00.csv` (columns: table, age, duration, qx). If a table provides select rates (durations 0…s−1), use them by duration and the ultimate rate from duration s; otherwise use the ultimate rate for all durations. Record which in the assumption register.
- EIOPA: use the basic risk-free spot curve **without** volatility adjustment for EUR (sheet commonly named `RFR_spot_no_VA`, column `Euro`), maturities 1–60 at least. Store `data/processed/curves.csv` (date, maturity, spot).
- `market_quotes.csv` columns: age, sex, smoker, sa, term, monthly_low, monthly_high, source, date. Irish quotes are unisex, so sex = U.

---

## 4. Assumptions (`assumptions/*.yaml`)

**4.1 Best-estimate basis `basis_2022.yaml`** — used for pricing, Solvency II and (without overhead) IFRS 17, until the review at 31 Dec 2025.
- Mortality: CMI 00 table by sex × smoker × level multiplier X = (1 − r)^(2023 − 2000.5), stored in the yaml as its inputs, not as a fitted number:
  - 2000.5 = centre of the 1999–2002 investigation period underlying the CMI 00 series;
  - r = 1.5% p.a. = illustrative average mortality improvement from then to issue (judgement; covers UK/Irish improvement over the period, insured-vs-CMI-population differences are not separately modelled). Gives X ≈ 0.712.
  - Status in the assumption register: external base table + documented judgement, not calibrated. Market quotes do not set X (§7.1).
- Lapse by policy year 1, 2, 3, 4, 5: 6%, 9%, 8%, 7%, 6%; 5% thereafter; 0 in the final year. Same for both products and channels.
- Expenses: acquisition 250 at t = 0; maintenance 60 p.a. at every t; overhead 15 p.a. at every t (non-attributable); claim expense 250 per death; inflation 2.5% p.a.
- Commission: 100% of the annual premium at t = 0; nothing thereafter.
- Premium: P = rate × SA / 1000 + fee, fee = 60 p.a.

**4.2 Reserving basis** (profit test only): mortality 110% of the best-estimate basis; no lapses; interest 2.5% flat; expenses as §4.1 (including overhead); reserves floored at 0 ("zeroised"); no reserve held at t = 0.

**4.3 Pricing economics:** earned rate i = 3.0% flat; risk discount rate RDR = 8.0% flat; target profit margin 10%.

**Unisex pricing.** Since 21 Dec 2012 EU insurers may not use sex as a pricing factor (CJEU case C-236/09 Test-Achats; Directive 2004/113/EC Art. 5(2) invalid). Premium rates are therefore unisex; valuation, reserving, Solvency II, IFRS 17 and the experience study still use sex-specific mortality because that is the actual risk. Pricing assumes a male share of new business of **60%** (`pricing.male_share`). Rationale: under a unisex price men get cover below their risk cost and women above it, so the mix anti-selects towards men; 60% = expected mix of the book (55% male, §5) plus a prudence margin. Illustrative judgement — no Irish market data on sex mix; tested in §7.4.
The policy data keep the observed `sex` (M/F): the observed risk characteristic is not the same thing as a permitted pricing factor.

**4.4 IFRS 17 basis:** §4.1 excluding overhead (only directly attributable expenses). Discount curve: EIOPA RFR without VA, illiquidity premium 0. Locked-in curve L = 2022-12-31. RA per §10.3. Coverage units per §10.4. No OCI option (all insurance finance income/expense in P&L).

**4.5 Solvency II parameters** (Delegated Regulation (EU) 2015/35; risk-margin amendment Delegated Regulation (EU) 2026/269, applying from 30 Jan 2027):
- Mortality: q × 1.15, permanent (Art. 137).
- Lapse (Art. 142): max of up (w × 1.5, capped at 1), down (w − min(0.5·w, 0.20)), mass (40% of policies discontinue immediately). Up and mass apply only to policies whose lapse would increase technical provisions (V < 0); down only to policies whose lapse would decrease them (V > 0).
- Expense (Art. 140): all expense items × 1.10 and expense inflation + 0.01. Commission is not shocked.
- Catastrophe (Art. 143): q + 0.0015 for the next 12 months.
- Correlation (Art. 136), order (mortality, lapse, expense, cat):
  ```
  [[1.00, 0.00, 0.25, 0.25],
   [0.00, 1.00, 0.50, 0.25],
   [0.25, 0.50, 1.00, 0.25],
   [0.25, 0.25, 0.25, 1.00]]
  ```
- Risk margin, current: RM = 6% × Σ_{t≥0} SCR(t) / (1 + r(t+1))^(t+1).
- Risk margin, 2027: RM = 4.75% × Σ_{t≥0} max(0.96^t, 0.5) × SCR(t) / (1 + r(t+1))^(t+1).
- SCR used for the risk margin = life-underwriting SCR only (operational, market and counterparty risk out of scope; document as a limitation).
- Basis: §4.1 including overhead; curve = EIOPA RFR without VA at the valuation date.

**4.6 Truth basis `truth.yaml`** (simulator only):
- Mortality: 110% of the best-estimate basis.
- Lapse: 120% of the best-estimate basis × channel factor (broker 1.10, direct 0.767), capped at 1.
- Maintenance expense: 106% of basis (applied to actual expenses, §8.1).

**4.7 Credibility:** limited fluctuation. n_full = (1.645 / 0.05)² = 1082.41 claims. Z = min(1, sqrt(A / n_full)), A = actual count.

**4.8 Updated basis `basis_2025.yaml`:** generated by §8.4. Never hand-edited.

---

## 5. Portfolio generator (`src/lifemodel/portfolio.py`)

N = 50,000, seed 2023. Columns:

| Column | Rule |
|---|---|
| policy_id | TL000001 … TL050000 |
| product | LTA / MP, 50% each |
| issue_age | integer, uniform 25–55 inclusive |
| sex | M 55% / F 45% (expected anti-selected mix under unisex pricing, §4.3) |
| smoker | True with probability 20% |
| channel | broker 70%, direct 30% |
| sa | LTA: lognormal, median 250,000, σ 0.5, clipped to [50,000, 1,000,000]; MP (initial loan): lognormal, median 300,000, σ 0.4, clipped to [100,000, 800,000]; both rounded to the nearest 1,000 |
| term | 20 |
| loan_rate | 0.04 for MP; empty for LTA |
| issue_date | 2023-01-01 |
| premium | from the rate table (§7.2) |

Sum assured schedule: LTA S_t = SA. MP S_t = SA × (1 − v^(n−t)) / (1 − v^n), v = 1 / (1 + loan_rate).

---

## 6. Projection engine (`src/lifemodel/projection.py`)

6.1 **Rates.** q_t = min(1, mort_mult × q_base(x+t, t, sex, smoker)); w_t per the basis × lapse_mult (capped at 1), w_{n−1} = 0.
6.2 **Cash-flow items** per §2.2 and §4, vectorised as arrays of shape (N, n).
6.3 **`value(policies, basis, curve, start_duration, include_overhead)`** → array (N, n+1) of V_t by the backward recursion in §2.4, for t ≥ start_duration.
6.4 **`project(policies, basis)`** → ℓ, expected deaths, expected lapses and every cash-flow item by policy year.
6.5 **Identity.** Forward PV at issue = V_0 (relative tolerance 1e-10).
6.6 **Performance.** Valuing the full book once should take under 5 seconds.

---

## 7. Pricing (`src/lifemodel/pricing.py`)

**7.1 Market reasonableness check** (does not change the basis). For each row of `market_quotes.csv`, compute the model's monthly premium (annual / 12) at the 10% target margin for an LTA of that age, smoker status and SA (unisex rate per §7.2 when sex = U; sex-specific only if a quote row is sex-specific), using X from §4.1. Report model, low, high, mid = (monthly_low + monthly_high) / 2, model / mid, and whether model lies within [low, high]. Also report, as a diagnostic only, the implied X that would minimise Σ ((model − mid) / mid)² on a grid 0.30–1.00 (step 0.01); it is never written to the basis. Rationale (state it in the phase summary): retail premiums also reflect underwriting, commission, expenses, margins and insurer strategy, so a quote cannot identify mortality uniquely. Flag for the owner if any model / mid lies outside 0.5–2.0.

**7.2 Rate table (unisex).** For each cell (product, smoker, issue age 25–55), solve the rate so that the pooled profit margin of a male and a female reference policy, weighted by the male share m, equals 10%: margin = [m·NPV_M + (1 − m)·NPV_F] / [m·EPV_M + (1 − m)·EPV_F] (total NPV over total EPV of premiums — not an average of the two margins) (LTA SA 250,000; MP initial SA 300,000), fee 60. The single-sex solver is kept for the golden fixtures F1/F2 (§13.3), which are sex-specific by construction. Premium of each policy = rate(cell) × SA / 1000 + 60. Use `scipy.optimize.brentq` with xtol 1e-12.

**7.3 Profit test** (per policy, pricing basis including overhead):
- Reserves: _tV = max(0, V^R_t) for t = 1 … n−1, V^R from the reserving basis (§4.2) at 2.5% flat; _0V = _nV = 0.
- Profit vector: Pr_t = (_tV + P − comm_t − exp_t)(1 + i) − q_t (S_t + CE_t) − (1 − q_t)(1 − w_t) · _{t+1}V, for t = 0 … n−1, i = 3%.
- Profit signature: Π_t = ℓ_t · Pr_t, received at time t+1.
- NPV = Σ Π_t (1 + RDR)^−(t+1). EPV premiums = Σ ℓ_t · P · (1 + RDR)^−t. Profit margin = NPV / EPV premiums.
- IRR solves Σ Π_t (1 + IRR)^−(t+1) = 0 (report NaN if no sign change).
- Discounted payback = first time t+1 at which the cumulative discounted Π ≥ 0.
- Also report the NPV with no reserves (all _tV = 0) to show the cost of holding reserves.

**7.4 Outputs.** Rate table CSV; charts for the reference LTA and MP (cash flows by year; reserves; profit signature); profit margin by SA band with and without the fee; sensitivity table (mortality ±10%, lapse ±20%, expenses +10%, earned rate ±1pp, RDR ±2pp) showing the change in margin at fixed premium; **sex-mix sensitivity**: pooled margin of the unisex rates at male share 30%, 40%, 50%, 60%, 70% (chart: male share → margin, reference cells), plus the unisex rate that would be needed at each mix.

**7.5 CM1 check.** Provide `profit_test_exam_mode(...)` that accepts an explicitly supplied basis and reserve vector. The owner supplies one IFoA CM1 / CT5 past-paper term-assurance profit test and its examiners' report answer; reproduce the profit vector, profit signature and NPV.

---

## 8. Experience (`src/lifemodel/simulate.py`, `src/lifemodel/experience.py`)

**8.1 Simulation 2023–2025** (seed 2025, reads `truth.yaml`). For each calendar year y = 2023, 2024, 2025 (policy year t = y − 2023) and each policy in force at the start of y:
1. death ~ Bernoulli(q_true);
2. if alive and t < n−1: lapse ~ Bernoulli(w_true).

Save one row per policy-year to `data/processed/actual_experience.parquet`: policy_id, year, t, attributes, sa_t (= S_t), exposed_death (= 1), died, exposed_lapse (= 1 − died), lapsed, q_basis, w_basis.
Actual maintenance expense per policy in force in year y = 1.06 × 60 × (1.025)^t. Everything else about expenses and claims follows the actual events.
In-force identity per year: in force at start = deaths + lapses + in force at end.

**8.2 A/E study** (basis only; must not read truth):
- Deaths by count: A = Σ died; E = Σ q_basis over exposed_death.
- Deaths by amount: A$ = Σ died × S_t; E$ = Σ q_basis × S_t.
- Lapses: A = Σ lapsed; E = Σ w_basis over exposed_lapse.
- Cuts: total; calendar year; policy year; attained-age band (25–34, 35–44, 45–54, 55+); sex; smoker; product; channel; SA band (<150k, 150–300k, 300–500k, ≥500k).

**8.3 95% confidence intervals.** Count basis: A/E ± 1.96 √A / E. Amount basis: A$/E$ ± 1.96 √(Σ q(1−q) S_t²) / E$.

**8.4 Assumption review at 31 Dec 2025** → write `basis_2025.yaml` with a reasons block:
- Mortality multiplier: new = old × (1 + Z · (A/E_count − 1)), Z = min(1, √(A / 1082.41)), using total deaths 2023–2025.
- Lapse multiplier: new = old × A/E_lapse (total 2023–2025). Z = 1 if lapses ≥ 1082.41. Applied to all future policy years (a judgement: only policy years 1–3 were observed; the owner documents why).
- Maintenance expense: 60 → 63.6 (expense investigation; owner documents).
- Channel: report broker vs direct lapse A/E; do not build it into the basis (pricing recommendation only).

**8.5 Outputs.** A/E tables with CIs; chart of mortality A/E by segment with CIs; chart of lapse A/E by policy year and channel; assumption register diff (old → new, with reasons).

---

## 9. Solvency II (`src/lifemodel/solvency2.py`)

**9.1 BEL** at date d = Σ over actual in-force policies of V_k (k = duration at d), basis §4.5, curve = EIOPA at d.

**9.2 Per-policy stress losses** at each future time t (policy in force at t, shock applied at t), all floored at 0:
- mortality: V^m_t − V_t, basis with q × 1.15;
- lapse up: V^up_t − V_t with w_up = min(1.5w, 1), only if V_t < 0;
- lapse down: V^dn_t − V_t with w_dn = w − min(0.5w, 0.20), only if V_t > 0;
- mass lapse: 0.40 × max(0, −V_t);
- expense: V^e_t − V_t, all expense items × 1.10 and inflation + 0.01;
- catastrophe: v_t × 0.0015 × [(S_t + CE_t) − (1 − w_t) · V_{t+1}].
For permanent shocks, one backward recursion under the shocked basis gives the shocked V_t for every t at once.

**9.3 Portfolio SCR at future time j** (j years after the valuation date): each risk = Σ_i ℓ_i(j) × loss_i(j), with ℓ from the valuation date on the best-estimate basis; lapse = max(Σ up, Σ down, Σ mass); SCR_life(j) = √(xᵀ · Corr · x), x = (mortality, lapse, expense, cat).

**9.4 Risk margin** per §4.5 with DF from the valuation-date curve. Identity check (must hold to 1e-10):
```
RM_new / RM_old = (19/24) · Σ_j π_j · max(0.96^j, 0.5),   π_j = SCR(j)·DF(j+1) / Σ_s SCR(s)·DF(s+1)
```
Assert 0.3958 ≤ RM_new / RM_old ≤ 0.7917.

**9.5 Day-one own funds from new business** = −(BEL + RM) at issue, by product, with RM_old and RM_new.

**9.6 Outputs.** At issue (by product and total) and at 31 Dec 2025 (on basis_2022 and basis_2025): BEL; SCR by component; SCR run-off; RM old/new and ratio; day-one own funds (issue only); RM sensitivity to a ±100bp parallel shift of the curve with the SCR path held fixed.

---

## 10. IFRS 17 (`src/lifemodel/ifrs17.py`)

**10.1 Level of aggregation.** Two portfolios — LTA and MP (different products, managed separately; IFRS 17 para 14) — each with one annual cohort, 2023. Within each portfolio, cells = smoker × issue-age band (25–34, 35–44, 45–55) × SA band (§8.2). Cells are not split by sex. Rationale: IFRS 17 groups by portfolio, annual cohort and profitability (paras 14–19), not by sex; but because unisex pricing leaves men much less profitable than women, a profitability assessment at a finer level could put male contracts into a different (possibly onerous) group. Para 20 permits — it does not require — keeping contracts in the same group when the only reason they would fall into different groups is that law or regulation specifically constrains the entity's practical ability to set a different price for policyholders with different characteristics; it must not be applied by analogy to other items. The model elects this option (an accounting policy choice, disclosed) for sex only; all other characteristics are still split. Report the male/female split of FCF, RA and CSM as a disclosure. Note that onerousness is tested on FCF + RA on the IFRS 17 basis, not on the pricing margin: a male contract with a small positive pricing margin can still be onerous once the RA is deducted. Profitability is assessed per cell (IFRS 17 para 17 allows sets of contracts). Groups are formed within each portfolio (so up to 6 groups: LTA-G1…G3, MP-G1…G3):
- G1 onerous: BE_cell + RA_cell > 0 at initial recognition;
- G2 no significant possibility of becoming onerous: not G1, and BE_cell under the combined stress (q × 1.15 and w × 1.5) + RA_cell < 0;
- G3 remaining.

**10.2 Fulfilment cash flows** at initial recognition per group: BE = Σ V_0 (IFRS basis, curve L) + RA_group.

**10.3 Risk adjustment — Monte Carlo confidence-level approach.**
- 10,000 scenarios, seed 17. z = 2.5758293035489 (99.5% standard normal quantile).
- σ_M = ln(1.15)/z, σ_L = ln(1.5)/z, σ_E = ln(1.10)/z (each risk's 99.5th percentile equals the Solvency II stress).
- Correlated normals Z ~ N(0, Σ), Σ = [[1, 0, 0.25], [0, 1, 0.5], [0.25, 0.5, 1]] (mortality, lapse, expense).
- Scenario multipliers: M = exp(σ_M·Z_M − σ_M²/2), and likewise L and E (mean-one lognormals).
- In each scenario apply M to every q (cap 1), L to every w (cap 1), E to every attributable expense item (not commission), permanently. Compute each policy's V at the valuation date; aggregate to cells with `np.bincount`; store a (scenarios × cells) matrix.
- RA_group(p) = Q_p(PV_group) − mean(PV_group), with PV_group = Σ of its cells per scenario. Base p = 0.75; also report 0.65 and 0.85.
- Comparison: cost-of-capital RA = 6% × Σ_j SCR_life(j) · DF(j+1) for the group; report its implied confidence level (empirical CDF of the group's PV at mean + RA_CoC).
- Grouped model points are allowed for speed if the agent shows that grouped and seriatim BE agree within 0.1%.

**10.4 Coverage units.** For group g and policy year k: CU_k = Σ S_k over the group's policies in force at the start of year k (actual for past and current years, expected ℓ-weighted for future years). Undiscounted.

**10.5 Initial recognition.** CSM_0 = max(0, −FCF_0); loss component LC_0 = max(0, FCF_0), recognised in P&L.

**10.6 Onerous-premium scenario.** Solve the uniform premium factor f (P → f·P, fee included) at which the total CSM_0 of G2 + G3 becomes 0.

**10.7 Outputs.** Group summary by portfolio (count, PV premiums, BE, RA, CSM_0, LC_0); RA by percentile and the CoC comparison; expected CSM release pattern by product; the onerous-premium factor.

---

## 11. Roll-forward and analysis of change (`src/lifemodel/aoc.py`)

For each year y ∈ {2023, 2024, 2025}: opening date d0 = 31 Dec (y−1), closing date d1 = 31 Dec y, duration at d0 k = y − 2023.
Notation: IF0 = actual in force at d0; IF1 = actual in force at d1; D = deaths in y; B0 = basis at d0; B1 = basis at d1 (= B0, except B1 = basis_2025 when d1 = 2025-12-31); C0, C1 = EIOPA curves at d0, d1; C0f = C0 rolled forward; L = locked-in curve.
For a set of policies P, weights ω and duration j: Val(P, ω, j; B, C) = Σ_{i∈P} ω_i · V_i(j; B, C).

**11.1 Steps** (the same for Solvency II with overhead, and for IFRS 17 BE without overhead):

| Step | Definition |
|---|---|
| S0 opening | Val(IF0, 1, k; B0, C0) |
| X start cash flows | Σ_{IF0} (−P + comm_k + exp_k) — expected net outgo at d0 |
| EC expected claims | Σ_{IF0} q_k (S_k + CE_k) |
| S1 expected | Val(IF0, (1 − q_k)(1 − w_k), k+1; B0, C0f) |
| S2 after mortality experience | Val(IF0 ∖ D, (1 − w_k), k+1; B0, C0f) |
| S3 after lapse experience | Val(IF1, 1, k+1; B0, C0f) |
| S4 after assumption change | Val(IF1, 1, k+1; B1, C0f) |
| S5 closing (economic) | Val(IF1, 1, k+1; B1, C1) |

Walk lines: expected cash flows = −X − EC; unwind = (S0 − X) · (1/v_k − 1) with v_k from C0; mortality = S2 − S1; lapse = S3 − S2; assumptions = S4 − S3; economic = S5 − S4.
Identity (tolerance 1e-8 relative): S1 = (S0 − X) / v_k − EC.
Cash-flow experience of the year (P&L): claims A − E = Σ_{D}(S_k + CE_k) − EC; maintenance A − E = actual − expected.

**11.2 Solvency II extras.** RM and SCR at d0 and d1 (d1 on B1). At 2025-12-31 also report RM under the 2027 formula, and the whole BEL/RM/SCR set on B0 and B1 (feeds §12).

**11.3 IFRS 17 per group.**
- Locked-in measures of future-service changes: repeat S1–S4 with curve L (v_{k+1+j} = DF_L(k+2+j)/DF_L(k+1+j)) → M_mort = S2^L − S1^L, M_lapse = S3^L − S2^L, M_assum = S4^L − S3^L.
- RA (all at d1 with C1): RA0 = RA at d0 (IF0, B0, C0); RA_e = RA(IF0 weighted by (1−q)(1−w), B0, C1); RA_a = RA(IF1, B0, C1); RA1 = RA(IF1, B1, C1).
- RA release (insurance service result) = RA0 − RA_e. The whole change in RA is presented in the insurance service result (IFRS 17 para 81 option). Future-service RA changes: ΔRA_if = RA_a − RA_e; ΔRA_as = RA1 − RA_a.
- CSM: accretion = CSM0 × (DF_L(k)/DF_L(k+1) − 1); adjustment = −(M_mort + M_lapse + M_assum + ΔRA_if + ΔRA_as); CSM_pre = CSM0 + accretion + adjustment. If CSM_pre < 0: loss-component increase = −CSM_pre (P&L loss) and CSM_pre = 0. Release = CSM_pre × CU_k / (CU_k + Σ_{j>k} CU_j), future CUs on IF1 with B1. CSM1 = CSM_pre − release.
- Groups with an existing loss component: subsequent favourable changes first reverse the loss component, then build CSM; unfavourable changes increase it. (Simplification: no systematic allocation of the loss component to revenue; document it.)
- P&L: insurance service result = CSM release + RA release + (E − A) claims + (E − A) maintenance − loss-component increase + reversals. Insurance finance expense = BE unwind + (S5 − S4) + [(S2 − S1) + (S3 − S2) + (S4 − S3) − (M_mort + M_lapse + M_assum)] + CSM accretion.
- Checks: the BE, RA and CSM walks each sum exactly to their closing values.

**11.4 Outputs.** For each year: Solvency II BEL walk; IFRS 17 walk (BE, RA, CSM) by group and total; P&L lines. Waterfall charts for 2025 (BEL and CSM).

---

## 12. Core result table and charts

**Core result table at 2025-12-31** (columns: basis_2022, basis_2025, change):
- premium adequacy = current premium ÷ premium required on basis_2025 (reference cells, and book average weighted by premium);
- profit margin of current premiums on basis_2025 (new business);
- Solvency II BEL, SCR, RM (current and 2027);
- IFRS 17 CSM and loss component (before vs after the assumption change, from the 2025 walk).

**Charts** (`outputs/charts/`):
1. `01_cashflows_reference.png` — premiums, claims, expenses, commission by policy year (reference LTA and MP)
2. `02_profit_reserve_emergence.png` — profit signature and reserves
3. `03_mortality_ae_segments.png` — mortality A/E with 95% CIs
4. `04_lapse_ae_duration_channel.png` — lapse A/E by policy year and channel
5. `05_assumption_review_impact.png` — core result table as a chart
6. `06_scr_and_risk_margin.png` — SCR by component, SCR run-off, RM old vs 2027
7. `07_csm_release_lta_vs_mp.png`
8. `08_aoc_waterfall_2025.png` — BEL (Solvency II) and CSM (IFRS 17)

---

## 13. Tests (`tests/`, pytest)

**13.1 Unit tests.** Rates in [0, 1]; ℓ non-increasing; V_n = 0; lapse caps; MP schedule (S_0 = SA, S_{n−1} > 0); forward PV = V_0; zeroised reserves ≥ 0 and _0V = 0.

**13.2 Identities.** In-force accounting in the simulation; the §11.1 expected-roll identity; every walk sums to its closing value; RM identity and bounds; with no experience and no assumption change, the undiscounted sum of CSM releases = CSM_0 plus total accretion; A/E self-test: simulate with truth = basis for 20 seeds and check that total mortality A/E falls inside its 95% CI in at least 17.

**13.3 Golden fixture.** Fixture basis: q_x = 0.0005 × 1.08^(x − 30), × 0.70 for females, × 1.80 for smokers, no select effect, capped at 1. Everything else per §4.1 (fee 60), §4.2 and §4.3. Valuation curve: flat 3%. Policies are single policies (weight 1). Tolerances: absolute 1e-3 on money amounts, 1e-6 on rates and ratios, unless stated.

*F1 — LTA, male, non-smoker, age 35, SA 250,000, term 20:*
- rate per 1,000 = 2.077131; premium P = 579.2828 (profit margin exactly 10%)
- NPV at 8% = 408.1656; IRR = 0.302477; discounted payback at time 4

| t | q_t | w_t | ℓ_t | V_t (best estimate, incl. overhead) | reserve _tV | profit vector Pr_t |
|---|---|---|---|---|---|---|
| 0 | 0.00073466 | 0.06 | 1.00000000 | −689.2270 | 0.0000 | −518.5997 |
| 1 | 0.00079344 | 0.09 | 0.93930942 | −1307.8794 | 0.0000 | 318.9174 |
| 2 | 0.00085691 | 0.08 | 0.85409336 | −1130.7856 | 0.0000 | 301.0474 |
| 3 | 0.00092547 | 0.07 | 0.78509256 | −939.5680 | 0.0000 | 194.1685 |
| 4 | 0.00099950 | 0.06 | 0.72946037 | −738.2090 | 94.3750 | 47.7670 |
| 5 | 0.00107946 | 0.05 | 0.68500739 | −531.5046 | 330.8408 | 58.5227 |
| 10 | 0.00158608 | 0.05 | 0.52669747 | 400.0117 | 1195.9478 | 112.1288 |
| 15 | 0.00233048 | 0.05 | 0.40377030 | 812.5284 | 1261.6641 | 123.4474 |
| 19 | 0.00317059 | 0.00 | 0.32543335 | 311.4070 | 392.6221 | 83.6515 |

- ℓ_20 = 0.32440200
- V_0 on the IFRS 17 basis (no overhead) = −856.8743
- Solvency II per-policy losses at t = 0: mortality 461.1183; lapse up 105.0972; lapse down 0; mass 275.6908; expense 180.3446; cat 366.2321

*F2 — MP, same life, initial SA 250,000, loan rate 4%:*
- S_0 = 250,000.0000; S_1 = 241,604.5624; S_10 = 149,203.4770; S_19 = 17,687.9208
- rate per 1,000 = 1.467883; premium P = 426.9708 (margin exactly 10%)
- V_0 = −627.6326
- Solvency II per-policy losses at t = 0: mortality 280.8733; lapse up 240.1787; lapse down 0; mass 251.0531; expense 180.3446; cat 366.1397

*F3 — portfolio {F1, F2}, flat 3%:*
- SCR components at t = 0 (mortality, lapse, expense, cat) = (741.9916, 526.7438, 360.6892, 732.3718); lapse sub-risks (up, down, mass) = (345.2758, 0, 526.7438)
- SCR_life(0) = 1554.0120; SCR_life(1) = 1742.0748; SCR_life(10) = 738.8610
- BEL at t = 0 = −1316.8596
- RM_old = 822.3561; RM_new = 526.5710; ratio = 0.64031996 = identity value
- IFRS 17 with a fixed RA of 0.25 × SCR_life(0) = 388.5030 (test only), locked-in curve flat 3%: FCF_0 = −1263.6512; CSM_0 = 1263.6512; CU_0 = 500,000.0000, CU_1 = 461,768.7943, CU_19 = 87,114.5756; CSM release in years 1, 2, 3 = 133.6955, 127.1770, 116.9930; closing CSM after year 20 = 0; total releases = 1607.9465
- Monte Carlo RA (§10.3, IFRS basis, F1 + F2 as one group — a test construct only; in the model they sit in different portfolios): reference values from 200,000 scenarios: RA_65 ≈ 134.5, RA_75 ≈ 233.5, RA_85 ≈ 357.5. With 10,000 scenarios RA_75 must lie within ±5% of 233.5.

**13.4 Excel reconciliation.** The owner's Excel single-policy model of F1 (and later of a real-basis reference policy) must agree with Python to within €0.01 on premium, ℓ_t, V_t, reserves, profit vector, NPV, and the t = 0 Solvency II losses.

---

## 14. Phases and acceptance criteria

| Phase | Build | Accept when |
|---|---|---|
| 0 Setup | repo, environment (Python 3.12, numpy, pandas, scipy, matplotlib, openpyxl, pyarrow, pyyaml, pytest), parsers, fixture basis | parsers produce tidy CSVs; fixture unit tests pass |
| 1 Engine + pricing | §5, §6, §7 | F1/F2 golden values for ℓ, V, reserves, profit vector, premium pass; forward = backward; market reasonableness table; rate table; charts 1–2; Excel reconciliation < €0.01 |
| 2 Experience + Solvency II | §8, §9 | in-force identity; A/E self-test; `basis_2025.yaml` written with reasons; F1/F2/F3 SII golden values and RM identity pass; charts 3, 4, 6 |
| 3 IFRS 17 + AoC | §10, §11, §12 | F3 CSM golden values; MC RA within tolerance; all walks reconcile; core result table; charts 5, 7, 8 |
| 4 Packaging | README, `report/technical_note.pdf`, project web page | every claim traceable to a test or output file |

---

## 15. Out of scope (do not build)

Participating / savings / unit-linked business; asset modelling, market risk and ALM; operational and counterparty-default risk; reinsurance; tax; embedded value; stochastic economic scenarios; full IFRS 17 insurance-revenue presentation and systematic loss-component allocation (optional later); Hong Kong RBC capital calculation (a terminology appendix only, later); machine-learning mortality models; web dashboards.

---

## Appendix A — Recommended repository layout

```
life-protection-model/
├── README.md
├── SPEC.md
├── assumptions/        basis_2022.yaml · basis_2025.yaml · truth.yaml · fixture.yaml
├── data/raw/           (manual downloads, see §3)
├── data/processed/
├── src/lifemodel/      tables.py · portfolio.py · projection.py · pricing.py · simulate.py ·
│                       experience.py · solvency2.py · ifrs17.py · aoc.py · charts.py
├── tests/
├── notebooks/          01_pricing · 02_experience · 03_solvency2 · 04_ifrs17 · 05_aoc (thin: call src)
├── excel/              single_policy_check.xlsx (built by the owner)
├── outputs/tables/ · outputs/charts/
├── docs/               phase summaries · learning log
└── report/             technical_note.pdf
```

## Appendix B — Worked toy example (for teaching and a quick test)

Three-year level term, SA 100,000, premium 180 at the start of each year; q = 0.0010, 0.0011, 0.0012; lapse 10% at the end of years 1 and 2 (none at the end of year 3); expenses 100 at t = 0 (including commission) and 15 at t = 1, 2; no claim expense; discount 3% flat.
- ℓ = 1, 0.8991, 0.8083 (0.80733 at the end)
- PV premiums 474.27; PV expenses 124.52; PV claims 279.08; BEL = −70.67
- mortality × 1.15 → BEL = −28.79, so the mortality stress loss = 41.87; mass lapse = 0.4 × 70.67 = 28.27
- profit by year (no reserves, earned 3%): −17.60, 53.90, 40.37; NPV at 8% = 61.97; margin 13.6%
- with RA = 20: CSM_0 = 50.67; coverage units 100,000 / 89,910 / 80,830; releases (with 3% accretion) 19.28, 17.85, 16.53
