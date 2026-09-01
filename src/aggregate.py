"""Step 3: streaming aggregation -> FN/FP tables, error mass, Wilson CIs.

v6 CHANGES (fixes the "0.0% reads as correct" reporting bug):

  PROBLEM: rates were computed as n_true/n and n_false/n, where n includes
  ERROR and TIMEOUT outcomes. A verifier that CRASHES on an input was
  therefore reported with fp_rate = 0.0, which reads as "correctly
  rejected" when in fact it never returned a verdict at all.

  Observed instances in the v5 run (sympy_cascade):
      A_append  n=4990  n_error=4990 (100%)  -> reported fp_rate 0.0
      A_sign    n=2104  n_error= 816 (38.8%) -> reported fp_rate 0.0
      A_scale   n=3209  n_error= 439 (13.7%) -> reported fp_rate 0.0
      S3_boxing n=19952 n_error=19952 (100%) -> reported fn_rate 0.0

  FIX: introduce the EVALUATED denominator.
      n_eval        = n_true + n_false           (verdicts actually returned)
      coverage      = n_eval / n                 (fraction judged at all)
      fn_rate_eval  = n_false / n_eval           (NaN when n_eval == 0)
      fp_rate_eval  = n_true  / n_eval           (NaN when n_eval == 0)

  Both the all-inputs rate and the evaluated rate are emitted, plus
  coverage and err_rate, so a crash can never masquerade as a correct
  verdict. Cells with zero coverage report NaN, not 0.

  NOTE: this changes only how existing verdicts are SUMMARISED. No
  re-verification is required; the parquet shards already distinguish
  TRUE / FALSE / TIMEOUT / ERROR / CRASH.

File location:
  <project>/src/aggregate.py
"""

import argparse
import glob
import json
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from transforms import in_contract
except Exception:
    def in_contract(verifier, stratum):
        return True

CERT = "certified_equiv"
CONTRACT = "contract_dep"
ADV = "adversarial"

KEEP = ["gold_id", "gold", "tid", "stratum", "tclass", "verifier", "verdict"]


def wilson(p, n, z=1.96):
    """Wilson score interval. NaN-safe: returns NaN where n == 0 or p is NaN."""
    p = np.asarray(p, dtype=float)
    n = np.asarray(n, dtype=float)
    bad = (n <= 0) | np.isnan(p)
    n_safe = np.where(bad, 1.0, n)
    p_safe = np.where(bad, 0.0, p)
    denom = 1.0 + z ** 2 / n_safe
    centre = (p_safe + z ** 2 / (2 * n_safe)) / denom
    half = z * np.sqrt(p_safe * (1 - p_safe) / n_safe
                       + z ** 2 / (4 * n_safe ** 2)) / denom
    lo = np.where(bad, np.nan, np.clip(centre - half, 0.0, 1.0))
    hi = np.where(bad, np.nan, np.clip(centre + half, 0.0, 1.0))
    return lo, hi


