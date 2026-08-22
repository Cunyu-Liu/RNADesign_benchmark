# ToeholdDesignBench v0.3.0 — Manuscript Draft

> Working draft generated from frozen run-directory artifacts. All numbers
> trace to `/mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/` outputs. Numbers
> marked [PENDING] await the completion of in-flight runs. Per the v0.3.0
> contract, no number in this draft may be replaced by a value computed
> under a different protocol; the draft structure follows contract §9
> Batch 4 item 5.

## Title (working)

Target-grouped evaluation and objective-matched training for toehold switch
candidate selection: a re-audit and modern re-benchmark of the
Angenent–Mari 2020 toehold dataset

## Abstract (draft)

Computational ranking of candidate toehold switches for a fixed RNA target
underpins every published toehold-design pipeline, yet the field's reference
benchmark (the Angenent–Mari 2020 dataset, 92,731 constructs across 931
targets) has been evaluated under protocols that mix train and test targets,
weight rows rather than targets, and fix decision thresholds after viewing
results. We rebuild this benchmark under a frozen protocol: exact and
reverse-complement trigger closure plus accession- and homology-based
target clustering with verified zero cross-fold leakage; per-target
equal-weight ranking metrics with analytic random baselines and analytic
tie handling; and a single evaluator with cluster-level bootstrap and
sign-flip statistics. Under this protocol we re-evaluate corrected
biophysical baselines, official reproductions of SANDSTORM and the Valeri
CNN, input-masking ablations of the BEACON 148-nt constructs at matched
capacity, and a target-balanced LambdaRank objective (TBLR) across matched
backbones. [PENDING: primary TBLR-SANDSTORM contrast sentence.] A controlled
leakage experiment quantifies the causal cost of same-target training
contamination (+0.034 NDCG@10). On the independent VISTA mCherry track, the
official PLS-DA ranking attains NDCG@10 0.676 [bootstrap CI 0.534, 0.825]
against an analytic random baseline of 0.263, while the prior tsgen2 ranking
falls below random under its documented convention. [PENDING: transfer-model
VISTA sentence.] All data identities, mappings, exclusions, and statistical
procedures are pre-frozen and auditable.

## 1. Introduction

- Toehold switches (Green et al. 2014) are the workhorse design target for
  RNA diagnostics; design pipelines must RANK candidate switches for a fixed
  target RNA under an experimental budget.
- The Angenent–Mari 2020 dataset is the largest public toehold measurement
  set and underpins a series of downstream ML papers. Its two public views
  (the "canonical" CSV and the BEACON 2024 release) are the SAME experiment
  with different label processing; treating them as independent datasets
  overstates external evidence.
- Prior evaluations of this dataset: (i) split targets without closing
  exact/reverse-complement trigger duplicates (46 identical 30-nt triggers
  crossed the v0.2.1 split); (ii) trained row-weighted pointwise objectives
  while evaluating per-target (one smallpox target contributes 33.15% of
  training rows); (iii) selected success thresholds post hoc; (iv) resolved
  BEACON's ambiguous mappings silently; (v) sliced the BEACON input at
  [0:30] instead of the true trigger [3:33].
- We ask the contract's frozen central question: in an evaluation with
  closed repeats, homology-clustered folds, and target-equal weighting,
  does a target-balanced ranking objective improve candidate selection
  across modern backbones, and do gains persist on an independent study's
  native task?

## 2. Data lineage and registry

- Study identity: canonical and BEACON share `study_id=angenent_mari_2020`
  as two label views; their label scales are never pooled
  (registry_v3, 931 targets, 908 clusters after union closure).
- Closure rules (all tested, all pass): same accession; exact or RC
  30-nt trigger; overlapping candidate intervals; >=80%/80% 512-nt context
  homology via k=17 seed chaining. Cross-fold exact/RC trigger overlap = 0;
  clusters never cross folds.
- 5-fold group-stratified split: 186/186/186/186/187 targets per fold
  (registry_v2's collapsed split retained on disk as a failed-run audit
  record).
- context512 rebuilt from frozen accession versions: 87,989/92,731 records
  resolved (N+mask boundaries; unverifiable records marked unresolved).
