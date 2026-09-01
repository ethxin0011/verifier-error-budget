"""
Verifier adapters + crash/timeout-isolating execution harness.

v4 CHANGES:
  - sympy_cascade RE-ENABLED as a fourth "reference implementation".
    In the pilot it errored on 46.5% of inputs (parse_latex cannot handle
    \\boxed{}, \\times10^{}, set notation), BUT on the subset it does
    process it accepted 15.8% of off-by-one adversarial cases. That false
    positive is the single most valuable finding in the study: a verifier
    that accepts a WRONG answer corrupts RL training, whereas one that
    rejects a RIGHT answer only adds noise.

    The v3 aggregate.py now counts ERROR/CRASH separately from FALSE, so
    a crashing verifier can no longer masquerade as flawless. Report its
    crash rate honestly alongside the FP rate.

  - Mechanism worth naming in the paper: math.isclose(rel_tol=1e-4) is
    SCALE INVARIANT. For a gold answer of 10,000 the value 10,001 differs
    by 0.01% and is therefore accepted. FP rate should rise with answer
    magnitude - see T8_offbyone_by_magnitude.csv.

Verdict codes:
  TRUE / FALSE  - verifier returned a boolean
  TIMEOUT       - exceeded per-item wall clock (5s)
  ERROR         - raised an exception
  CRASH         - killed the worker process (segfault / OOM)

File location:
  <project>/src/verifiers.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

TRUE = "TRUE"
FALSE = "FALSE"
TIMEOUT = "TIMEOUT"
ERROR = "ERROR"
CRASH = "CRASH"

PER_ITEM_TIMEOUT_S = 5
CHUNK_WALL_TIMEOUT_S = 900

# Documented tolerance of the reference cascade. Scale invariant by design.
NUMERIC_REL_TOL = 1e-4


# ======================================================================
# In-worker implementations (run inside the child process)
# ======================================================================

def _v_mathverify(gold, pred):
    """math-verify with LaTeX extraction (library default)."""
    from math_verify import parse, verify
    return bool(verify(parse("$" + gold + "$"), parse("$" + pred + "$")))


def _v_mathverify_expr(gold, pred):
    """math-verify restricted to plain-expression extraction."""
    from math_verify import parse, verify
    from math_verify.parser import ExprExtractionConfig
    cfg = [ExprExtractionConfig()]
    g = parse(gold, extraction_config=cfg)
    p = parse(pred, extraction_config=cfg)
    return bool(verify(g, p))


def _v_strip_string(gold, pred):
    """DeepSeek-Math / MATH lineage normalizer, then exact string compare."""
    from normalizers import strip_string
    return strip_string(gold) == strip_string(pred)


def _v_sympy_cascade(gold, pred):
    """Reference three-level cascade: string -> numeric(rel_tol) -> symbolic.

    This is the canonical pattern used across many evaluation harnesses.
    Two properties are under audit:
      1. parse_latex() raises on boxed / scientific / set notation -> ERROR
      2. math.isclose(rel_tol=1e-4) is scale invariant -> off-by-one FPs
         on large gold answers.
    """
    import math
    from normalizers import strip_string, parse_digits
    from sympy import simplify
    from sympy.parsing.latex import parse_latex

    a = strip_string(gold)
    b = strip_string(pred)
    if a == b:
        return True

    da = parse_digits(a)
    db = parse_digits(b)
    if da is not None and db is not None:
        return math.isclose(da, db, rel_tol=NUMERIC_REL_TOL)

    return simplify(parse_latex(a) - parse_latex(b)) == 0


# ----------------------------------------------------------------------
# ACTIVE REGISTRY (v4: 4 verifiers)
# ----------------------------------------------------------------------
VERIFIERS = {
    "mathverify_latex": _v_mathverify,
    "mathverify_expr": _v_mathverify_expr,
    "strip_string": _v_strip_string,
    "sympy_cascade": _v_sympy_cascade,   # v4: re-enabled, crash rate reported
}


# ======================================================================
# Child-process source
# ======================================================================

_CHILD_SRC = r'''
import json
import signal
import sys
import time

sys.path.insert(0, sys.argv[3])
from verifiers import VERIFIERS, PER_ITEM_TIMEOUT_S, TRUE, FALSE, TIMEOUT, ERROR


class _TO(Exception):
    pass


def _handler(signum, frame):
    raise _TO()


signal.signal(signal.SIGALRM, _handler)

with open(sys.argv[1]) as fh:
    items = json.load(fh)

out = open(sys.argv[2], "w")
for it in items:
    fn = VERIFIERS[it["verifier"]]
    t0 = time.time()
    signal.setitimer(signal.ITIMER_REAL, PER_ITEM_TIMEOUT_S)
    try:
        v = TRUE if fn(it["gold"], it["pred"]) else FALSE
        err = ""
    except _TO:
        v = TIMEOUT
        err = "per_item_timeout"
    except Exception as e:
        v = ERROR
        err = type(e).__name__ + ": " + str(e)[:180]
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    it["verdict"] = v
    it["err"] = err
    it["latency_ms"] = round((time.time() - t0) * 1000, 3)
    out.write(json.dumps(it) + "\n")
    out.flush()
out.close()
'''


def run_chunk(items, src_dir):
    """Run one chunk in an isolated subprocess. Survives segfaults and hangs."""
    tmp = tempfile.mkdtemp(prefix="vchunk_")
    fin = os.path.join(tmp, "in.json")
    fout = os.path.join(tmp, "out.jsonl")
    fsrc = os.path.join(tmp, "child.py")

    try:
        with open(fin, "w") as f:
            json.dump(items, f)
        with open(fsrc, "w") as f:
            f.write(_CHILD_SRC)

        try:
            subprocess.run(
                [sys.executable, fsrc, fin, fout, src_dir],
                timeout=CHUNK_WALL_TIMEOUT_S,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired:
            pass

        done = {}
        if os.path.exists(fout):
            with open(fout) as f:
                for line in f:
                    try:
                        r = json.loads(line)
                    except Exception:
                        continue
                    done[(r["gold_id"], r["tid"], r["verifier"])] = r

        results = []
        for it in items:
            key = (it["gold_id"], it["tid"], it["verifier"])
            if key in done:
                results.append(done[key])
            else:
                bad = dict(it)
                bad["verdict"] = CRASH
                bad["err"] = "worker_died"
                bad["latency_ms"] = None
                results.append(bad)
        return results
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
