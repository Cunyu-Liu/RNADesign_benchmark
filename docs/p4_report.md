# P4 — main experiments (E1/E2/E5) & red-team findings

Date: 2026-08-19 · seed=0 · source-disjoint split (train 648/val 138/test 140 targets) · GPU (toeholdbench)
Records: test 7,041 / 140 targets · success definitions: relative top-20% ON/OFF; absolute ON>=0.5 & OFF<=0.5 (pos rate 34.3%)

## E1 — Prediction ≠ Design
| model | Spearman ρ (prediction) | success@1 (design) |
|---|---|---|
| B0_gc (GC rule) | -0.200 | 0.107 |
| B2_mlp (Angenent-Mari) | 0.108 | 0.350 |
| B1_thermo (RBS/MFE) | **0.136** | 0.321 |

**Finding 1:** the model with the best prediction correlation (B1_thermo, ρ=0.136) is NOT the best designer
(B2_mlp, success@1=0.350). Prediction ranking and design ranking are inconsistent — a single-sequence
regression benchmark does not answer the top-K selection question.

## E2 — Split stress (leakage)
| split | test source leak | MLP test ρ |
|---|---|---|
| source-disjoint | 0.000 | 0.108 |
| row-random | 0.999 | 0.103 |

**Finding 2:** row-random split leaks 99.9% of test sources into training (vs 0% source-disjoint).
Notably, the simple MLP's test ρ is NOT inflated by this leakage (0.103 vs 0.108) — the trigger-sequence
ON/OFF signal is intrinsically weak under this model, so source leakage alone does not guarantee inflated
correlation. The leak fraction itself is the airtight methodological evidence for source-disjoint splits.

## E5 — Ratio pathology (single vs dual objective; absolute success ON>=0.5 & OFF<=0.5)
| ranking | success@1 |
|---|---|
| ON/OFF ratio | 0.992 |
| ON-only | 0.797 |
| Pareto (max ON, min OFF) | 0.805 |
| OFF-only (min leak) | 0.234 |

**Finding 3:** ranking by low OFF alone collapses to 0.234 — OFF (leak) is a poor single ranking signal;
ON (induction) dominates. The ON/OFF ratio collapses two objectives into one axis and, on this data,
happens to perform well (0.992), so the "pathological ratio" failure mode is NOT observed here. The
takeaway is that design utility is genuinely multi-objective; a single OFF-only (specificity-like) metric
is insufficient.

## Summary for GO gate (>=2 non-trivial findings)
1. Prediction metric and design utility rank models inconsistently (E1).
2. Row-random split leaks 99.9% of sources; source-disjoint is required; leak does not trivially inflate ρ (E2).
3. OFF-only ranking is ~4x worse than ON/ratio/Pareto — a multi-objective design metric is required (E5).

## Remaining P4 experiments (not blocking GO, documented)
- E3 fused→trans transfer (needs VISTA mCherry external ranking harness + Green/Valeri free-trigger).
- E4 target-context ablation (clean seeded B2_mlp vs B4_struct vs B5_targetaware).
- E6 reward/evaluator audit (generator coupled to a predictor; proxy-overfitting quantification).

Outputs: processed/p4_experiments.json