# ToeholdDesignBench Task Contract v0.2

Status: controlling project contract from 2026-08-21. The original v0.1 contract,
phase reports, and handover document are historical records. If they conflict with
this file, v0.2 controls.

## Evidence tracks

### R1 — canonical target ranking

- Dataset used by the main ranking track: 52,861 `admitted_paired` records from
  926 label-bearing targets. The retained canonical table has 931 targets in
  total; do not describe R1 as a 91,534-row main leaderboard.
- Label: signed `ON - OFF`, including negative values.
- Split: fixed source-disjoint target manifest; a target cannot cross splits.
- Input regimes: local sequence and local sequence plus local biophysical features.
- Primary metric: success@1 with the frozen absolute threshold ON ≥ 0.5 and OFF ≤ 0.5.
- Secondary metrics: success@3/5, NDCG@10, normalized regret@10, and global
  Pareto-front coverage@10.
- Statistics: target is the unit. Report target-bootstrap intervals and paired
  target-bootstrap method differences. Report targets with no feasible candidate.
- Learned baselines use seeds 0–4; the paper-facing ranking uses their mean score.

### R2 — BEACON source reconstruction

- Dataset: BEACON authoritative mapping, 91,534 rows, 23 virus and 905 TF sources.
- BEACON `ON_OFF` is its own normalized label and is not merged with canonical
  signed `ON - OFF`.
- Tracks: stratified source-disjoint TF+virus ranking and TF-to-virus domain OOD.
- The published row split is not evidence of unseen-target generalization.
- Report within-target Spearman, NDCG@10, and normalized regret; do not transfer
  canonical absolute success thresholds.

### R3 — VISTA paired context stress test

- Dataset: 189 sites from one mCherry target and one study.
- Compare paired truncated and full-target measurements for the same sites.
- Report score correlation in both contexts, their difference, top-10 overlap,
  and label rank shift.
- Site-bootstrap intervals describe uncertainty within this single target only.

## Implementation corrections required by v0.2

1. CNN inputs use true `(N, 4, L)` nucleotide channels.
2. Canonical regressors preserve signed `ON - OFF` labels.
3. Confidence intervals resample targets; per-target percentiles are not CIs.
4. Oracle diagnostics retain every test target and are never presented as methods.
5. Pareto reporting uses global-front coverage or a declared deterministic rule.
6. E4 is named local biophysical feature concatenation, not target-context ablation.
7. E6 is evaluator disagreement, not proxy overfitting.
8. The runner and schema expose the same metrics and target accounting.

## Allowed claims

- Prediction and per-target candidate-selection utility are distinct evaluation axes.
- Source-disjoint evaluation is necessary to test unseen-target generalization.
- Repository baselines can be compared under the same candidates, inputs, and budget.
- VISTA quantifies a context shift for mCherry in the evaluated study.

## Prohibited claims

- Row leakage necessarily inflates every model's performance.
- The 52,861-row canonical and 91,534-row BEACON labels form one common scale.
- One mCherry target establishes universal full-target transfer behavior.
- B3/B4/B5 are complete reproductions of named published systems.
- OFF is specificity, or retrospective ranking proves de novo/trans-sensing validity.

## Paper gate

The project is ready for submission only when the corrected core run completes,
all paper numbers are generated from its v0.2 outputs, the manuscript states the
single-target and proxy-baseline limitations, and a final three-reviewer audit has
no blocking technical finding. “Ready for submission” is not a guarantee of review
outcome or acceptance.
