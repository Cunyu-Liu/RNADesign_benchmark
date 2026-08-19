# ToeholdDesignBench: A Target-Aware, Source-Isolated Benchmark for Toehold RNA Sensor Design Utility

*(paper draft — P5 deliverable; figures/tables reference the processed/ JSON artifacts)*

## Abstract
Existing evaluations of toehold-switch design systems treat the problem as single-sequence function
regression (predict ON/OFF of a switch, then rank by R²). We show this conflates *prediction* with
*design*. We rebuild the Angenent-Mari 2020 91,534-switch dataset (97,436 raw records; 23 viral genomes +
908 human-transcription-factor-derived targets) into target-level candidate sets, reconstruct absolute
window coordinates (94.9% of records), and define a source-disjoint, top-K design-utility benchmark.
Three core findings: (1) prediction correlation and per-target top-K utility rank models inconsistently;
(2) random row splits leak 99.9% of test sources and do not trivially inflate prediction correlation;
(3) fused-context rankings do not transfer to full-length-target contexts (transfer ρ ≈ 0 or negative),
even for the traditional thermodynamic tool. The benchmark is released as a static, versioned, runnable
package.

## 1. Introduction
Toehold switches are de-novo prokaryotic riboregulators that activate translation on a programmable
trans-RNA trigger [Green 2014]. High-throughput flow-seq produced 91,534 paired ON/OFF measurements
[Angenent-Mari 2020], enabling deep sequence-to-function predictors (R² 0.43–0.70) and downstream
target-aware design methods [Toehold-VISTA 2026]. Yet a central question remains: does prediction
accuracy translate to *per-target top-K candidate selection under a fixed experiment budget*? We argue
the field lacks a benchmark that (a) groups candidates by full target/source, (b) isolates sources across
splits, (c) measures design utility (success@K / regret / ON–OFF Pareto), and (d) separates fused-trigger
from full-length-target contexts.

## 2. Benchmark design
- **Task (R1):** given a target + fixed first-gen-30nt architecture + budget K, rank its candidate trigger
  sites so the top-K contains high-ON / low-OFF, grammar-valid switches.
- **Splits:** source-disjoint 70/15/15, target never crosses train/test (overlap = 0).
- **Metrics:** primary success@1 (pre-registered success: ON ≥ 0.5 and OFF ≤ 0.5); secondary success@3/5,
  NDCG@10, normalized regret, ON/OFF Pareto front size; target-level bootstrap CI.
- **Baselines (6 families):** B0 random/GC rule; B1 traditional thermodynamic (RBS-calculator + MFE);
  B2 Angenent-Mari MLP/CNN; B3 STORM/NuSpeak-equivalent deep predictor; B4 SANDSTORM-equivalent
  sequence+structure joint; B5 VISTA-like structure-rich ranker.

## 3. Data & provenance
97,436 raw rows (83 columns) → 92,731 canonical virus+TF records (931 targets; median 53 candidates).
Full source sequences resolved via NCBI (BLAST self-validated): 23 "viruses" include non-obvious taxa
(Tai Forest ebolavirus, Ikoma lyssavirus, HIV-2, Leishmania RNA virus LRV2, Saffold cardiovirus, bat
astrovirus). 94.9% of triggers mapped to absolute coordinates; residual fail-closed excluded with ledger.
QC: paper's Supplementary Table S1 selects QC2 as final filter (91,534 = QC2 paired).

## 4. Experiments & findings
### E1 — Prediction ≠ Design
Best prediction (B1_thermo ρ=0.136) ≠ best designer (B2_mlp success@1=0.350). Under source-disjoint
split all models have low prediction ρ (~0.1) yet design utility has headroom (0.35 vs random 0.24).

### E2 — Split stress
Row-random split leaks 99.9% of test sources (vs 0.000 source-disjoint). The simple MLP's test ρ is *not*
inflated by leakage (0.103 vs 0.108) — trigger-sequence ON/OFF signal is intrinsically weak; the leak
fraction itself is the airtight evidence that source-disjoint splits are required.

### E3 — Fused → trans/full-target transfer
A model trained on fused 91k transfers to VISTA mCherry full-target (189 tiles) with ρ = -0.07/-0.20;
the traditional tsgen2 tool is anti-correlated (ρ = -0.23); only GC content transfers (ρ = +0.30).
Fused-context ranking does not generalize to real trans/full-target conditions.

### E4 — Target-context ablation
Naively concatenating structure features (MFE/RBS) into the deep MLP *degrades* design utility
(seq-only 0.350 → seq+structure 0.214/0.250); the thermodynamic baseline is strong alone (0.321).

### E5 — Ratio pathology (multi-objective)
Ranking by low OFF alone collapses success@1 to 0.234, vs ON-only 0.797 / Pareto 0.805 / ratio 0.992:
design utility is genuinely multi-objective; a single specificity-like OFF metric is insufficient.

## 5. Discussion & allowed claims
Per R1-only evidence, we claim a *source-isolated fused-context candidate-site ranking benchmark*.
We do NOT claim real trans sensing, de-novo redesign, or specificity (OFF = no-cognate leak). The fused→
full-target transfer gap motivates R2 (external full-target evaluation) and, ultimately, P1 prospective
validation as the only route to de-novo design claims.

## 6. Availability
Static versioned release: `canonical_records.parquet`, `split_manifests`, `runner.py`, metrics module with
unit tests, `datasheet`, `leaderboard_schema`, license matrix, exclusion ledger, sha256 manifest.
Reproduce: `python src/runner.py --method B1_thermo` (built-in) or `--scores scores.csv` (external).

## References
[1] Green et al., Cell 2014; [2] Angenent-Mari et al., Nat Commun 2020; [3] Valeri et al., Nat Commun 2020;
[4] Robson & Green, NAR 2026 (Toehold-VISTA); [5] Ren et al., NeurIPS D&B 2024 (BEACON).