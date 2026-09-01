### Table 1: Self-validation by implementation

| Verifier | n | Accepted | Self-val. | Coverage | Self-val. (judged) |
|---|---:|---:|---:|---:|---:|
| strip_string | 28,570 | 27,190 | 95.2% | 100.0% | 95.2% |
| sympy_cascade | 31,266 | 27,299 | 87.3% | 87.3% | 100.0% |
| mathverify_latex | 31,266 | 24,981 | 79.9% | 100.0% | 79.9% |
| mathverify_expr | 22,953 | 12,355 | 53.8% | 100.0% | 53.8% |

*Self-validation: acceptance of certified-equivalent variants, in-contract only. Self-val. is over all inputs; Coverage is the fraction on which the verifier returned a verdict at all, and Self-val. (judged) restricts to those. Spread: 41.3 points.*


### Table 2: Error mass share

| Verifier | Stratum | Failures | Share | from error |
|---|---|---:|---:|---:|
| mathverify_expr | S6 whitespace | 7,852 | 74.1% | 0.0% |
| mathverify_expr | S5 math-mode | 2,417 | 22.8% | 0.0% |
| mathverify_expr | S2 frac/decimal | 329 | 3.1% | 0.0% |
| mathverify_latex | S6 whitespace | 5,846 | 93.0% | 0.0% |
| mathverify_latex | S10 sets | 238 | 3.8% | 0.0% |
| mathverify_latex | S4 delimiters | 200 | 3.2% | 0.0% |
| mathverify_latex | S7 sqrt/exponent | 1 | 0.0% | 0.0% |
| strip_string | S6 whitespace | 694 | 50.3% | 0.0% |
| strip_string | S2 frac/decimal | 438 | 31.7% | 0.0% |
| strip_string | S7 sqrt/exponent | 142 | 10.3% | 0.0% |
| strip_string | S5 math-mode | 106 | 7.7% | 0.0% |
| sympy_cascade | S14 unreduced | 2,062 | 52.0% | 100.0% |
| sympy_cascade | S6 whitespace | 694 | 17.5% | 100.0% |
| sympy_cascade | S10 sets | 634 | 16.0% | 100.0% |
| sympy_cascade | S2 frac/decimal | 330 | 8.3% | 100.0% |
| sympy_cascade | S7 sqrt/exponent | 142 | 3.6% | 100.0% |
| sympy_cascade | S5 math-mode | 105 | 2.6% | 100.0% |

*Error mass share: fraction of in-contract failures by stratum. The final column separates failures caused by execution error from those caused by rejection.*


### Table 3: Per-stratum FN rates

| Stratum | Verifier | n | Judged | FN | 95% CI | Err |
|---|---|---:|---:|---:|---|---:|
| S6 whitespace | mv_expr | 15,704 | 15,704 | 50.0% | [49.2, 50.8] | 0.0% |
| S5 math-mode | mv_expr | 4,951 | 4,951 | 48.8% | [47.4, 50.2] | 0.0% |
| S10 sets | mv_latex | 634 | 634 | 37.5% | [33.9, 41.4] | 0.0% |
| S6 whitespace | mv_latex | 15,704 | 15,704 | 37.2% | [36.5, 38.0] | 0.0% |
| S7 sqrt/exponent | strip | 404 | 404 | 35.1% | [30.7, 39.9] | 0.0% |
| S2 frac/decimal | strip | 1,725 | 1,725 | 25.4% | [23.4, 27.5] | 0.0% |
| S2 frac/decimal | mv_expr | 1,725 | 1,725 | 19.1% | [17.3, 21.0] | 0.0% |
| S4 delimiters | mv_latex | 1,067 | 1,067 | 18.7% | [16.5, 21.2] | 0.0% |
| S6 whitespace | strip | 15,704 | 15,704 | 4.4% | [4.1, 4.8] | 0.0% |
| S5 math-mode | strip | 4,951 | 4,951 | 2.1% | [1.8, 2.6] | 0.0% |
| S7 sqrt/exponent | mv_latex | 404 | 404 | 0.2% | [0.0, 1.4] | 0.0% |
| S2 frac/decimal | mv_latex | 1,725 | 1,725 | 0.0% | [0.0, 0.2] | 0.0% |
| S1 frac dialect | mv_latex | 4,146 | 4,146 | 0.0% | [0.0, 0.1] | 0.0% |
| S14 unreduced | mv_latex | 2,062 | 2,062 | 0.0% | [0.0, 0.2] | 0.0% |
| S9 grouping | mv_expr | 573 | 573 | 0.0% | [0.0, 0.7] | 0.0% |
| S5 math-mode | mv_latex | 4,951 | 4,951 | 0.0% | [0.0, 0.1] | 0.0% |
| S9 grouping | mv_latex | 573 | 573 | 0.0% | [0.0, 0.7] | 0.0% |
| S1 frac dialect | strip | 4,146 | 4,146 | 0.0% | [0.0, 0.1] | 0.0% |
| S4 delimiters | strip | 1,067 | 1,067 | 0.0% | [0.0, 0.4] | 0.0% |
| S9 grouping | strip | 573 | 573 | 0.0% | [0.0, 0.7] | 0.0% |
| S7 sqrt/exponent | sympy | 404 | 262 | 0.0% | [0.0, 1.4] | 35.1% |
| S2 frac/decimal | sympy | 1,725 | 1,395 | 0.0% | [0.0, 0.3] | 19.1% |
| S6 whitespace | sympy | 15,704 | 15,010 | 0.0% | [0.0, 0.0] | 4.4% |
| S5 math-mode | sympy | 4,951 | 4,846 | 0.0% | [0.0, 0.1] | 2.1% |
| S1 frac dialect | sympy | 4,146 | 4,146 | 0.0% | [0.0, 0.1] | 0.0% |
| S4 delimiters | sympy | 1,067 | 1,067 | 0.0% | [0.0, 0.4] | 0.0% |
| S9 grouping | sympy | 573 | 573 | 0.0% | [0.0, 0.7] | 0.0% |
| S10 sets | sympy | 634 | 0 | n/a | n/a | 100.0% |
| S14 unreduced | sympy | 2,062 | 0 | n/a | n/a | 100.0% |

