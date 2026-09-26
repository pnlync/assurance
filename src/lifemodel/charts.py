"""Static charts for the README and report (SPEC §12). Palette: validated categorical slots, fixed order."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.ticker import FuncFormatter, PercentFormatter  # noqa: E402

CHART_DIR = Path(__file__).resolve().parents[2] / "outputs" / "charts"

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100")  # blue, orange, aqua, yellow — always in this order

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": TEXT_2, "xtick.color": TEXT_2, "ytick.color": TEXT_2,
    "text.color": TEXT, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "legend.frameon": False, "lines.linewidth": 2, "xtick.major.size": 0, "ytick.major.size": 0,
})

EUR = FuncFormatter(lambda v, _: f"{'−' if v < 0 else ''}€{abs(v):,.0f}")


def _save(fig, name: str, note: str) -> Path:
    fig.text(0.01, 0.01, note, color=TEXT_2, fontsize=8, ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    path = CHART_DIR / name
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def _zero_line(ax):
    ax.axhline(0, color=TEXT_2, linewidth=0.8, zorder=1)


def cashflows_reference(projections: dict, note: str) -> Path:
    """Chart 1: expected premiums, claims, expenses and commission by policy year, per policy issued (SPEC §12)."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    items = (("premiums", "Premiums"), ("claims", "Death claims"), ("expenses", "Expenses"), ("commission", "Commission"))
    for ax, (title, p) in zip(axes, projections.items()):
        year = np.arange(1, p["premiums"].shape[1] + 1)
        for (key, label), color in zip(items, SERIES):
            ax.plot(year, p[key][0], color=color, label=label)
        ax.set_title(title)
        ax.set_xlabel("Policy year")
        ax.yaxis.set_major_formatter(EUR)
        ax.set_xticks([1, 5, 10, 15, 20])
    axes[0].set_ylabel("Expected amount per policy issued")
    axes[0].legend(loc="upper right")
    return _save(fig, "01_cashflows_reference.png", note)


def profit_reserve_emergence(results: dict, note: str) -> Path:
    """Chart 2: profit signature and zeroised reserves, LTA vs MP (SPEC §12)."""
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    width = 0.4
    for i, ((label, pt), color) in enumerate(zip(results.items(), SERIES)):
        year = np.arange(1, len(pt.profit_signature) + 1)
        top.bar(year + (i - 0.5) * width, pt.profit_signature, width=width - 0.04, color=color, label=label, zorder=2)
        bottom.plot(year, pt.reserves[:-1], color=color, label=label)  # reserve at time t = start of policy year t+1
    _zero_line(top)
    top.set_title("Profit signature (profit per policy issued, received at the end of each policy year)")
    top.yaxis.set_major_formatter(EUR)
    top.legend(loc="upper right")
    bottom.set_title("Zeroised reserve per policy in force, start of policy year (mortgage protection: 0 throughout)")
    bottom.yaxis.set_major_formatter(EUR)
    bottom.set_xlabel("Policy year")
    bottom.set_xticks([1, 5, 10, 15, 20])
    return _save(fig, "02_profit_reserve_emergence.png", note)


def margin_by_sa(table, note: str, fee: float) -> Path:
    """Profit margin by sum assured, with and without the policy fee (SPEC §7.4)."""
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.plot(table["sa"], table["margin_with_fee"], color=SERIES[0], marker="o", markersize=5, label=f"Rate + €{fee:.0f} policy fee")
    ax.plot(table["sa"], table["margin_no_fee"], color=SERIES[1], marker="o", markersize=5, label="Rate only, no fee")
    _zero_line(ax)
    ax.axhline(0.10, color=TEXT_2, linewidth=0.8, linestyle="--")
    ax.text(table["sa"].iloc[-1], 0.115, "10% target", color=TEXT_2, fontsize=8, ha="right")
    ax.set_xscale("log")
    ax.set_xticks(table["sa"], [f"€{v / 1e6:.0f}m" if v >= 1e6 else f"€{v // 1000:.0f}k" for v in table["sa"]])
    ax.minorticks_off()
    floor = -1.0
    ax.set_ylim(floor, 0.5)
    off_scale = [f"{m:.0%} at €{sa // 1000:.0f}k".replace("-", "−")
                 for col in ("margin_with_fee", "margin_no_fee")
                 for sa, m in zip(table["sa"], table[col]) if m < floor]
    if off_scale:  # off-scale points are stated, never silently clipped
        ax.text(0.01, 0.95, "Below the axis (no fee): " + ", ".join(off_scale), transform=ax.transAxes,
                color=TEXT_2, fontsize=8)
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Sum assured (log scale)")
    ax.set_ylabel("Profit margin")
    ax.set_title("Level term, age 35 non-smoker: margin by sum assured")
    ax.legend(loc="lower right")
    return _save(fig, "02b_margin_by_sa.png", note)


