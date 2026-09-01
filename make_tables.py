"""Regenerate all paper tables directly from the report CSVs.

v2 CHANGES: surfaces the v6 aggregate columns.
  - coverage and err_rate shown wherever a verifier failed to return a verdict
  - rates that are NaN (zero coverage) print as "n/a", never as 0.0%
  - Table 3 gains an error column so a crash cannot read as a rejection

Emits Markdown and LaTeX so the paper never drifts from the data.

Usage:
    python make_tables.py --report_dir <RDIR> --out_dir <RDIR>/paper_tables
"""

import argparse
import os

import numpy as np
import pandas as pd

SHORT = {
    "mathverify_expr": "mv_expr",
    "mathverify_latex": "mv_latex",
    "strip_string": "strip",
    "sympy_cascade": "sympy",
}

STRATUM = {
    "S1_frac_dialect": "S1 frac dialect",
    "S2_frac_decimal": "S2 frac/decimal",
    "S3_boxing": "S3 boxing",
    "S4_delimiters": "S4 delimiters",
    "S5_mathmode": "S5 math-mode",
    "S6_whitespace": "S6 whitespace",
    "S7_sqrt_exp": "S7 sqrt/exponent",
    "S8_scientific": "S8 scientific",
    "S9_grouping": "S9 grouping",
    "S10_sets": "S10 sets",
    "S11_text": "S11 text wrap",
    "S12_units": "S12 units",
    "S13_percent": "S13 percent",
    "S14_unreduced": "S14 unreduced",
}


def pct(x, d=1):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    return f"{100 * float(x):.{d}f}%"


def ci(lo, hi):
    if pd.isna(lo) or pd.isna(hi):
        return "n/a"
    return f"[{100*max(lo,0):.1f}, {100*hi:.1f}]"


def thousands(x):
    return "n/a" if pd.isna(x) else f"{int(x):,}"


def md_table(df, aligns=None):
    cols = list(df.columns)
    aligns = aligns or ["---"] * len(cols)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join(aligns) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(out)


def tex_table(df, caption, label, colspec):
    cols = list(df.columns)
    esc = lambda s: (str(s).replace("%", r"\%").replace("_", r"\_")
                     .replace("[", "{[}").replace("]", "{]}"))
    lines = [r"\begin{table}[t]", r"\centering", r"\small",
             r"\begin{tabular}{" + colspec + "}", r"\toprule",
             " & ".join(esc(c) for c in cols) + r" \\", r"\midrule"]
    for _, r in df.iterrows():
        lines.append(" & ".join(esc(r[c]) for c in cols) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}",
              r"\caption{" + caption + "}", r"\label{" + label + "}",
              r"\end{table}"]
    return "\n".join(lines)


