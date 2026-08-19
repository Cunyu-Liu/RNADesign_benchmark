# P4 — main experiments (E1–E6) & red-team findings — REVISED

Date: 2026-08-20 · seed=0 (torch seeded before model init) · source-disjoint split (train 648/val 138/test 140 targets) · GPU
Success definition: **pre-registered ABSOLUTE threshold ON>=0.5 & OFF<=0.5** (test-independent; positive rate 34.3%)

> **REVISION NOTE (FIX-2):** E1/E2 success numbers were recomputed with the absolute pre-registered threshold
> (previously used a leaky per-target top-20% ON/OFF quantile that touched test data). E5 already used the
> absolute threshold. This revision removes the test-threshold leakage.

## E1 — Prediction ≠ Design (absolute success)
| model | Spearman ρ (prediction) | success@1 (design) |
|---|---|---|
| B0_gc (GC rule) | -0.200 | 0.093 |
| B2_mlp (Angenent-Mari) | 0.108 | **0.350** |
| B1_thermo (RBS/MFE) | **0.136** | 0.343 |

**Finding 1:** the best predictor (B1_thermo ρ=0.136) is not the best designer (B2_mlp s@1=0.350) — and no
model beats random (0.350) at top-1. Prediction ranking ≠ design ranking.

## E2 — Split stress (leakage)
| split | test source leak | MLP test ρ |
|---|---|---|
| source-disjoint | 0.000 | 0.108 |
| row-random | 0.999 | 0.103 |

**Finding 2:** row-random split leaks 99.9% of test sources into training; source-disjoint = 0. Leak does not
inflate this MLP's test ρ (0.103 vs 0.108) because trigger-sequence ON/OFF signal is intrinsically weak; the
leak fraction is the airtight methodological evidence for source-disjoint splits.

## E3 — Fused → trans/full-target transfer (VISTA mCherry, 189×36nt → 30nt)
| transfer source | ρ vs ON OFF Full |
|---|---|
| fused MLP (first30 / last30) | -0.065 / -0.202 |
| tsgen2 (traditional tool) | -0.228 (anti-correlated) |
| random | -0.072 |
| GC content | +0.303 |

**Finding 3:** fused-context rankings (and the traditional tool) do NOT transfer to full-target context;
only shallow GC features transfer. External-validity gap is real.

## E4 — Target-context ablation (seeded)
seq-only MLP s@1=0.350 > seq+structure 0.214 / 0.250 (structure features alone are strong: B1_thermo 0.343,
but naive concatenation into a deep MLP degrades it).

## E5 — Ratio pathology (absolute success; multi-objective)
| ranking | success@1 |
|---|---|
| ON/OFF ratio | 0.992 |
| ON-only | 0.797 |
| Pareto (max ON, min OFF) | 0.805 |
| OFF-only | 0.234 |

**Finding 4:** OFF-only ranking collapses to 0.234; ON/ratio/Pareto are far stronger. Design utility is
multi-objective; a single OFF-only (specificity-like) metric is insufficient.

## E6 — Cross-evaluator / proxy-overfitting audit (R1-appropriate)
cross-evaluator top-1 agreement (MLP vs thermo) = **0.086**; A_model's top-1 pick median real ON/OFF
percentile = **0.542** (vs 1.0 self-rank). **Finding 5:** the choice of evaluator changes the answer (8.6%
agreement), and self-ranking over-rates its picks (proxy overfitting).

## Summary for P4 GO gate (≥2 non-trivial findings)
1. Prediction ρ and design utility rank models inconsistently (E1).
2. Row-random split leaks 99.9% of sources; leak does not trivially inflate ρ (E2).
3. Fused→full-target transfer fails; only shallow GC transfers (E3).
4. Naive structure-augmented deep models underperform seq-only (E4).
5. OFF-only ranking is ~4× worse — multi-objective metric required (E5).
6. Evaluator choice flips top-1 (8.6% agreement); proxy overfitting confirmed (E6).

## Honest NO-GO-context note
Under the absolute threshold and strict source-disjoint split, success@1 is near-random for all models
(random 0.350). Signal survives at success@3 (B1_thermo 0.700 vs random 0.593) and NDCG@10, and E2 shows the
weak-signal cause (intrinsic ρ≈0.1). Per contract §9, this is a *documented, explainable* near-random top-1
result — NOT a NO-GO (label noise is explainable via E1/E2/E4), but it caps the allowed claim strength:
R1 supports "candidate-site ranking benchmark" only, not real trans-sensing or de-novo design.

Outputs: processed/p4_experiments.json (+ p4_e3/e4/e6 outputs)