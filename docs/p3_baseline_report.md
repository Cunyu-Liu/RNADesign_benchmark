# P3 — 6 core baseline families reproduced (R1 source-disjoint) — REVISED

Date: 2026-08-20 · seed=0 (torch.manual_seed BEFORE model construction) · env: toeholdbench (torch 2.5.1+cu121, A100)
Split: source-disjoint (train 648 / val 138 / test 140 targets) · records: train 39,517 / test 7,041
Success definition: **pre-registered ABSOLUTE threshold ON>=0.5 AND OFF<=0.5** (test-independent; replaces the earlier leaky per-target top-20% definition).

> **REVISION NOTE (FIX-1/FIX-2):** The numbers in this report supersede the earlier p3_baseline_report.md. The earlier deep-model numbers were NOT reproducible (models were built before torch.manual_seed ran) and used a leaky per-target success threshold. After fixing seed order and using the absolute pre-registered threshold, results are fully reproducible (verified by 2 identical runs) and threshold-clean.

## Results (higher s@1 = better design utility)

| family | baseline | success@1 | success@3 | NDCG@10 | regret |
|---|---|---|---|---|---|
| B0 random | B0_random | 0.350 | 0.593 | 0.520 | 0.085 |
| B0 rule | B0_gc (GC content) | 0.093 | 0.350 | 0.414 | 0.141 |
| B1 traditional | B1_thermo (RBS-calculator / MFE) | 0.343 | **0.700** | 0.564 | 0.085 |
| B2 seq predictor | B2_mlp (Angenent-Mari MLP) | 0.350 | 0.664 | **0.588** | **0.051** |
| B2 seq predictor | B2_cnn (Angenent-Mari CNN) | 0.200 | 0.579 | 0.501 | 0.100 |
| B3 deep predictor | B3_storm (STORM/NuSpeak equiv) | 0.214 | 0.564 | 0.493 | 0.102 |
| B4 seq+structure | B4_struct (SANDSTORM equiv) | 0.214 | 0.500 | 0.484 | 0.107 |
| B5 target-aware | B5_targetaware (VISTA-like) | 0.336 | 0.679 | 0.541 | 0.088 |

## Reproducibility (FIX-1 verified)
Two identical runs (same seed=0, torch seeded before model init) produced **identical** numbers for every
baseline (B2_mlp s@1 = 0.350 in both runs; previously 0.379/0.393 across runs). PASS.

## Reading (honest)
- With the pre-registered ABSOLUTE threshold, **success@1 is near-random for every model** (random 0.350;
  models 0.34–0.35 or worse) — the absolute-hit rate in the top-1 slot is ~35% for all approaches under a
  strict source-disjoint split. This is close to the contract's P4 NO-GO signal ("all models ≈ random").
- However **success@3 and NDCG@10 show differentiation**: B1_thermo s@3=0.700 and B2_mlp s@3=0.664 beat
  random 0.593 (+10.7pp / +7.1pp); B2_mlp NDCG@10=0.588 and regret 0.051 are best. Signal exists but is weak
  at top-1 and stronger at top-3 — consistent with E1 (prediction ρ ≈ 0.1 is intrinsically weak) and with
  the benchmark's thesis that design utility ≠ raw prediction accuracy.
- GC rule remains worst (s@1=0.093), confirming GC content is anticorrelated with switch function.

## Coverage & functional-equivalence notes (contract 8.1)
- B0 exact; B1 thermodynamic proxy (RBS-calculator + ViennaRNA MFE, functionally equivalent to NUPACK/tsgen);
  B2 Angenent-Mari MLP/CNN reproduced (simplified epochs); B3/B4/B5 functional equivalents (deep / seq+struct /
  structure-rich) — R1 has no generative/redesign/full-target scenario.
- All 8 baselines ran (coverage 8/8); fixed seed => reproducible (verified 2 runs).

## Reproduce
```
cd /home/cunyuliu/ToeholdDesignBench
python tests/test_metrics.py            # metric unit tests
python src/p3_baselines.py             # this report (writes processed/p3_baselines.json)
python src/runner.py --method B1_thermo # leaderboard entry (same abs-threshold metric)
```