*Certified false-negative rates by stratum and verifier, in-contract only, with Wilson score intervals. FN is computed over verdicts actually returned; cells with no verdicts report n/a. Err gives the execution-error rate.*


### Table 4: Off-by-one by magnitude

| Magnitude | n | mv_expr | mv_latex | strip | sympy |
|---|---:|---:|---:|---:|---:|
| <10 | 20 | 0.0% | 0.0% | 0.0% | 0.0% |
| 10-100 | 134 | 0.0% | 0.0% | 0.0% | 0.0% |
| 100-1k | 560 | 0.0% | 0.0% | 0.0% | 0.0% |
| 1k-10k | 367 | 0.0% | 0.0% | 0.0% | 0.0% |
| 10k-100k | 131 | 0.0% | 0.0% | 0.0% | 100.0% |
| >100k | 75 | 0.0% | 0.0% | 0.0% | 100.0% |

*Off-by-one acceptance by gold magnitude, over verdicts actually returned. A deterministic step reflects scale-invariant relative tolerance.*


### Table 5: Cross-verifier disagreement

|  | mv_expr | mv_latex | strip | sympy |
|---|---:|---:|---:|---:|
| mv_expr | --- | 49.9% | 48.0% | 53.4% |
| mv_latex | 49.9% | --- | 31.4% | 22.0% |
| strip | 48.0% | 31.4% | --- | 0.4% |
| sympy | 53.4% | 22.0% | 0.4% | --- |

*Pairwise disagreement on certified-equivalent pairs, computed only over pairs where both verifiers returned a verdict.*


### Table 6: Contract-dependent acceptance

| Input class | n | mv_expr | mv_latex | strip | sympy |
|---|---:|---:|---:|---:|---:|
| S11 text wrap | 9,980 | 28.2% | 39.6% | 48.9% | 100.0% |
| S12 units | 2,782 | 50.0% | 100.0% | 100.0% | 100.0% |
| S13 percent | 20 | 0.0% | 100.0% | 0.0% | 0.0% |
| S3 boxing | 19,952 | 8.0% | 75.1% | 0.0% | n/a |
| S8 scientific | 326 | 0.0% | 100.0% | 0.0% | n/a |

*Acceptance on contract-dependent input classes, over verdicts actually returned. These are undocumented contract differences, not defects.*


### Table 7: Out-of-contract

| Stratum | Verifier | n | Rejection | Err |
|---|---|---:|---:|---:|
| S10 sets | strip_string | 634 | 100.0% | 0.0% |
| S14 unreduced | mathverify_expr | 2,062 | 100.0% | 0.0% |
| S14 unreduced | strip_string | 2,062 | 100.0% | 0.0% |
| S10 sets | mathverify_expr | 634 | 97.5% | 0.0% |
| S1 frac dialect | mathverify_expr | 4,146 | 93.8% | 0.0% |
| S4 delimiters | mathverify_expr | 1,067 | 87.1% | 0.0% |
| S7 sqrt/exponent | mathverify_expr | 404 | 31.4% | 0.0% |

*Out-of-contract behaviour: strata a verifier does not claim to handle. Reported for completeness; not counted as defects.*
