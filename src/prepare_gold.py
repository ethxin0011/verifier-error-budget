"""Step 1: load corpora, dedup golds, expand transforms, STREAM shards.

v5 CHANGES:
  PROBLEM observed in v4: 3,565 unique golds loaded, but only 2 contained
  set notation (\\{...\\}). S10_sets therefore stays at n~55 and supports
  no claim. This is a DIVERSITY limit, not a compute limit - adding more
  corpus golds cannot manufacture answer forms that are absent from the
  source data.

  FIX: targeted synthesis (--synth_per_family N, default 400).
  Generates answers designed to exercise the starved strata:
      sets       \\{1,2,3\\}, \\{-2,5\\}
      intervals  [0,1), (-\\infty,-5]\\cup[5,\\infty)
      radicals   3\\sqrt{5}, \\frac{\\sqrt{3}}{2}
      products   (x+1)(x-2)

  These are legitimate MATH-style answer forms. Synthetic golds carry
  source="synth_<family>" so results can be reported SEPARATELY from
  corpus-derived ones. Disclose this in the paper.

  Set --synth_per_family 0 to disable synthesis entirely.

File location:
  <project>/src/prepare_gold.py
"""

import argparse
import hashlib
import json
import os
import random
import re
from collections import Counter

from transforms import TRANSFORMS
from verifiers import VERIFIERS

CAP_GSM8K = 8000
CAP_MATH = 15000
CAP_BIGMATH = 25000

SYNTH_SEED = 20260901


def _try_load(candidates, split, streaming=False):
    from datasets import load_dataset
    for repo, cfg in candidates:
        try:
            if cfg:
                ds = load_dataset(repo, cfg, split=split, streaming=streaming)
            else:
                ds = load_dataset(repo, split=split, streaming=streaming)
            print("    loaded {} [{}]".format(repo, cfg or "-"), flush=True)
            return ds
        except Exception as e:
            print("    miss {} [{}]: {}".format(
                repo, cfg or "-", str(e)[:110]), flush=True)
    return None


def _extract_boxed(text):
    s = str(text)
    i = s.rfind("\\boxed")
    if i < 0:
        return None
    j = s.find("{", i)
    if j < 0:
        return None
    depth = 1
    k = j + 1
    while k < len(s) and depth > 0:
        if s[k] == "{":
            depth += 1
        elif s[k] == "}":
            depth -= 1
            if depth == 0:
                return s[j + 1:k].strip()
        k += 1
    return None


# ----------------------------------------------------------------------
# v5: targeted synthesis for starved strata
# ----------------------------------------------------------------------