- BEACON label view: trigger fixed at [3:33] (agrees with the authoritative
  canonical trigger on 36,104/36,104 linked rows); mapping ledger with
  explicit unique/ambiguous/unresolved status (87,829 unique; 3,705
  unresolved random rows; ambiguous rows excluded from the main analysis).
- The 140-target legacy test set is demoted to `legacy_development`
  (post-hoc 0.5/0.5 threshold; never used in confirmatory statements).

## 3. Evaluation protocol

- Primary endpoint: mean per-target NDCG@10; relevance = ON−OFF minus
  within-target minimum; linear nonnegative gains; targets with >=2
  candidates and ideal DCG>0 (917 eligible targets, 52,852 rows).
- Secondary: regret@{1,3,5,10}; target-level Spearman; success@k over the
  full 5x5 threshold surface (legacy 0.5/0.5 demoted to continuity cell).
- Random baselines are analytic per-target expectations; ties at cutoffs
  are analytic expectations over equiprobable permutations (single
  evaluator kernel; 29 unit tests on hand-enumerated cases).
- Statistics: 5 training seeds averaged before metrics; 5,000-replicate
  paired target-cluster bootstrap; 50,000-replicate cluster-level
  sign-flip with add-one correction; Holm correction over exactly the two
  pre-declared secondary contrasts.
- Primary contrast: TBLR-SANDSTORM vs matched pointwise SANDSTORM.
  Secondaries: TBLR-CNN vs pointwise CNN; TBLR-RNAElectra vs pointwise
  RNAElectra.

## 4. Corrected baselines (frozen results)

Biophysical baselines with train-fold-only preprocessing (salis log1p +
standardize, median imputation + missingness indicators; Salis never
backfills to MFE), 12-config inner-CV per variant, target-balanced weights:

| Method | NDCG@10 | random | Spearman |
|---|---|---|---|
| LightGBM combined | 0.7627 | 0.6427 | 0.336 |
| LightGBM biophysics | 0.7440 | 0.6427 | 0.301 |
| Ridge thermodynamic | 0.7391 | 0.6427 | 0.317 |
| LightGBM 4-mer sequence | 0.7255 | 0.6427 | 0.229 |
| GC baseline | 0.5708 | 0.6427 | −0.191 |

Combined vs biophysics: +0.0187, CI [0.0129, 0.0243], p = 2e-5. The v0.2.1
claim "biophysics hurts" is overturned: it was an artifact of naive
preprocessing (zero-filled unstandardized salis mixed with negative-scale
MFE).

Official identity reproductions (official code, official 3-fold protocol,
TF 2.11 GPU): SANDSTORM ON R2 0.626 ± 0.013, ON Spearman 0.785 ± 0.009;
Valeri CNN ON R2 0.600 ± 0.004.

## 5. BEACON input-masking ablations (fixed capacity, fold 0)

One fixed-capacity 148-position model; seven input regimes; identical
budget/folds/candidates:

| Variant | NDCG@10 |
|---|---|
| full construct | 0.7730 |
| segment shuffle | 0.7692 |
| trigger-only [3:33] | 0.7642 |
| RC-copy-only [53:83] | 0.7613 |
| template-variable | 0.7598 |
| trigger + RC copy | 0.7567 |
| scaffold-only | 0.7463 |
| analytic random | 0.6296 |

Full vs trigger-only: +0.0088, CI [0.0008, 0.0168], p = 0.065. Segment ORDER
contributes little (shuffle ≈ full). The v0.2.1 "context benefit" was
confounded by capacity (3.54x) and wrong slicing; at matched capacity the
trigger carries most of the signal.

## 6. Controlled leakage experiment

156 candidate-rich fold-0 test targets; fixed seed-frozen 20% evaluation
candidates (identical in both arms); leaky arm adds 15,838 same-target
neighboring windows to training; clean arm adds 15,838
candidate-count-matched, label-quintile-stratified cluster-disjoint
training rows (duplicated upweighting); 5 seeds:

- leaky NDCG@10 = 0.8879
- clean NDCG@10 = 0.8544
- paired difference = +0.0335 (106/156 targets leaky-better)

Same-target contamination causally inflates apparent ranking skill by ~3.4
NDCG points under otherwise identical conditions.

## 7. TBLR objective vs matched pointwise backbones