def emit(md, tex, title, df, caption, label, colspec, aligns):
    md.append(f"### {title}\n\n" + md_table(df, aligns) + f"\n\n*{caption}*\n")
    tex.append(tex_table(df, caption, label, colspec))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report_dir", required=True)
    ap.add_argument("--out_dir", required=True)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    md, tex = [], []

    def rd(name):
        p = os.path.join(a.report_dir, name)
        return pd.read_csv(p) if os.path.exists(p) else None

    # ---------------- Table 1: self-validation ------------------------
    t6 = rd("T6_reconciliation.csv")
    spread = float("nan")
    if t6 is not None and len(t6):
        # HEADLINE = all-inputs rate: operationally, a crash and a rejection
        # both mean the correct answer went unrewarded. The evaluated rate and
        # coverage are reported alongside as the diagnostic split.
        head = ("self_validation_all" if "self_validation_all" in t6.columns
                else "self_validation_rate")
        t6 = t6.sort_values(head, ascending=False)
        d = pd.DataFrame({
            "Verifier": t6.verifier,
            "n": t6.n.map(thousands),
            "Accepted": t6.n_true.map(thousands),
            "Self-val.": t6[head].map(pct),
        })
        if "coverage" in t6.columns:
            d["Coverage"] = t6.coverage.map(pct)
            d["Self-val. (judged)"] = t6.self_validation_rate.map(pct)
        spread = 100 * (t6[head].max() - t6[head].min())
        cap = (f"Self-validation: acceptance of certified-equivalent variants, "
               f"in-contract only. Self-val. is over all inputs; Coverage is "
               f"the fraction on which the verifier returned a verdict at all, "
               f"and Self-val. (judged) restricts to those. Spread: "
               f"{spread:.1f} points.")
        n = len(d.columns)
        emit(md, tex, "Table 1: Self-validation by implementation", d, cap,
             "tab:selfval", "l" + "r" * (n - 1),
             ["---"] + ["---:"] * (n - 1))

    # ---------------- Table 2: error mass share -----------------------
    t2 = rd("T2_error_mass_share.csv")
    if t2 is not None and len(t2):
        t2 = t2[t2.fail_count > 0].copy()
        d = pd.DataFrame({
            "Verifier": t2.verifier,
            "Stratum": t2.stratum.map(lambda s: STRATUM.get(s, s)),
            "Failures": t2.fail_count.map(thousands),
            "Share": t2.error_mass_share.map(pct),
        })
        if "share_from_error" in t2.columns:
            d["from error"] = t2.share_from_error.map(pct)
        cap = ("Error mass share: fraction of in-contract failures by stratum. "
               "The final column separates failures caused by execution error "
               "from those caused by rejection.")
        n = len(d.columns)
        emit(md, tex, "Table 2: Error mass share", d, cap, "tab:errormass",
             "ll" + "r" * (n - 2), ["---", "---"] + ["---:"] * (n - 2))

    # ---------------- Table 3: FN rates -------------------------------
    t1 = rd("T1_fn_by_stratum_verifier.csv")
    if t1 is not None and len(t1):
        t1 = t1.sort_values("fn_rate", ascending=False, na_position="last")
        d = pd.DataFrame({
            "Stratum": t1.stratum.map(lambda s: STRATUM.get(s, s)),
            "Verifier": t1.verifier.map(lambda v: SHORT.get(v, v)),
            "n": t1.n.map(thousands),
            "Judged": t1.n_eval.map(thousands) if "n_eval" in t1 else t1.n.map(thousands),
            "FN": t1.fn_rate.map(pct),
            "95% CI": [ci(lo, hi) for lo, hi in zip(t1.fn_ci_lo, t1.fn_ci_hi)],
        })
        if "err_rate" in t1.columns:
            d["Err"] = t1.err_rate.map(pct)
        cap = ("Certified false-negative rates by stratum and verifier, "
               "in-contract only, with Wilson score intervals. FN is computed "
               "over verdicts actually returned; cells with no verdicts report "
               "n/a. Err gives the execution-error rate.")
        n = len(d.columns)
        emit(md, tex, "Table 3: Per-stratum FN rates", d, cap, "tab:fnrates",
             "ll" + "r" * (n - 3) + "lr" if "Err" in d else "ll" + "r" * (n - 3) + "l",
             ["---", "---", "---:", "---:", "---:", "---"] + (["---:"] if "Err" in d else []))

    # ---------------- Table 4: off-by-one -----------------------------
    t8 = rd("T8_offbyone_by_magnitude.csv")
    if t8 is not None and len(t8):
        order = ["<10", "10-100", "100-1k", "1k-10k", "10k-100k", ">100k"]
        piv = t8.pivot_table(index="magnitude", columns="verifier",
                             values="fp_rate", aggfunc="first")
        nmap = t8.groupby("magnitude", observed=True).n.first()
        piv = piv.reindex([o for o in order if o in piv.index])
        d = pd.DataFrame({"Magnitude": piv.index,
                          "n": [thousands(nmap.get(i, 0)) for i in piv.index]})
        for v in piv.columns:
            d[SHORT.get(v, v)] = [pct(x) for x in piv[v]]
        cap = ("Off-by-one acceptance by gold magnitude, over verdicts actually "
               "returned. A deterministic step reflects scale-invariant "
               "relative tolerance.")
        n = len(d.columns)
        emit(md, tex, "Table 4: Off-by-one by magnitude", d, cap,
             "tab:offbyone", "lr" + "r" * (n - 2),
             ["---"] + ["---:"] * (n - 1))

    # ---------------- Table 5: disagreement ---------------------------
    p = os.path.join(a.report_dir, "T4_disagreement_matrix.csv")
    if os.path.exists(p):
        t4 = pd.read_csv(p, index_col=0)
        t4.index = [SHORT.get(i, i) for i in t4.index]
        t4.columns = [SHORT.get(c, c) for c in t4.columns]
        d = pd.DataFrame({"": t4.index})
        for c in t4.columns:
            d[c] = ["---" if (not pd.isna(v) and abs(v) < 1e-9) else pct(v)
                    for v in t4[c]]
        cap = ("Pairwise disagreement on certified-equivalent pairs, computed "
               "only over pairs where both verifiers returned a verdict.")
        n = len(d.columns)
        emit(md, tex, "Table 5: Cross-verifier disagreement", d, cap,
             "tab:disagree", "l" + "r" * (n - 1),
             ["---"] + ["---:"] * (n - 1))

    # ---------------- Table 6: contract-dependent ---------------------
    t5 = rd("T5_contract_dependent.csv")
    if t5 is not None and len(t5):
        piv = t5.pivot_table(index="stratum", columns="verifier",
                             values="accept_rate", aggfunc="first")
        nmap = t5.groupby("stratum").n.first()
        d = pd.DataFrame({"Input class": [STRATUM.get(i, i) for i in piv.index],
                          "n": [thousands(nmap.get(i, 0)) for i in piv.index]})
        for v in piv.columns:
            d[SHORT.get(v, v)] = [pct(x) for x in piv[v]]
        cap = ("Acceptance on contract-dependent input classes, over verdicts "
               "actually returned. These are undocumented contract "
               "differences, not defects.")
        n = len(d.columns)
        emit(md, tex, "Table 6: Contract-dependent acceptance", d, cap,
             "tab:contract", "lr" + "r" * (n - 2),
             ["---", "---:"] + ["---:"] * (n - 2))

    # ---------------- Table 7: out-of-contract ------------------------
    t7 = rd("T7_out_of_contract.csv")
    if t7 is not None and len(t7):
        t7 = t7.sort_values("fn_rate", ascending=False, na_position="last")
        d = pd.DataFrame({
            "Stratum": t7.stratum.map(lambda s: STRATUM.get(s, s)),
            "Verifier": t7.verifier,
            "n": t7.n.map(thousands),
            "Rejection": t7.fn_rate.map(pct),
        })
        if "err_rate" in t7.columns:
            d["Err"] = t7.err_rate.map(pct)
        cap = ("Out-of-contract behaviour: strata a verifier does not claim to "
               "handle. Reported for completeness; not counted as defects.")
        n = len(d.columns)
        emit(md, tex, "Table 7: Out-of-contract", d, cap, "tab:oocontract",
             "ll" + "r" * (n - 2), ["---", "---"] + ["---:"] * (n - 2))

    with open(os.path.join(a.out_dir, "tables.md"), "w") as f:
        f.write("\n\n".join(md))
    with open(os.path.join(a.out_dir, "tables.tex"), "w") as f:
        f.write("% Auto-generated. Requires \\usepackage{booktabs}\n\n")
        f.write("\n\n".join(tex))

    print("wrote:")
    print(" ", os.path.join(a.out_dir, "tables.md"))
    print(" ", os.path.join(a.out_dir, "tables.tex"))
    if not np.isnan(spread):
        print(f"\nself-validation spread: {spread:.1f} points")


if __name__ == "__main__":
    main()
