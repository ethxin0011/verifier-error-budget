# Verifier Error Budget

Certified metamorphic audit of the answer verifiers used in RLVR reward computation and math benchmark evaluation.

**Paper:** arXiv:XXXX.XXXXX
**License:** MIT

---

## What this is

Verifiers convert a free-text answer into a binary correctness signal. Prior work reports that a standard harness validates ground truth against itself at ~94% accuracy, attributing the residual to LaTeX parsing. That is an aggregate. This repo decomposes it.

Given a gold answer `g` and a semantics-preserving transformation `T`, the pair `(g, T(g))` has a known correct verdict **by construction**. Any verifier rejecting it commits a *certified false negative* — no human adjudication required. The dual construction certifies false positives.

## Findings

| Metric | Result |
| --- | --- |
| Self-validation spread | 53.8% – 95.2% across four implementations on identical inputs |
| Same-library disagreement | 49.9% between two `math-verify` configurations |
| Error concentration | 93.0% of `mv-latex` in-contract failures are whitespace/punctuation |
| Scale-dependent FP | 0% → 100% off-by-one acceptance at gold magnitude 10⁴ |

**Dataset scale:** 307,420 verdicts · 43 transformations · 14 strata · 4,990 gold answers.

## Verifiers audited

1. `math-verify` v0.9.0, LaTeX extraction (library default)
2. `math-verify` v0.9.0, `ExprExtractionConfig`
3. DeepSeek-Math lineage string normalizer
4. Reference cascade: string → numeric (`rel_tol=1e-4`) → SymPy

> ⚠️ **ANTLR4 runtime is pinned to 4.13.2.** Behaviour differs across runtimes; results are not reproducible without this pin.

---

## Repository structure

```
verifier-error-budget/
├── env/                      # Conda / Docker environment definitions for the Azure ML job
│                             #   (pinned ANTLR4 4.13.2, math-verify 0.9.0, SymPy)
├── src/                      # Experiment source, mounted as job code by pipelines.yml
│   ├── verifiers.py          # Verifier adapters + crash/timeout-isolating execution harness
│   │                         #   verdict domain: TRUE | FALSE | TIMEOUT | ERROR | CRASH
│   │                         #   PER_ITEM_TIMEOUT_S = 5, CHUNK_WALL_TIMEOUT_S = 900
│   ├── transforms.py         # The 43 semantics-preserving + adversarial transformations T
│   ├── build_dataset.py      # Gold-answer sampling into the 14 strata (4,990 answers)
│   ├── run_audit.py          # Sharded verdict generation → raw verdict shards
│   └── aggregate.py          # Verdict shards → results/ CSVs
│                             #   counts ERROR/CRASH separately from FALSE
├── results/                  # ALL GENERATED ARTIFACTS LAND HERE (see below)
│   ├── raw/                  # Per-shard verdict records, one row per (gold, T, verifier)
│   ├── tables/               # Paper tables, emitted by make_tables.py
│   │   ├── T1_self_validation.csv
│   │   ├── T2_pairwise_disagreement.csv
│   │   ├── T3_error_budget_by_category.csv
│   │   └── T8_offbyone_by_magnitude.csv
│   └── figures/              # Paper figures, emitted by make_figures.py (PDF + PNG)
├── make_tables.py            # results/raw/ → results/tables/*.csv
├── make_figures.py           # results/tables/ → results/figures/*.pdf
├── pipelines.yml             # Azure ML pipeline definition (compute, env, sharding)
├── submitjob.ipynb           # Notebook driver: submits the pipeline, monitors, pulls results
├── LICENSE                   # MIT
└── README.md
```

### About `results/`

`results/` is the single destination for every generated artifact — nothing else in the repo is written to at runtime. It has three tiers, in dependency order:

- **`results/raw/`** — the immutable audit output. One record per `(gold answer, transformation, verifier)` triple, carrying the verdict symbol and the stratum label. This is the 307,420-verdict corpus; everything downstream is a pure function of it. Written by `src/run_audit.py`, one file per shard, then reduced by `src/aggregate.py`.
- **`results/tables/`** — the numbers that appear in the paper. Regenerate with `python make_tables.py`. `T8_offbyone_by_magnitude.csv` is the one to read first: it exposes the scale-invariance of `math.isclose(rel_tol=1e-4)`, where a gold answer of 10,000 accepts 10,001 because the relative error is only 0.01%.
- **`results/figures/`** — plots built from the tables, not from raw. Regenerate with `python make_figures.py`.

Because every tier is derived, deleting `results/tables/` and `results/figures/` is always safe; deleting `results/raw/` means re-running the full audit.

---

## Reproducing

```bash
# 1. Environment (the ANTLR4 pin is load-bearing)
conda env create -f env/environment.yml
conda activate verifier-error-budget

# 2. Run the audit (Azure ML) — see submitjob.ipynb for the interactive path
az ml job create -f pipelines.yml

# 3. Rebuild paper artifacts from results/raw/
python make_tables.py
python make_figures.py
```

## Reading the verdict symbols

A crashing verifier must never be scored as a flawless one. `aggregate.py` therefore keeps five outcomes distinct:

| Symbol | Meaning |
| --- | --- |
| `TRUE` / `FALSE` | The verifier returned a boolean |
| `TIMEOUT` | Exceeded the 5 s per-item budget |
| `ERROR` | Raised an exception (e.g. `parse_latex` on `\boxed{}`, `\times10^{}`, set notation) |
| `CRASH` | Killed the worker process (segfault / OOM) |

The SymPy cascade errors on ~46.5% of inputs, but on the subset it *does* process it accepts 15.8% of off-by-one adversarial cases. Crash rate must always be reported alongside the FP rate.

## Citation

```bibtex
@misc{verifier-error-budget,
  title  = {Verifier Error Budget: A Certified Metamorphic Audit of RLVR Math Verifiers},
  year   = {2026},
  eprint = {XXXX.XXXXX},
  archivePrefix = {arXiv},
  primaryClass  = {cs.CL}
}
```
