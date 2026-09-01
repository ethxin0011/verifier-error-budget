"""Generate publication-quality figures from the report CSVs.

v2 CHANGES:
  - Fig 3: label offset increased so the value text no longer collides with
    the ~94% reference line; xlim widened accordingly.
  - NaN-safe throughout: cells where a verifier returned no verdict are
    skipped rather than plotted as 0.
  - Fig 1: optional hatching on segments dominated by execution error, so a
    crash-heavy verifier is visually distinct from a rejection-heavy one.

Usage:
    python make_figures.py --report_dir <RDIR> --out_dir <RDIR>/figures

Produces PNG (preview, 300 dpi) and PDF (vector, for LaTeX).
"""

import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 10,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.5,
})

SHORT = {
    "mathverify_expr": "math-verify (expr)",
    "mathverify_latex": "math-verify (latex)",
    "strip_string": "strip_string",
    "sympy_cascade": "sympy cascade",
}

STRATUM = {
    "S1_frac_dialect": "frac dialect",
    "S2_frac_decimal": "frac/decimal",
    "S4_delimiters": "delimiters",
    "S5_mathmode": "math-mode",
    "S6_whitespace": "whitespace",
    "S7_sqrt_exp": "sqrt/exponent",
    "S9_grouping": "grouping",
    "S10_sets": "sets",
    "S14_unreduced": "unreduced frac",
}

# Okabe-Ito, colourblind safe
PALETTE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7",
           "#56B4E9", "#D55E00", "#F0E442", "#999999"]


def save(fig, out_dir, name):
    for ext in ("png", "pdf"):
        p = os.path.join(out_dir, f"{name}.{ext}")
        fig.savefig(p)
        print("  wrote", p)
    plt.close(fig)


# =====================================================================
# FIGURE 1 - error budget
# =====================================================================
def fig_error_budget(report_dir, out_dir):
    p = os.path.join(report_dir, "T2_error_mass_share.csv")
    if not os.path.exists(p):
        print("  [skip] fig1"); return
    t2 = pd.read_csv(p)
    t2 = t2[t2.fail_count > 0].copy()
    if not len(t2):
        print("  [skip] fig1: no failures"); return

    has_err = "share_from_error" in t2.columns

    verifiers = (t2.groupby("verifier").fail_count.sum()
                   .sort_values(ascending=False).index.tolist())
    strata = (t2.groupby("stratum").fail_count.sum()
                .sort_values(ascending=False).index.tolist())

    fig, ax = plt.subplots(figsize=(5.5, 3.0))
    left = np.zeros(len(verifiers))

    for k, st in enumerate(strata):
        vals, hatches = [], []
        for v in verifiers:
            row = t2[(t2.verifier == v) & (t2.stratum == st)]
            if len(row):
                vals.append(float(row.error_mass_share.iloc[0]))
                e = float(row.share_from_error.iloc[0]) if has_err else 0.0
                hatches.append(e > 0.5 if not np.isnan(e) else False)
            else:
                vals.append(0.0); hatches.append(False)
        vals = np.array(vals)
        if vals.sum() == 0:
            continue
        for i, (v, h) in enumerate(zip(vals, hatches)):
            if v == 0:
                continue
            ax.barh(i, v, left=left[i], height=0.62,
                    color=PALETTE[k % len(PALETTE)],
                    hatch="///" if h else None,
                    edgecolor="white", linewidth=0.6)
            if v >= 0.12:
                ax.text(left[i] + v / 2, i, f"{100*v:.0f}%",
                        ha="center", va="center", fontsize=7.5,
                        color="white", fontweight="bold")
        # legend proxy
        ax.barh(np.nan, 0, color=PALETTE[k % len(PALETTE)],
                label=STRATUM.get(st, st))
        left += vals

    ax.set_yticks(range(len(verifiers)))
    ax.set_yticklabels([SHORT.get(v, v) for v in verifiers])
    ax.set_xlabel("share of in-contract certified failures")
    ax.set_xlim(0, 1)
    ax.set_xticks(np.arange(0, 1.01, 0.2))
    ax.set_xticklabels([f"{int(100*x)}%" for x in np.arange(0, 1.01, 0.2)])
    ax.set_ylim(-0.7, len(verifiers) - 0.3)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)

    ncol = 4 if len(strata) > 4 else max(len(strata), 1)
    leg = ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.26),
                    ncol=ncol, frameon=False, columnspacing=1.1,
                    handlelength=1.3)
    if has_err:
        ax.text(0.5, -0.52, "hatched = failure caused by execution error",
                transform=ax.transAxes, ha="center", fontsize=7,
                color="#555555")
    save(fig, out_dir, "fig1_error_budget")


