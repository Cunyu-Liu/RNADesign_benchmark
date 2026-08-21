# P4 — v0.1 experiments (archived; superseded by v0.2)

> **Do not cite the numerical claims below.** They predate the corrected channel
> encoding, signed-label training, matched-size split comparison, target-bootstrap
> method differences, unconditional oracle accounting, and paired VISTA analysis.
> `src/revision_analysis.py`, `src/beacon_target_benchmark.py`, and
> `src/vista_paired_context.py` generate the replacement `_v02` evidence.

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

## Unified table: prediction quality vs design utility (T5)
One table combining the two axes on the same source-disjoint test split
(`processed/p5_unified_table.json`, `src/p5_unified_table.py`; design values = P3; prediction rho held-out):

| method | prediction ρ (held-out) | success@1 | success@3 | NDCG@10 | regret |
|---|---|---|---|---|---|
| B0_random | -0.002 | 0.350 | 0.593 | 0.520 | 0.085 |
| B0_gc | -0.200 | 0.093 | 0.350 | 0.414 | 0.141 |
| B1_thermo | **+0.136** | 0.343 | **0.700** | 0.564 | 0.085 |
| B2_mlp | +0.110 | 0.350 | 0.664 | **0.588** | **0.051** |
| B2_cnn | n/a | 0.200 | 0.579 | 0.501 | 0.100 |
| B3_deep | n/a | 0.214 | 0.564 | 0.493 | 0.102 |
| B4_struct | n/a | 0.214 | 0.500 | 0.484 | 0.107 |
| B5_structrank | n/a | 0.336 | 0.679 | 0.541 | 0.088 |

**Reading (honest inference, do not over-read ties):** the best *predictor* (B1_thermo, ρ=0.136) is a
*tied* best at success@1 (0.343 vs B2_mlp/random 0.350) — i.e., the top-1 design row is near-random for
everyone (see appendix T4). The signal that *does* separate methods appears at success@3/NDCG@10, where
B2_mlp leads (NDCG@10 = 0.588, regret 0.051) and B1_thermo leads success@3 (0.700). Prediction ρ and design
rank correlate only weakly (Spearman 0.32 over methods with both), supporting E1: reporting raw regression
accuracy is not a reliable proxy for ranking/design utility. Because s@3/NDCG separate methods while s@1
does not, we recommend reporting the top-1 absolute-hit result alongside s@3/NDCG, and we do not claim any
method "wins" at the strict top-1 pooled level.

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