def synth_golds(n_per_family):
    """Generate MATH-style answers that exercise S10 / S4 / S7."""
    if n_per_family <= 0:
        return []

    rng = random.Random(SYNTH_SEED)
    out = []

    def push(val, family):
        out.append((val, "synth_" + family))

    # --- sets  (S10) ---
    for _ in range(n_per_family):
        k = rng.choice([2, 2, 3, 3, 4])
        vals = rng.sample(range(-20, 40), k)
        push("\\{" + ",".join(str(v) for v in sorted(vals)) + "\\}", "set")

    # --- intervals  (S10 + S4) ---
    for _ in range(n_per_family):
        a = rng.randint(-30, 10)
        b = a + rng.randint(1, 25)
        lo = rng.choice(["[", "("])
        hi = rng.choice(["]", ")"])
        style = rng.random()
        if style < 0.25:
            push("(-\\infty," + str(b) + hi, "interval")
        elif style < 0.5:
            push(lo + str(a) + ",\\infty)", "interval")
        elif style < 0.7:
            push("(-\\infty," + str(a) + "]\\cup[" + str(b) + ",\\infty)",
                 "interval")
        else:
            push(lo + str(a) + "," + str(b) + hi, "interval")

    # --- radicals  (S7) ---
    for _ in range(n_per_family):
        r = rng.choice([2, 3, 5, 6, 7, 10, 11, 13, 15])
        style = rng.random()
        if style < 0.35:
            push("\\sqrt{" + str(r) + "}", "radical")
        elif style < 0.6:
            push(str(rng.randint(2, 9)) + "\\sqrt{" + str(r) + "}", "radical")
        elif style < 0.8:
            push("\\frac{\\sqrt{" + str(r) + "}}{" + str(rng.randint(2, 6)) + "}",
                 "radical")
        else:
            push(str(rng.randint(1, 9)) + " + \\sqrt{" + str(r) + "}", "radical")

    # --- parenthesised products / tuples  (S4) ---
    for _ in range(n_per_family):
        style = rng.random()
        if style < 0.4:
            a = rng.randint(1, 12)
            b = rng.randint(1, 12)
            sa = rng.choice(["+", "-"])
            sb = rng.choice(["+", "-"])
            push("(x" + sa + str(a) + ")(x" + sb + str(b) + ")", "product")
        elif style < 0.7:
            push("(" + str(rng.randint(-15, 15)) + "," +
                 str(rng.randint(-15, 15)) + ")", "tuple")
        else:
            push("\\left(\\frac{" + str(rng.randint(1, 9)) + "}{" +
                 str(rng.randint(2, 9)) + "},\\frac{" +
                 str(rng.randint(1, 9)) + "}{" +
                 str(rng.randint(2, 9)) + "}\\right)", "tuple")

    # --- fractions (feeds S1 and the new S14_unreduced) ---
    for _ in range(n_per_family):
        num = rng.randint(1, 30)
        den = rng.randint(2, 30)
        push("\\frac{" + str(num) + "}{" + str(den) + "}", "fraction")

    return out