[PENDING: TBLR-SANDSTORM primary contrast -- tuning 177/180 runs complete;
finals in flight. To be filled from eval_sandstorm_family once all 125
finals land. Fill exactly: table of 5 objectives x NDCG@10, primary
contrast effect + CI + p, seed variation.]

CNN60 backbone (complete, 5 folds x 5 objectives x 5 seeds, 917 targets):

| Objective | NDCG@10 | Spearman |
|---|---|---|
| legacy row-weighted MSE | 0.8332 | 0.486 |
| target-balanced MSE (matched pointwise) | 0.8123 | 0.450 |
| target-balanced dual ON/OFF | 0.8076 | 0.445 |
| full TBLR (LambdaRank@10 + aux) | 0.7998 | 0.429 |
| LambdaRank-only | 0.7941 | 0.407 |
| analytic random | 0.6427 | — |

On the CNN backbone the primary-direction contrast is NEGATIVE
(full_tblr − tb_mse = −0.0125, CI [−0.0160, −0.0089], p = 2e-5). We record
this honestly; the contract's iteration rules forbid re-running favorable
subsets. [PENDING: whether the SANDSTORM backbone reproduces or reverses
this direction; the frozen exit criteria in §12 handle either outcome.]

## 8. Independent external track: VISTA mCherry

189 sites, ONE target (site-level bootstrap CIs only; never extrapolated to
multi-target claims). Official rankings scored under the paper-documented
rank convention (rank 1 = best, per Fig. 5D of the VISTA preprint):

| Method | NDCG@10 (ON/OFF Full) | CI | random |
|---|---|---|---|
| VISTA PLS-DA (Full model) | 0.6760 | [0.5336, 0.8247] | 0.2627 |
| VISTA PLS-DA (Trunc model) | 0.6692 | [0.5300, 0.8336] | 0.2627 |
| tsgen2 (documented convention) | 0.1147 | [0.0596, 0.1702] | 0.2627 |
| tsgen2 (direction-reversed sensitivity) | 0.4246 | [0.2261, 0.6856] | 0.2627 |

The prior tsgen2 ranking falls below the analytic random baseline under its
documented convention -- consistent with the VISTA paper's motivation for
replacing it. [PENDING: transfer-cnn60 row; transfer training in flight,
models frozen on canonical before any external label is read.]

## 9. Reproduction and audit

- Single evaluator kernel (`src/toeholdbench/`); all analyses consume it;
  78 tests green (64 evaluator/registry + 14 TBLR).
- Protocol freeze audit (independent, manifest-based): matched-ablation
  parameter parity; fixed seeds; config selections within the pre-declared
  grid; exact per-fold target AND record coverage (f0 19955 / f1 8619 /
  f2 7736 / f3 7736 / f4 7891 records) -- all completed families PASS.
- All runs under immutable run directories; v0.2.1 artifacts untouched
  (releases/v0.2.1/).

## 10. Limitations and boundaries

- Compute-only reanalysis; no prospective or wet-lab claims.
- VISTA evidence is a single target; architecture-shift analysis
  (crowdsourced 100-regulator preprint) is blocked on data access
  (supplementary gated; no public repo as of 2026-08-22).
- BEACON 2024 LM checkpoints (BEACON-B512, SpliceBERT-MS1024, RNA-FM,
  UTR-LM-MRL) are blocked on network access; these comparators are recorded
  as pending assets rather than silently omitted.
- NUPACK 4 not installed; SANDSTORM reproduction uses the official
  prototype-PPM path (no NUPACK code path exercised).

## 11. Data availability

Canonical CSV (CC BY 4.0, Angenent–Mari 2020), NCBI RefSeq accessions,
VISTA mCherry ranking workbook (AlexGreenLab/vista). Non-redistributable
assets are tracked with acquisition scripts and derived scores only.

## 12. Frozen exit criteria (from contract §12)

High-impact outlet requires: primary contrast >= +0.02 with CI lower bound
> 0; at least one secondary positive under Holm; both external studies
same-direction with CI lower bounds > 0; sensitivity analyses not reversing
conclusions; three final reviewers without major blockers. Otherwise the
honest outcome is the professional-journal exit (benchmark/resource paper),
which the current evidence base already supports.