def sex_mix(table, note: str, priced_share: float) -> Path:
    """Pooled margin of the priced unisex rate against the male share of new business (SPEC §7.4)."""
    fig, ax = plt.subplots(figsize=(8, 4.2))
    cells = [c for c in table["cell"].unique() if c.startswith("LTA") and c.endswith("NS")]
    for cell, color in zip(cells, SERIES):
        t = table[table["cell"] == cell]
        ax.plot(t["male_share"], t["margin_at_priced_rate"], color=color, marker="o", markersize=5,
                label=f"Level term, age {cell.split()[1]} non-smoker")
    ax.axvline(priced_share, color=TEXT_2, linewidth=0.8, linestyle="--")
    ax.text(priced_share, ax.get_ylim()[1], " priced mix", color=TEXT_2, fontsize=8, va="top")
    ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Male share of new business")
    ax.set_ylabel("Pooled profit margin")
    ax.set_title("Unisex pricing: margin if the sex mix differs from the priced 60% male")
    ax.legend(loc="lower left")
    return _save(fig, "02c_sex_mix_margin.png", note)


def _ae_dots(ax, frame, value, lo, hi, color, label=None, offset=0.0):
    y = np.arange(len(frame)) + offset
    ax.errorbar(frame[value], y, xerr=[frame[value] - frame[lo], frame[hi] - frame[value]], fmt="o",
                color=color, ecolor=color, elinewidth=1.5, capsize=0, markersize=6, label=label, zorder=3)
    return y


def mortality_ae(study, note: str) -> Path:
    """Chart 3: mortality A/E by count, by segment, with 95% CIs (SPEC §12)."""
    # Calendar year is omitted: every policy was issued in 2023, so it repeats policy year exactly.
    cuts = [("total", "Total"), ("t", "Policy year"), ("age_band", "Attained age"),
            ("sex", "Sex"), ("smoker", "Smoker"), ("product", "Product"), ("sa_band", "Sum assured")]
    frames = []
    for cut, title in cuts:
        f = study[study["cut"] == cut].copy()
        if cut == "t":
            f["segment"] = "PY " + (f["segment"].astype(int) + 1).astype(str)
        if cut == "sa_band":
            order = {"<150k": 0, "150-300k": 1, "300-500k": 2, "500k+": 3}
            f = f.sort_values("segment", key=lambda c: c.map(order))
        f["label"] = title + ": " + f["segment"].astype(str) + "  (" + f["deaths"].astype(int).astype(str) + " deaths)"
        frames.append(f)
    import pandas as pd
    data = pd.concat(frames, ignore_index=True).iloc[::-1].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(9, 8))
    _ae_dots(ax, data, "ae_deaths", "ae_deaths_lo", "ae_deaths_hi", SERIES[0])
    ax.axvline(1.0, color=TEXT_2, linewidth=0.8, linestyle="--")
    ax.set_yticks(np.arange(len(data)), data["label"])
    ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Actual / expected deaths (by count) on basis_2022, with 95% confidence interval")
    ax.set_title("Mortality A/E 2023–25: wide intervals, few deaths")
    ax.grid(axis="y", visible=False)
    return _save(fig, "03_mortality_ae_segments.png", note)


