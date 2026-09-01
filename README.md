# Verifier Error Budget
2
 
3
Certified metamorphic audit of the answer verifiers used in RLVR reward
4
computation and math benchmark evaluation.
5
 
6
**Paper:** [arXiv:XXXX.XXXXX](https://arxiv.org/abs/XXXX.XXXXX)
7
 
8
## What this is
9
 
10
Verifiers convert a free-text answer into a binary correctness signal.
11
Prior work reports that a standard harness validates ground truth against
12
itself at ~94% accuracy, attributing the residual to LaTeX parsing. That
13
is an aggregate. This repo decomposes it.
14
 
15
Given a gold answer `g` and a semantics-preserving transformation `T`, the
16
pair `(g, T(g))` has a known correct verdict by construction. Any verifier
17
rejecting it commits a **certified false negative** — no human
18
adjudication required. The dual construction certifies false positives.
19
 
20
## Findings
21
 
22
| | Result |
23
|---|---|
24
| Self-validation spread | **53.8% – 95.2%** across four implementations on identical inputs |
25
| Same-library disagreement | **49.9%** between two `math-verify` configurations |
26
| Error concentration | **93.0%** of `mv-latex` in-contract failures are whitespace/punctuation |
27
| Scale-dependent FP | **0% → 100%** off-by-one acceptance at gold magnitude 10⁴ |
28
 
29
307,420 verdicts, 43 transformations, 14 strata, 4,990 gold answers.
30
 
31
## Verifiers audited
32
 
33
- `math-verify` v0.9.0, LaTeX extraction (library default)
34
- `math-verify` v0.9.0, `ExprExtractionConfig`
35
- DeepSeek-Math lineage string normalizer
36
- Reference cascade: string → numeric (`rel_tol=1e-4`) → SymPy
37
 
38
ANTLR4 runtime pinned to 4.13.2; behaviour differs across runtimes.
39
 
40
## Repo layout
