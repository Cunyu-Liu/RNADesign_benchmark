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
backbones, with the TBLR ranking objective significantly underperforming
its matched pointwise twin on both (CNN −0.0125; SANDSTORM −0.0204
NDCG@10, both p = 2e-5). A controlled
leakage experiment quantifies the causal cost of same-target training
contamination (+0.034 NDCG@10). On the independent VISTA mCherry track, the
official PLS-DA ranking attains NDCG@10 0.676 [bootstrap CI 0.534, 0.825]
against an analytic random baseline of 0.263, while the prior tsgen2 ranking
falls below random under its documented convention. Frozen canonical-
trained transfer models fail to carry ranking skill to alternative sensor
architectures -- below random on VISTA's tsgen2-hairpin scaffold (CNN
transfer 0.079), absent-to-negative on the VISTA SARS-CoV selection groups
and on 100 crowdsourced heterogeneous regulators for sequence-only
backbones -- while the structure-aware SANDSTORM transfer model transfers
significantly on the crowdsourced set (Spearman 0.41 OFF / 0.33 ON,
cluster-bootstrap CIs excluding zero), identifying backbone structure
awareness as the regime in which cross-architecture signal survives. All
data identities, mappings, exclusions, and statistical
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

SANDSTORM backbone (complete, 5 folds x 5 objectives x 5 seeds, 917
targets, structure-aware official backbone):

| Objective | NDCG@10 | Spearman | success@1 |
|---|---|---|---|
| legacy row-weighted MSE | 0.8349 | 0.485 | 0.709 |
| target-balanced MSE (matched pointwise) | 0.8171 | 0.453 | 0.671 |
| target-balanced dual ON/OFF | 0.8150 | 0.457 | 0.678 |
| full TBLR (LambdaRank@10 + aux) | 0.7966 | 0.410 | 0.626 |
| LambdaRank-only | 0.7933 | 0.406 | 0.600 |
| analytic random | 0.6427 | — | — |

Primary contrast on SANDSTORM: full_tblr − tb_mse = −0.0204, CI
[−0.0241, −0.0164], p = 2e-5 (cluster bootstrap, Holm-adjusted); secondary
contrast vs rowwise: −0.0383, CI [−0.0431, −0.0335], p = 2e-5. The
SANDSTORM backbone REPRODUCES the CNN direction with a larger effect.

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
subsets. The SANDSTORM backbone reproduces the same direction with a
larger effect (−0.0204 above): across both backbones the target-balanced
ranking objective (TBLR) underperforms its matched pointwise twin by
1.3-2.0 NDCG points, and the legacy row-weighted MSE remains the strongest
objective family. This is a stable, two-backbone negative result for
ranking-objective superiority in target-balanced toehold ranking.

## 8. Independent external track: VISTA mCherry

189 sites, ONE target (site-level bootstrap CIs only; never extrapolated to
multi-target claims). Official rankings scored under the paper-documented
rank convention (rank 1 = best, per Fig. 5D of the VISTA preprint):

| Method | NDCG@10 (ON/OFF Full) | CI | random |
|---|---|---|---|
| VISTA PLS-DA (Full model) | 0.6760 | [0.5336, 0.8247] | 0.2627 |
| VISTA PLS-DA (Trunc model) | 0.6692 | [0.5300, 0.8336] | 0.2627 |
| tsgen2 (direction-reversed sensitivity) | 0.4246 | [0.2261, 0.6856] | 0.2627 |
| tsgen2 (documented convention) | 0.1147 | [0.0596, 0.1702] | 0.2627 |
| canonical transfer CNN (5 frozen seeds) | 0.0788 | [0.0324, 0.2099] | 0.2627 |

The prior tsgen2 ranking falls below the analytic random baseline under its
documented convention -- consistent with the VISTA paper's motivation for
replacing it. The canonical-trained transfer model (frozen on all-canonical
training with the full-canonical inner-CV config; no external label read
before final scoring; input pair reconstructed from each 36-nt site exactly
as the canonical switch==RC(trigger) relation dictates) also fails to
transfer, scoring below random (0.0788 Full / 0.1130 Trunc vs random
0.263/0.250). Both failures are architecture-shift results: models trained
on the Angenent–Mari linear toehold architecture do not carry ranking skill
to the tsgen2-hairpin sensor architecture, even though both nominally rank
"toehold switches for a fixed target". Under the contract's frozen exit
criteria (§12) this fails the high-impact external-gain gate; the honest
outcome is the professional-journal benchmark/resource exit, for which the
negative transfer and the tsgen2 below-random result are themselves
contributions.

## 8b. Architecture-shift external track: crowdsourced 100 regulators

