# Verifier Error Budget

Certified metamorphic audit of the answer verifiers used in RLVR reward computation and math benchmark evaluation.

**Paper:** [arXiv:XXXX.XXXXX](https://arxiv.org/abs/XXXX.XXXXX)

## What this is

Verifiers convert a free-text answer into a binary correctness signal. Prior work reports that a standard harness validates ground truth against itself at ~94% accuracy, attributing the residual to LaTeX parsing. That is an aggregate. This repo decomposes it.

Given a gold answer `g` and a semantics-preserving transformation `T`, the pair `(g, T(g))` has a known correct verdict by construction. Any verifier rejecting it commits a **certified false negative** — no human adjudication required. The dual construction certifies false positives.

## Findings

| Metric | Result |
| :--- | :--- |
| Self-validation spread | **53.8% – 95.2%** across four implementations on identical inputs |
| Same-library disagreement | **49.9%** between two `math-verify` configurations |
| Error concentration | **93.0%** of `mv-latex` in-contract failures are whitespace/punctuation |
| Scale-dependent FP | **0% → 100%** off-by-one acceptance at gold magnitude 10⁴ |

*Dataset scale: 307,420 verdicts, 43 transformations, 14 strata, 4,990 gold answers.*

## Verifiers audited

* `math-verify` v0.9.0, LaTeX extraction (library default)
* `math-verify` v0.9.0, `ExprExtractionConfig`
* DeepSeek-Math lineage string normalizer
* Reference cascade: string → numeric (`rel_tol=1e-4`) → SymPy

> ⚠️ ANTLR4 runtime is pinned to **4.13.2**; behaviour differs across runtimes.