def load_golds(max_n, synth_per_family):
    out = []
    seen = set()
    per_source = Counter()

    def add(ans, src, cap=10 ** 9):
        if per_source[src] >= cap:
            return
        a = str(ans).strip()
        if not a or len(a) > 200:
            return
        h = hashlib.md5(a.encode()).hexdigest()[:16]
        if h in seen:
            return
        seen.add(h)
        out.append({"gold_id": h, "gold": a, "source": src})
        per_source[src] += 1

    # ---------------- GSM8K ----------------
    print("  [1/4] GSM8K", flush=True)
    ds = _try_load([("openai/gsm8k", "main"), ("gsm8k", "main")], "train")
    if ds is not None:
        for r in ds:
            add(r["answer"].split("####")[-1], "gsm8k", CAP_GSM8K)
    print("    unique so far: {}".format(len(out)), flush=True)

    # ---------------- MATH ----------------
    print("  [2/4] MATH", flush=True)
    ds = _try_load([("HuggingFaceH4/MATH-500", None)], "test")
    if ds is not None:
        for r in ds:
            a = r.get("answer") or _extract_boxed(r.get("solution", ""))
            if a:
                add(a, "math", CAP_MATH)

    for cfg in ["algebra", "counting_and_probability", "geometry",
                "intermediate_algebra", "number_theory", "prealgebra",
                "precalculus"]:
        ds = _try_load([
            ("EleutherAI/hendrycks_math", cfg),
            ("nlile/hendrycks-MATH-benchmark", None),
        ], "train")
        if ds is None:
            continue
        for r in ds:
            a = r.get("answer") or _extract_boxed(r.get("solution", ""))
            if a:
                add(a, "math", CAP_MATH)
    print("    unique so far: {}".format(len(out)), flush=True)

    # ---------------- Big-Math ----------------
    print("  [3/4] Big-Math", flush=True)
    ds = _try_load([("SynthLabsAI/Big-Math-RL-Verified", None)], "train")
    if ds is None:
        ds = _try_load([("SynthLabsAI/Big-Math-RL-Verified", None)],
                       "train", streaming=True)
    if ds is not None:
        for i, r in enumerate(ds):
            if per_source["bigmath"] >= CAP_BIGMATH or i > 300000:
                break
            add(r.get("answer", ""), "bigmath", CAP_BIGMATH)
    print("    unique so far: {}".format(len(out)), flush=True)

    # ---------------- v5: targeted synthesis ----------------
    print("  [4/4] targeted synthesis (starved strata)", flush=True)
    n_before = len(out)
    for val, src in synth_golds(synth_per_family):
        add(val, src)
    print("    added {} synthetic golds".format(len(out) - n_before), flush=True)

    # ---------------- diagnostics ----------------
    print("\n  --- gold pool composition ---", flush=True)
    for k, v in per_source.most_common():
        print("    {:18s} {}".format(k, v), flush=True)

    pat = {
        "plain_number": lambda s: bool(re.fullmatch(r"-?\d+(\.\d+)?", s)),
        "has_frac": lambda s: "\\frac" in s or "\\dfrac" in s,
        "has_sqrt": lambda s: "\\sqrt" in s,
        "has_paren": lambda s: ("(" in s and ")" in s) or ("[" in s and "]" in s),
        "has_set": lambda s: "\\{" in s,
        "has_infty": lambda s: "\\infty" in s,
        "has_space": lambda s: " " in s,
    }
    print("\n  --- LaTeX richness ---", flush=True)
    for name, fn in pat.items():
        c = sum(1 for g in out if fn(g["gold"]))
        print("    {:14s} {:6d}  ({:.1%})".format(
            name, c, c / max(len(out), 1)), flush=True)

    random.Random(SYNTH_SEED).shuffle(out)
    return out[:max_n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--max_golds", type=int, default=40000)
    ap.add_argument("--shard_size", type=int, default=2000)
    ap.add_argument("--synth_per_family", type=int, default=400,
                    help="synthetic golds per family; 0 disables synthesis")
    a = ap.parse_args()

    os.makedirs(a.out_dir, exist_ok=True)
    print("loading corpora...", flush=True)
    golds = load_golds(a.max_golds, a.synth_per_family)
    print("\nFINAL: {} unique golds\n".format(len(golds)), flush=True)

    stats = Counter()
    strat_n = Counter()
    state = {"shard_idx": 0, "n_tasks": 0}
    buf = []

    def flush():
        if not buf:
            return
        path = os.path.join(a.out_dir,
                            "shard_{:06d}.jsonl".format(state["shard_idx"]))
        with open(path, "w") as f:
            for r in buf:
                f.write(json.dumps(r) + "\n")
        state["shard_idx"] += 1
        del buf[:]

    for gi, g in enumerate(golds):
        for t in TRANSFORMS:
            pred = t.apply(g["gold"])
            if pred is None:
                continue
            stats[t.tid] += 1
            strat_n[t.stratum] += 1
            for vname in VERIFIERS:
                buf.append({
                    "gold_id": g["gold_id"],
                    "gold": g["gold"],
                    "source": g["source"],
                    "tid": t.tid,
                    "stratum": t.stratum,
                    "tclass": t.tclass,
                    "pred": pred,
                    "verifier": vname,
                })
                state["n_tasks"] += 1
                if len(buf) >= a.shard_size:
                    flush()
        if gi % 5000 == 0:
            print("  {}/{} golds -> {:,} tasks".format(
                gi, len(golds), state["n_tasks"]), flush=True)

    flush()

    nv = len(VERIFIERS)
    print("\n  --- projected per-stratum n (x{} verifiers) ---".format(nv),
          flush=True)
    for st, c in sorted(strat_n.items(), key=lambda x: -x[1]):
        flag = "  <-- WEAK" if c * nv < 200 else ""
        print("    {:18s} {:8d}{}".format(st, c * nv, flag), flush=True)

    manifest = {
        "n_golds": len(golds),
        "n_tasks": state["n_tasks"],
        "n_shards": state["shard_idx"],
        "n_verifiers": nv,
        "verifiers": list(VERIFIERS),
        "synth_per_family": a.synth_per_family,
        "applicability": dict(stats),
        "stratum_n": {k: v * nv for k, v in strat_n.items()},
    }
    with open(os.path.join(a.out_dir, "_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    print("\nwrote {} shards / {:,} tasks".format(
        state["shard_idx"], state["n_tasks"]), flush=True)


if __name__ == "__main__":
    main()