The 2026 crowdsourced riboregulator preprint (bioRxiv 2026.07.08.737257;
PMC13370501) reports 100 community-designed riboregulators measured in a
cell-free TX-TL system with native continuous outcomes (ON average, OFF
average, fold-change fluorescence). The supplementary table was fetched
directly from PMC (proof-of-work-solved fetch; acquisition script
`scripts/download_crowdsourced.py`); exposure against the canonical registry
is zero (sensor, trigger, and 30-nt trigger-prefix overlap all 0 of 100), so
the track is a genuine independent architecture-shift probe. Crowdsourced
sensors do not follow the canonical switch==RC(trigger) relation (verified
0/100); sensor lengths span 41-157 nt.

Per the contract, this track uses native continuous outcomes only -- no
artificial candidate-set NDCG. Frozen canonical-transfer models (full-canonical
inner-CV config, 5 seeds, seed-averaged predictions) are scored by Spearman
correlation against native outcomes, with an architecture-cluster bootstrap
(k-means K=5, seed 20260821, on the preprint's structural descriptors:
sensor/target length, target-binding positions relative to TSS/RBS/GFP;
99/100 complete-feature regulators; 5000 cluster-resampling reps):

| Method | prediction | native outcome | Spearman rho | cluster-bootstrap 95% CI |
|---|---|---|---|---|
| transfer CNN (5 frozen seeds) | score | ON-OFF | -0.059 | [-0.353, 0.099] |
| transfer CNN | predicted ON | ON average | 0.010 | [-0.216, 0.201] |
| transfer CNN | predicted OFF | OFF average | -0.008 | [-0.101, 0.268] |
| transfer CNN | score | fold change | -0.113 | [-0.499, -0.001] |
| transfer SANDSTORM (5 frozen seeds) | score | ON-OFF | 0.199 | [0.037, 0.497] |
| transfer SANDSTORM | predicted ON | ON average | 0.326 | [0.106, 0.560] |
| transfer SANDSTORM | predicted OFF | OFF average | 0.413 | [0.208, 0.660] |
| transfer SANDSTORM | score | fold change | 0.121 | [-0.086, 0.294] |

The two frozen transfer families split sharply. The sequence-only CNN shows
absent-to-negative transfer on every native outcome (fold-change CI excludes
zero on the negative side). The structure-aware SANDSTORM transfer model --
identical training corpus, identical frozen-transfer protocol -- transfers
significantly and positively: predicted OFF correlates at rho 0.413
[0.208, 0.660], predicted ON at 0.326 [0.106, 0.560], and the ranking score
at 0.199 [0.037, 0.497] against native ON-OFF (all cluster-bootstrap CIs
exclude zero). Architecture shift therefore does not uniformly destroy
transfer: structure-aware features carry signal across 100 heterogeneous
community architectures while sequence-only features do not. This is a
regime-stratified result -- it does not rescue the contract's external-gain
gate (the VISTA track remains negative transfer), but it identifies the
backbone regime in which cross-architecture signal survives.

## 8c. VISTA SARS-CoV selection groups (selection-conditioned)

The published Toehold-VISTA study (NAR 2026, gkag097) reports 72 switches in
six selection groups of 12 (Supplementary Table 9): four mCherry-screen
groups selected by VISTA's own predictions (low/high ON/OFF, low OFF, high
ON), and two SARS-CoV-2 N-gene groups designed by tsgen2 vs VISTA. These
switches were SELECTED by design-model scores, so the analysis is
selection-conditioned description, never independent validation (contract
§9); input mapping is identical to the mCherry track (trigger30 =
target[6:36], switch30 = switch[25:55]; alignment verified 72/72).

Paper-native group separation (measured ON/OFF full-RNA, mean of 12):
VISTA_high_onoff 126.9 vs VISTA_low_onoff 12.3 (10.3x); VISTA_high_on 71.1;
VISTA_low_off 4.1 -- the VISTA selection itself separates measured
performance. The SARS-CoV-2 N groups measure comparably in this table
(VISTA 36.0 vs tsgen2 33.0). Our frozen transfer CNN scores do not separate
the groups in the measured ordering (pooled Spearman vs measured ON/OFF:
-0.056 full / -0.101 truncated; descriptive only, no CI claim on
selection-conditioned data), consistent with the architecture-shift
transfer failure in Sections 8 and 8b. The structure-aware SANDSTORM
transfer model also fails here (-0.086 full / -0.173 truncated) -- these 72
switches all use the tsgen2-hairpin VISTA scaffold, the same architecture
family that defeated transfer in the mCherry track, in contrast to the
architecturally diverse crowdsourced set where SANDSTORM transfer is
significantly positive (Section 8b).

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
- VISTA evidence is a single target; the crowdsourced architecture-shift
  track (100 heterogeneous regulators) shows absent-to-negative canonical
  transfer (Section 8b), so external generalization remains unsupported
  beyond the native benchmark.
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