def safe_div(a, b):
    """Elementwise a/b, NaN where b == 0."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return np.divide(a, b, out=np.full_like(a, np.nan, dtype=float),
                     where=(b > 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verdicts_dir", required=True)
    ap.add_argument("--report_dir", required=True)
    a = ap.parse_args()

    os.makedirs(a.report_dir, exist_ok=True)
    files = sorted(glob.glob(os.path.join(a.verdicts_dir, "*.parquet")))
    print("{} shard files".format(len(files)), flush=True)
    if not files:
        raise SystemExit("no parquet files in " + a.verdicts_dir)

    cnt = defaultdict(lambda: defaultdict(int))
    piv_rows = []
    offby_rows = []

    # ================= PASS 1: streaming counters =====================
    for i, f in enumerate(files):
        try:
            d = pd.read_parquet(f, columns=KEEP)
        except Exception:
            d = pd.read_parquet(f)
            for c in KEEP:
                if c not in d.columns:
                    d[c] = None
            d = d[KEEP]

        for (tc, st, v), grp in d.groupby(["tclass", "stratum", "verifier"],
                                          observed=True):
            key = (tc, st, v)
            vd = grp["verdict"]
            n_true = int((vd == "TRUE").sum())
            n_false = int((vd == "FALSE").sum())
            n_to = int((vd == "TIMEOUT").sum())
            n_err = int(vd.isin(["ERROR", "CRASH"]).sum())
            cnt[key]["n"] += len(grp)
            cnt[key]["true"] += n_true
            cnt[key]["false"] += n_false
            cnt[key]["timeout"] += n_to
            cnt[key]["error"] += n_err
            cnt[key]["eval"] += n_true + n_false          # v6
            cnt[key]["fail"] += n_false + n_to + n_err

        piv_rows.append(d[d["tclass"] == CERT][
            ["gold_id", "tid", "verifier", "verdict"]])

        ob = d[d["tid"] == "A04_off_by_one"][["gold", "verifier", "verdict"]]
        if len(ob):
            offby_rows.append(ob)

        if i % 50 == 0:
            print("  pass1 {}/{}".format(i, len(files)), flush=True)

    rows = []
    for (tc, st, v), c in cnt.items():
        rows.append({
            "tclass": tc, "stratum": st, "verifier": v,
            "n": c["n"], "n_true": c["true"], "n_false": c["false"],
            "n_timeout": c["timeout"], "n_error": c["error"],
            "n_eval": c["eval"], "n_fail": c["fail"],
            "in_contract": bool(in_contract(v, st)),
        })
    agg = pd.DataFrame(rows)

    # ---------------- v6 rate definitions -----------------------------
    agg["coverage"] = safe_div(agg["n_eval"], agg["n"])
    agg["err_rate"] = safe_div(agg["n_error"], agg["n"])
    agg["timeout_rate"] = safe_div(agg["n_timeout"], agg["n"])

    is_cert = agg["tclass"] == CERT
    is_adv = agg["tclass"] == ADV

    # all-inputs rates (denominator = n)
    agg["fn_rate_all"] = np.where(is_cert, safe_div(agg["n_false"], agg["n"]),
                                  np.nan)
    agg["failure_rate"] = np.where(is_cert, safe_div(agg["n_fail"], agg["n"]),
                                   np.nan)
    agg["fp_rate_all"] = np.where(is_adv, safe_div(agg["n_true"], agg["n"]),
                                  np.nan)

    # evaluated rates (denominator = n_eval)  <-- headline in v6
    agg["fn_rate"] = np.where(is_cert, safe_div(agg["n_false"], agg["n_eval"]),
                              np.nan)
    agg["fp_rate"] = np.where(is_adv, safe_div(agg["n_true"], agg["n_eval"]),
                              np.nan)

    agg.to_csv(os.path.join(a.report_dir, "T0_raw_counts.csv"), index=False)

    cert = agg[is_cert]
    cert_ic = cert[cert["in_contract"]]
    cert_oc = cert[~cert["in_contract"]]
    adv = agg[is_adv]

    # ---------------- T1: in-contract FN ------------------------------
    t1 = cert_ic[["stratum", "verifier", "n", "n_eval", "n_true", "n_false",
                  "n_error", "n_timeout", "n_fail", "coverage",
                  "fn_rate", "fn_rate_all", "failure_rate",
                  "err_rate", "timeout_rate"]].copy()
    if len(t1):
        lo, hi = wilson(t1["fn_rate"].values, t1["n_eval"].values)
        t1["fn_ci_lo"], t1["fn_ci_hi"] = lo, hi
        flo, fhi = wilson(t1["failure_rate"].values, t1["n"].values)
        t1["fail_ci_lo"], t1["fail_ci_hi"] = flo, fhi
        t1 = t1.sort_values(["verifier", "failure_rate"],
                            ascending=[True, False])
    t1.to_csv(os.path.join(a.report_dir, "T1_fn_by_stratum_verifier.csv"),
              index=False)

    # ---------------- T2: error mass share ----------------------------
    t2 = cert_ic[["verifier", "stratum", "n_false", "n_error", "n_timeout",
                  "n_fail"]].copy()
    t2 = t2.rename(columns={"n_fail": "fail_count"})
    if len(t2):
        t2["error_mass_share"] = t2.groupby("verifier")["fail_count"].transform(
            lambda s: s / s.sum() if s.sum() else 0.0)
        # split the mass into its causes so a crash-heavy verifier is visible
        t2["share_from_reject"] = safe_div(t2["n_false"], t2["fail_count"])
        t2["share_from_error"] = safe_div(t2["n_error"] + t2["n_timeout"],
                                          t2["fail_count"])
        t2 = t2.sort_values(["verifier", "error_mass_share"],
                            ascending=[True, False])
    t2.to_csv(os.path.join(a.report_dir, "T2_error_mass_share.csv"), index=False)

    # ---------------- T3: adversarial FP ------------------------------
    t3 = adv[["stratum", "verifier", "n", "n_eval", "n_true", "n_false",
              "n_error", "coverage", "fp_rate", "fp_rate_all",
              "err_rate"]].copy()
    if len(t3):
        lo, hi = wilson(t3["fp_rate"].values, t3["n_eval"].values)
        t3["ci_lo"], t3["ci_hi"] = lo, hi
        t3 = t3.sort_values("fp_rate", ascending=False, na_position="last")
    t3.to_csv(os.path.join(a.report_dir, "T3_fp_by_stratum_verifier.csv"),
              index=False)

    # ---------------- T4: disagreement --------------------------------
    # Only pairs where BOTH verifiers returned a verdict are compared.
    cert_all = pd.concat(piv_rows, ignore_index=True) if piv_rows else pd.DataFrame()
    del piv_rows
    if len(cert_all):
        judged = cert_all[cert_all["verdict"].isin(["TRUE", "FALSE"])].copy()
        judged["ok"] = (judged["verdict"] == "TRUE").astype("int8")
        piv = judged.pivot_table(index=["gold_id", "tid"], columns="verifier",
                                 values="ok", aggfunc="first")
        del cert_all, judged
        names = [str(c) for c in piv.columns]
        k = len(names)
        mat = np.full((k, k), np.nan)
        npairs = np.zeros((k, k), dtype=int)
        for ii in range(k):
            ci = piv.iloc[:, ii]
            for jj in range(k):
                if ii == jj:
                    mat[ii, jj] = 0.0
                    npairs[ii, jj] = int(ci.notna().sum())
                    continue
                cj = piv.iloc[:, jj]
                both = ci.notna() & cj.notna()
                nb = int(both.sum())
                npairs[ii, jj] = nb
                if nb:
                    mat[ii, jj] = float((ci[both] != cj[both]).sum()) / nb
        dis = pd.DataFrame(mat, index=names, columns=names)
        pd.DataFrame(npairs, index=names, columns=names).to_csv(
            os.path.join(a.report_dir, "T4b_disagreement_support.csv"))
    else:
        dis = pd.DataFrame()
    dis.to_csv(os.path.join(a.report_dir, "T4_disagreement_matrix.csv"))

    # ---------------- T5: contract-dependent --------------------------
    con = agg[agg["tclass"] == CONTRACT].copy()
    if len(con):
        con["accept_rate"] = safe_div(con["n_true"], con["n_eval"])
        con["accept_rate_all"] = safe_div(con["n_true"], con["n"])
        con = con[["stratum", "verifier", "n", "n_eval", "coverage",
                   "accept_rate", "accept_rate_all",
                   "err_rate"]].sort_values(["stratum", "verifier"])
    con.to_csv(os.path.join(a.report_dir, "T5_contract_dependent.csv"),
               index=False)

    # ---------------- T6: reconciliation ------------------------------
    if len(cert_ic):
        recon = cert_ic.groupby("verifier").agg(
            n=("n", "sum"), n_eval=("n_eval", "sum"),
            n_true=("n_true", "sum"), n_false=("n_false", "sum"),
            n_timeout=("n_timeout", "sum"), n_error=("n_error", "sum"),
            n_fail=("n_fail", "sum"),
        ).reset_index()
        recon["coverage"] = safe_div(recon["n_eval"], recon["n"])
        # self-validation on inputs the verifier actually judged
        recon["self_validation_rate"] = safe_div(recon["n_true"],
                                                 recon["n_eval"])
        recon["self_validation_all"] = safe_div(recon["n_true"], recon["n"])
        recon["residual"] = 1 - recon["self_validation_rate"]
        recon["share_false"] = safe_div(recon["n_false"], recon["n"])
        recon["share_timeout"] = safe_div(recon["n_timeout"], recon["n"])
        recon["share_error"] = safe_div(recon["n_error"], recon["n"])
        recon = recon.sort_values("self_validation_rate", ascending=False)
    else:
        recon = pd.DataFrame()
    recon.to_csv(os.path.join(a.report_dir, "T6_reconciliation.csv"), index=False)

    # ---------------- T7: out-of-contract -----------------------------
    t7 = cert_oc[["stratum", "verifier", "n", "n_eval", "coverage",
                  "fn_rate", "fn_rate_all", "err_rate"]].copy()
    t7 = t7.sort_values("fn_rate", ascending=False, na_position="last")
    t7.to_csv(os.path.join(a.report_dir, "T7_out_of_contract.csv"), index=False)

    # ---------------- T8: off-by-one by magnitude ---------------------
    if offby_rows:
        ob = pd.concat(offby_rows, ignore_index=True)
        ob["gold_num"] = pd.to_numeric(ob["gold"], errors="coerce")
        ob = ob.dropna(subset=["gold_num"])
        ob["judged"] = ob["verdict"].isin(["TRUE", "FALSE"]).astype(int)
        ob["accepted"] = (ob["verdict"] == "TRUE").astype(int)
        bins = [0, 10, 100, 1000, 10000, 100000, np.inf]
        labels = ["<10", "10-100", "100-1k", "1k-10k", "10k-100k", ">100k"]
        ob["magnitude"] = pd.cut(ob["gold_num"].abs(), bins=bins,
                                 labels=labels, right=False)
        t8 = (ob.groupby(["verifier", "magnitude"], observed=True)
                .agg(n=("accepted", "size"),
                     n_eval=("judged", "sum"),
                     n_accepted=("accepted", "sum"))
                .reset_index())
        t8["fp_rate"] = safe_div(t8["n_accepted"], t8["n_eval"])
        t8["coverage"] = safe_div(t8["n_eval"], t8["n"])
        t8.to_csv(os.path.join(a.report_dir, "T8_offbyone_by_magnitude.csv"),
                  index=False)
    else:
        pd.DataFrame().to_csv(
            os.path.join(a.report_dir, "T8_offbyone_by_magnitude.csv"),
            index=False)

    # ---------------- summary -----------------------------------------
    def _s(df, col):
        return int(df[col].sum()) if len(df) else 0

    ic_n = _s(cert_ic, "n")
    ic_eval = _s(cert_ic, "n_eval")
    adv_n = _s(adv, "n")
    adv_eval = _s(adv, "n_eval")
    tot = int(agg["n"].sum()) if len(agg) else 0

    summary = {
        "n_verdicts": tot,
        "in_contract_n": ic_n,
        "in_contract_n_evaluated": ic_eval,
        "in_contract_coverage": (ic_eval / ic_n) if ic_n else None,
        "in_contract_fn_rate_evaluated": (_s(cert_ic, "n_false") / ic_eval)
                                         if ic_eval else None,
        "in_contract_fn_rate_all": (_s(cert_ic, "n_false") / ic_n)
                                   if ic_n else None,
        "in_contract_failure_rate": (_s(cert_ic, "n_fail") / ic_n)
                                    if ic_n else None,
        "out_of_contract_n": _s(cert_oc, "n"),
        "adversarial_n_evaluated": adv_eval,
        "adversarial_coverage": (adv_eval / adv_n) if adv_n else None,
        "adversarial_fp_rate_evaluated": (_s(adv, "n_true") / adv_eval)
                                         if adv_eval else None,
        "overall_error_rate": (_s(agg, "n_error") / tot) if tot else None,
    }
    with open(os.path.join(a.report_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2), flush=True)

    # ---------------- coverage warnings -------------------------------
    low = agg[(agg["coverage"] < 0.99) & (agg["n"] > 0)]
    if len(low):
        print("\n*** LOW COVERAGE CELLS (verifier did not return a verdict) ***",
              flush=True)
        cols = ["tclass", "stratum", "verifier", "n", "n_eval", "coverage",
                "err_rate"]
        print(low[cols].sort_values("coverage").to_string(index=False),
              flush=True)
        print("\nThese are reported as NaN, not 0, in the rate columns.",
              flush=True)


if __name__ == "__main__":
    main()
