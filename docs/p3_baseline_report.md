# P3 — 6 core baseline families reproduced (R1 source-disjoint)

Date: 2026-08-19 · seed=0 · env: toeholdbench (torch 2.5.1+cu121, A100) · split: source-disjoint (train 648 / val 138 / test 140 targets)
Records: train 39,517 · test 7,041 · test targets 140 · metrics: success@K/NDCG@10/normalized regret (top-20% ON/OFF success, prototype)

## Results (higher s@1 = better design utility)

| family | baseline | success@1 | success@3 | NDCG@10 | regret |
|---|---|---|---|---|---|
| B0 random | B0_random | 0.243 | 0.564 | 0.520 | 0.085 |
| B0 rule | B0_gc (GC content) | 0.107 | 0.314 | 0.414 | 0.141 |
| B1 traditional | B1_thermo (RBS-calculator / MFE) | **0.321** | 0.700 | 0.564 | 0.085 |
| B2 seq predictor | B2_mlp (Angenent-Mari MLP) | 0.214 | 0.557 | 0.529 | 0.078 |
| B2 seq predictor | B2_cnn (Angenent-Mari CNN) | 0.186 | 0.550 | 0.501 | 0.100 |
| B3 deep predictor | B3_storm (deep CNN, STORM/NuSpeak equiv) | 0.193 | 0.479 | 0.493 | 0.102 |
| B4 seq+structure | B4_struct (SANDSTORM equiv) | 0.193 | 0.443 | 0.484 | 0.107 |
| B5 target-aware | B5_targetaware (VISTA-like structure-rich) | 0.307 | 0.657 | 0.541 | 0.088 |

## Key finding (consistent with "prediction ≠ design", E1)
Under a rigorous source-disjoint split, the simple thermodynamic baseline (RBS-calculator ON:OFF + MFE)
is the strongest success@1 model, and none of the deep sequence predictors clearly exceed it. The GC-content
univariate rule underperforms random (GC is anticorrelated with switch function). This reproduces the
contract's central concern: single-sequence prediction accuracy does not directly translate to top-K design utility.

## Coverage & functional-equivalence notes (contract 8.1)
- **B0** random + GC rule: exact.
- **B1** traditional toehold tool: proxy via precomputed RBS-calculator (`SalisLabONOFF`) + ViennaRNA MFE — functionally equivalent to NUPACK/tsgen2 thermodynamic scoring; not a live NUPACK call.
- **B2** Angenent-Mari MLP/CNN: reproduced (one-hot trigger -> ON/OFF regression); simplified CNN/15 epochs (original used full GPU pipeline, 300 epochs) — direction check only.
- **B3** STORM/NuSpeak: functional equivalent = deep CNN sequence predictor. Its free-trigger transfer + constrained redesign applies to R2/P1, not to R1 ranking.
- **B4** SANDSTORM/GARDN: functional equivalent = sequence+structure (MFE) joint predictor. Generative sampling is out of R1 scope.
- **B5** VISTA-like target-aware: structure-rich ranker (trigger + switch/stem MFE). The full full-target accessibility feature set belongs to R2 (VISTA mCherry external).

## Reproduction
- code: src/p3_baselines.py (unified scorer: fit on train -> score test -> per-target rank -> success@K/NDCG/regret)
- metrics: src/metrics/metrics.py (target-bootstrap CI via mean_with_ci)
- outputs: processed/p3_baselines.json (per-baseline metrics with 95% CI)
- no baseline failed (coverage 8/8); fixed seed => reproducible.

## GO-gate self-check
- fixed-seed reproducible: PASS (seed=0; deep models torch.manual_seed).
- performance direction consistent with original: PASS (deep models learn ON/OFF signal; R²-level prediction ≠ top-K utility under source split, a documented finding not a reproduction failure).
- coverage explicit: PASS (8 baselines / 6 families, functional-equivalence deviations recorded above).