def lapse_ae(by_t_channel, study, note: str) -> Path:
    """Chart 4: lapse A/E by policy year and channel (SPEC §12)."""
    fig, ax = plt.subplots(figsize=(8, 4.2))
    years = sorted({s.split()[0] for s in by_t_channel["segment"]})
    x = np.arange(len(years))
    for i, (channel, color) in enumerate(zip(("broker", "direct"), SERIES)):
        f = by_t_channel[by_t_channel["segment"].str.endswith(channel)].copy()
        f["py"] = f["segment"].str.split().str[0]
        f = f.set_index("py").loc[years]
        ax.errorbar(x + (i - 0.5) * 0.18, f["ae_lapses"], yerr=[f["ae_lapses"] - f["ae_lapses_lo"],
                    f["ae_lapses_hi"] - f["ae_lapses"]], fmt="o-", color=color, markersize=6, elinewidth=1.5,
                    capsize=0, label=f"{channel.capitalize()} channel")
    total = study[(study["cut"] == "total")].iloc[0]["ae_lapses"]
    ax.axhline(1.0, color=TEXT_2, linewidth=0.8, linestyle="--")
    ax.axhline(total, color=TEXT_2, linewidth=0.8, linestyle=":")
    ax.text(x[-1] + 0.65, total + 0.01, f"all channels: {total:.0%}", color=TEXT_2, fontsize=8, ha="right", va="bottom")
    ax.set_xticks(x, [y.replace("PY", "Policy year ") for y in years])
    ax.set_xlim(-0.4, x[-1] + 0.7)
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_ylabel("Actual / expected lapses")
    ax.set_title("Lapse A/E 2023–25: about 20% above basis, higher through brokers")
    ax.legend(loc="center right")
    return _save(fig, "04_lapse_ae_duration_channel.png", note)


def scr_and_risk_margin(summary, paths, note: str) -> Path:
    """Chart 6: SCR by component, SCR run-off, and risk margin current vs 2027 (SPEC §12)."""
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(14, 4.4), gridspec_kw={"width_ratios": [1.1, 1.3, 1]})
    total = summary[summary["product"] == "Total"].iloc[0]
    parts = [("Mortality", total["scr_mortality"]), ("Lapse", total["scr_lapse"]), ("Expense", total["scr_expense"]),
             ("Catastrophe", total["scr_cat"]), ("Diversification", -total["diversification"]),
             ("Life SCR", total["scr_life"])]
    running = 0.0
    for i, (name, amount) in enumerate(parts):
        if name == "Life SCR":
            a.bar(i, amount, color=SERIES[0], width=0.7)
        else:
            # heights are always positive; a negative step (diversification) spans running+amount … running
            a.bar(i, abs(amount), bottom=running if amount >= 0 else running + amount,
                  color=GRID if amount < 0 else SERIES[1], width=0.7)
            running += amount
        top = amount if name == "Life SCR" else (running if amount >= 0 else running - amount)
        a.text(i, top + total["scr_life"] * 0.02, f"{'−' if amount < 0 else ''}€{abs(amount) / 1e6:.1f}m",
               ha="center", fontsize=8, color=TEXT_2)
    a.set_xticks(range(len(parts)), [p[0] for p in parts], rotation=30, ha="right")
    a.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"€{v / 1e6:.0f}m"))
    a.set_title("Life SCR at issue, by risk")

    for product, color in zip(("LTA", "MP"), SERIES):
        p = paths[paths["product"] == product]
        b.plot(p["j"], p["scr_life"], color=color, label="Level term" if product == "LTA" else "Mortgage protection")
    b.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"€{v / 1e6:.0f}m"))
    b.set_xlabel("Years after issue")
    b.set_xticks([0, 5, 10, 15, 19])
    b.set_title("Projected life SCR run-off")
    b.legend(loc="upper right")

    prods = summary[summary["product"].isin(["LTA", "MP"])]
    x = np.arange(len(prods))
    c.bar(x - 0.18, prods["rm_current"], width=0.34, color=SERIES[0], label="Current (6%)")
    c.bar(x + 0.18, prods["rm_2027"], width=0.34, color=SERIES[1], label="2027 (4.75%, 0.96^t)")
    for xi, (_, r) in zip(x, prods.iterrows()):
        c.text(xi + 0.18, r["rm_2027"], f"−{1 - r['rm_ratio']:.0%}", ha="center", va="bottom", fontsize=9, color=TEXT)
    c.set_xticks(x, ["Level term", "Mortgage protection"])
    c.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"€{v / 1e6:.1f}m"))
    c.set_title("Risk margin at issue")
    c.legend(loc="upper right")
    return _save(fig, "06_scr_and_risk_margin.png", note)


