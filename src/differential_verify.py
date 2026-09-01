"""Step 2 (parallel run_function): one mini-batch = one shard file.

Sized for Standard_D4ds_v5 (4 vCPU / 16 GB): small CHUNK keeps the
per-subprocess working set well under the node memory budget.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd

from verifiers import run_chunk

_SRC = os.path.dirname(os.path.abspath(__file__))
_OUT = None
CHUNK = 100


def init():
    global _OUT
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--verdicts_out", required=True)
    args, _ = p.parse_known_args()
    _OUT = args.verdicts_out
    os.makedirs(_OUT, exist_ok=True)
    print("init ok ->", _OUT, flush=True)


def run(mini_batch):
    processed = []
    for path in mini_batch:
        p = str(path)
        if not p.endswith(".jsonl"):
            continue

        with open(p) as f:
            items = [json.loads(line) for line in f if line.strip()]

        results = []
        for i in range(0, len(items), CHUNK):
            results.extend(run_chunk(items[i:i + CHUNK], _SRC))

        base = os.path.splitext(os.path.basename(p))[0]
        out_path = os.path.join(_OUT, base + ".parquet")
        pd.DataFrame(results).to_parquet(out_path, index=False)
        processed.append("{}:{}".format(base, len(results)))

    return pd.DataFrame({"processed": processed})