# =====================================================================
# FIGURE 2 - off-by-one step function
# =====================================================================
def fig_offbyone(report_dir, out_dir):
    p = os.path.join(report_dir, "T8_offbyone_by_magnitude.csv")
    if not os.path.exists(p):
        print("  [skip] fig2"); return
    t8 = pd.read_csv(p)
    if not len(t8):
        print("  [skip] fig2: empty"); return

    order = ["<10", "10-100", "100-1k", "1k-10k", "10k-100k", ">100k"]
    labels = [r"$<10$", r"$10^1$", r"$10^2$", r"$10^3$", r"$10^4$", r"$10^5{+}$"]
    present = [m for m in order if m in set(t8.magnitude)]
    xs = np.arange(len(present))

    fig, ax = plt.subplots(figsize=(5.0, 2.8))

    for k, v in enumerate(sorted(t8.verifier.unique())):
        d = t8[t8.verifier == v].set_index("magnitude").reindex(present)
        y = d.fp_rate.values.astype(float)
        hot = np.nanmax(y) > 0 if not np.all(np.isnan(y)) else False
        ax.plot(xs, y,
                marker="o" if hot else "s",
                markersize=5.5 if hot else 3.5,
                linewidth=2.2 if hot else 1.0,
                color=PALETTE[k % len(PALETTE)],
                alpha=1.0 if hot else 0.55,
                zorder=3 if hot else 2,
                label=SHORT.get(v, v))

    if "10k-100k" in present:
        xt = present.index("10k-100k") - 0.5
        ax.axvline(xt, color="#666666", linestyle="--", linewidth=1.0, zorder=1)
        ax.text(xt + 0.08, 0.52,
                "tolerance threshold\n" r"$|g|\geq 1/\mathrm{rel\_tol}=10^{4}$",
                fontsize=7.5, color="#444444", va="center")

    ax.set_xticks(xs)
    ax.set_xticklabels([labels[order.index(m)] for m in present])
    ax.set_xlabel("gold answer magnitude")
    ax.set_ylabel("off-by-one acceptance")
    ax.set_ylim(-0.05, 1.08)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
    ax.legend(loc="center left", frameon=False)
    save(fig, out_dir, "fig2_offbyone_step")


# =====================================================================
# FIGURE 3 - self-validation spread   (v2: label collision fixed)
# =====================================================================
def fig_selfval(report_dir, out_dir):
    p = os.path.join(report_dir, "T6_reconciliation.csv")
    if not os.path.exists(p):
        print("  [skip] fig3"); return
    t6 = pd.read_csv(p)
    if not len(t6):
        print("  [skip] fig3: empty"); return
    head = ("self_validation_all" if "self_validation_all" in t6.columns
            else "self_validation_rate")
    t6 = t6.sort_values(head)

    fig, ax = plt.subplots(figsize=(5.2, 2.5))
    ys = np.arange(len(t6))
    ax.barh(ys, t6[head], height=0.55,
            color=PALETTE[0], edgecolor="white", linewidth=0.6, zorder=2)

    # v2 FIX: larger offset so labels clear the 94% reference line
    for y, v in zip(ys, t6[head]):
        ax.text(v + 0.035, y, f"{100*v:.1f}%", va="center", fontsize=8,
                zorder=4)

    ax.axvline(0.94, color="#D55E00", linestyle="--", linewidth=1.2, zorder=3)
    ax.text(0.94, -0.85, "prior work (~94%)", fontsize=7.5,
            color="#D55E00", ha="center", va="bottom")

    ax.set_yticks(ys)
    ax.set_yticklabels([SHORT.get(v, v) for v in t6.verifier])
    ax.set_xlabel("self-validation rate (in-contract)")
    ax.set_xlim(0, 1.15)                       # v2 FIX: widened
    ax.set_xticks(np.arange(0, 1.01, 0.2))
    ax.set_xticklabels([f"{int(100*x)}%" for x in np.arange(0, 1.01, 0.2)])
    ax.set_ylim(-1.1, len(t6) - 0.4)
    ax.grid(axis="y", visible=False)
    save(fig, out_dir, "fig3_selfval")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report_dir", required=True)
    ap.add_argument("--out_dir", required=True)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    print("figures:")
    fig_error_budget(a.report_dir, a.out_dir)
    fig_offbyone(a.report_dir, a.out_dir)
    fig_selfval(a.report_dir, a.out_dir)
    print("\ndone. use the .pdf versions in LaTeX.")


if __name__ == "__main__":
    main()