def csm_release(by_product, note: str) -> Path:
    """Chart 7: expected cumulative CSM release, level term vs mortgage protection (SPEC §12)."""
    fig, ax = plt.subplots(figsize=(8, 4.2))
    labels = {"LTA": "Level term", "MP": "Mortgage protection"}
    for (product, color) in zip(("LTA", "MP"), SERIES):
        p = by_product[by_product["product"] == product].sort_values("year")
        released = p["release"].cumsum() / p["release"].sum()
        ax.plot(p["year"], released, color=color, label=labels[product])
        five = released.iloc[4]
        ax.scatter([5], [five], color=color, s=36, zorder=3)
        if product == "MP":
            ax.text(4.6, five + 0.03, f"{five:.0%} by year 5", ha="right", va="bottom", fontsize=8, color=TEXT_2)
        else:
            ax.text(5.4, five - 0.03, f"{five:.0%} by year 5", ha="left", va="top", fontsize=8, color=TEXT_2)
    ax.set_xticks([1, 5, 10, 15, 20])
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Policy year")
    ax.set_ylabel("Share of total CSM released")
    ax.set_title("Mortgage protection releases its CSM faster")
    ax.legend(loc="lower right")
    return _save(fig, "07_csm_release_lta_vs_mp.png", note)


def assumption_review_impact(core, note: str) -> Path:
    """Chart 5: the core result table as % change from basis_2022 to basis_2025 at 31 Dec 2025 (SPEC §12)."""
    rows = core[core["unit"] == "EUR"].copy()
    rows = rows[rows["metric"] != "IFRS 17 loss component"]
    rows["pct"] = rows["change"] / rows["basis_2022"].abs()
    extra = core[core["metric"] == "Premium adequacy, book (premium-weighted)"].iloc[0]
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.2), gridspec_kw={"width_ratios": [1.6, 1]})
    y = np.arange(len(rows))[::-1]
    a.barh(y, rows["pct"], color=SERIES[0], height=0.6)

    def eur(v):
        return f"{'−' if v < 0 else ''}€{abs(v) / 1e6:,.1f}m"

    for yi, (_, r) in zip(y, rows.iterrows()):
        a.text(r["pct"] + (0.01 if r["pct"] >= 0 else -0.01), yi,
               f"{r['pct']:+.0%}  ({eur(r['basis_2022'])} → {eur(r['basis_2025'])})".replace("-", "−"),
               va="center", ha="left" if r["pct"] >= 0 else "right", fontsize=8, color=TEXT_2)
    a.set_yticks(y, rows["metric"])
    a.axvline(0, color=TEXT_2, linewidth=0.8)
    a.set_xlim(-0.6, 0.6)
    a.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    a.set_title("Change from the assumption review, 31 Dec 2025")
    a.set_xlabel("Change vs basis_2022 (BEL is negative: a rise means less future profit)")
    margins = core[core["unit"] == "margin"]
    x = np.arange(len(margins))
    b.bar(x - 0.18, margins["basis_2022"], width=0.34, color=SERIES[0], label="on basis_2022 (priced)")
    b.bar(x + 0.18, margins["basis_2025"], width=0.34, color=SERIES[1], label="on basis_2025")
    b.set_xticks(x, [m.split(", ")[1] for m in margins["metric"]])
    b.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    b.set_ylim(0, 0.14)
    b.axhline(0, color=TEXT_2, linewidth=0.8)
    b.set_title("New-business margin at current rates")
    b.legend(loc="upper right", ncol=2, fontsize=8)
    b.text(0.0, -0.16, f"Current premiums cover {extra['basis_2025']:.1%} of the premium basis_2025 requires (book)",
           transform=b.transAxes, fontsize=8, color=TEXT_2)
    return _save(fig, "05_assumption_review_impact.png", note)


NEUTRAL_STEPS = {"Expected cash flows", "Unwind", "Accretion (locked-in)", "Release to profit"}


def _waterfall(ax, steps, total_label_open, total_label_close, colors_by_sign):
    running = 0.0
    names, lows, heights, colors = [], [], [], []
    for i, (name, amount) in enumerate(steps):
        if i == 0:
            names.append(total_label_open); lows.append(min(0, amount)); heights.append(abs(amount)); colors.append(SERIES[0])
            running = amount
            continue
        names.append(name); lows.append(min(running, running + amount)); heights.append(abs(amount))
        colors.append("#b9b8b2" if name in NEUTRAL_STEPS else colors_by_sign[amount > 0])
        running += amount
    names.append(total_label_close); lows.append(min(0, running)); heights.append(abs(running)); colors.append(SERIES[0])
    x = np.arange(len(names))
    ax.bar(x, heights, bottom=lows, color=colors, width=0.7)
    values = [steps[0][1]] + [a for _, a in steps[1:]] + [running]
    for xi, lo, h, v in zip(x, lows, heights, values):
        label = f"{v / 1e6:+.1f}" if 0 < xi < len(x) - 1 else f"{v / 1e6:.1f}"
        label = "0.0" if label in ("+0.0", "-0.0") else label.replace("-", "−")
        ax.text(xi, lo + h, label, ha="center", va="bottom", fontsize=8, color=TEXT_2)
    ax.set_xticks(x, names, rotation=35, ha="right")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{'−' if v < 0 else ''}€{abs(v) / 1e6:.0f}m"))
    ax.axhline(0, color=TEXT_2, linewidth=0.8)


def aoc_waterfall_2025(sii, ifrs, note: str) -> Path:
    """Chart 8: 2025 analysis of change — Solvency II BEL and IFRS 17 CSM side by side (SPEC §12)."""
    fig, (a, b) = plt.subplots(1, 2, figsize=(13, 4.8))
    bel_steps = [("Opening", sii["opening"]), ("Expected cash flows", sii["expected_cash_flows"]),
                 ("Unwind", sii["unwind"]), ("Mortality experience", sii["mortality_experience"]),
                 ("Lapse experience", sii["lapse_experience"]), ("Assumption change", sii["assumption_change"]),
                 ("Economic (curve)", sii["economic"])]
    # BEL: increase = worse (orange); decrease = better (blue-grey)
    _waterfall(a, bel_steps, "Opening BEL", "Closing BEL", {True: SERIES[1], False: SERIES[2]})
    a.set_title("Solvency II BEL, 2025 (a rise = less future profit; grey = expected)")
    csm_steps = [("Opening", ifrs["csm_opening"]), ("Accretion (locked-in)", ifrs["csm_accretion"]),
                 ("Mortality experience", ifrs["csm_adj_mortality"]), ("Lapse experience", ifrs["csm_adj_lapse"]),
                 ("Assumption change", ifrs["csm_adj_assumptions"]), ("RA change", ifrs["csm_adj_ra"]),
                 ("Onerous (to loss comp.)", ifrs["csm_lc_absorbed"]), ("Release to profit", ifrs["csm_release"])]
    _waterfall(b, csm_steps, "Opening CSM", "Closing CSM", {True: SERIES[2], False: SERIES[1]})
    b.set_title("IFRS 17 CSM, 2025 (a fall = less profit to come; grey = expected)")
    return _save(fig, "08_aoc_waterfall_2025.png", note)
