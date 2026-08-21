# ToeholdDesignBench v0.3.0 — Frozen Execution Contract

Status: **sole controlling contract** for all ToeholdDesignBench work from 2026-08-21. Supersedes `task_contract_v0.2.1_consolidated.md` (retained unmodified for audit). Any deviation requires an owner decision recorded in this repository before execution.

Execution root: `cunyuliu@36.137.135.49:/home/cunyuliu/ToeholdDesignBench`
Large artifacts: `/mnt/cunyuliu/ToeholdDesignBench/` (runs under `runs/v0.3.0/<run_id>/`, releases under `releases/`)

## 1. Central Question (frozen)

> In an evaluation with closed repeat sequences, homologous target clusters never crossing folds, and every target equally weighted under a fixed experimental budget, does a target-balanced ranking objective stably improve candidate selection across multiple modern RNA model backbones, and does the gain persist in the same direction on independent studies' native tasks?

Innovation boundary:

- Contribution = target-grouped benchmark + task-aligned ranking objective + multi-backbone matched ablation + modern official-model re-evaluation.
- Source/virus holdout itself is NOT claimed as novel (Angenent–Mari 2020 already did per-viral-genome holdout).
- Target-grouped evaluation is NOT misrepresented as "model uses full target sequence".
- canonical and BEACON are NOT described as two independent datasets.
- No prospective, de novo generation, or wet-lab hit-rate claims.
- "State of the art"/"generalizable" wording only if all high-impact gates pass.

## 2. Data Identity, Global Registry, and Splits

1. canonical and BEACON share `study_id=angenent_mari_2020`, distinct `label_view`; label scales are never merged.
2. The 140-target legacy split is retained as `legacy_development` only (regression tests and historical continuity); it never enters confirmatory wording.
3. Canonical main analysis = 5-fold retrospective nested cross-validation. All protocols, models, metrics, and comparison families freeze before outer results are generated.
4. For records with verifiable accession/coordinates, rebuild direction-consistent 512-nt context from frozen accession versions: 241 nt upstream + 30-nt trigger + 241 nt downstream; boundaries padded with `N` plus explicit mask. Records whose trigger/strand/coordinates cannot be verified on the reference are `context_unresolved`; no guessing.
5. `target_cluster_id` by union closure. Targets sharing any of the following enter the same component:
   - same authoritative accession/source;
   - any 30-nt trigger exactly identical or reverse-complementary;
   - overlapping candidate intervals on the same accession;
   - any verifiable 512-nt contexts with ≥80% nucleotide identity covering ≥80% of the shorter sequence.
6. All rows, candidate windows, homologous components, and targets of a component enter the same outer fold.
7. Outer folds: fixed-seed group-stratified assignment balancing target category, target count, and candidate-pool size, never splitting components.
8. Context-unresolved targets remain in the local/construct track (flagged); the context track excludes them; a sensitivity analysis excludes all unresolved targets.
9. Ranking-metric denominators require ≥2 candidates and nonzero within-target label range. Singleton/flat-label targets stay in coverage, feasibility, and unconditional-success reporting only.
10. Selection-mechanism audit of paired vs. single/no-label/excluded cohorts: report category, GC, MFE, pool size, label availability differences; no inverse-probability weighting without label support.

## 3. BEACON Rules

- Correct trigger = `[3:33]` (0-based).
- Main analysis excludes `mapping_status=ambiguous`; inclusion of ambiguous rows is sensitivity-only.
- Every record is explicitly `unique`, `ambiguous`, or `unresolved`; silent first-match disambiguation is forbidden.
- All 148-nt "context" experiments use one fixed-capacity 148-position model with masking ablations: trigger-only `[3:33]`; RC-copy-only `[53:83]`; trigger+RC; scaffold-only; authoritative-template variable positions; full construct; segment-wise shuffle.
- All ablations share architecture, parameter count, training budget, folds, and candidate sets.
- BEACON counts only as the same study's construct/label view; it never increments the independent-external-study count.

## 4. Endpoints

Primary: mean per-target NDCG@10; continuous relevance = `ON−OFF` minus target minimum, linear nonnegative gain; only targets with ≥2 candidates and ideal DCG > 0; targets equally weighted; candidate rows are not independent samples.

Secondary: normalized regret@1/3/5/10; target-level Spearman; success@1/3/5/10 over the full threshold surface `ON ∈ {0.3..0.7} × OFF ∈ {0.3..0.7}`; legacy 0.5/0.5 is a continuity cell only; pooled R²/MAE/row-level correlation are auxiliary; no raw-scale pooling across studies/label views.

Random and ties: analytic per-target random expectations computed by the evaluator; no seed-0 ordering as the paper random baseline; ties at cutoffs handled as analytic expectations over equiprobable permutations, never by `record_id` or input order; one tie policy shared by NDCG, success, and regret.

## 5. Statistical Contract

- Outer-fold predictions: mean of 5 training seeds' scores, then metrics; seed variation reported separately; seeds are not biological replicates.
- 95% CI: 5,000-replicate paired target-cluster bootstrap (clusters resampled whole).
- Formal P: 50,000-replicate cluster-level paired sign-flip/randomization with add-one correction. Bootstrap zero-crossing proportions are never P values.
- Primary contrast: `TBLR-SANDSTORM` vs matched pointwise `SANDSTORM`.
- Secondary contrasts (Holm-corrected): `TBLR-CNN` vs matched pointwise CNN; `TBLR-RNAElectra` vs matched pointwise RNAElectra.
- Other model pairs: effects, CIs, ordering only; no per-pair P values.
- Overall-SOTA claims require paired positive differences against all pre-declared core published comparators in the same information regime with Holm-adjusted simultaneous intervals excluding 0.
- VISTA mCherry intervals are site-level only; never extrapolated to multi-target uncertainty.
- Each external study is analyzed on its own native units; labels are never pooled across studies.

## 6. Model Panel (frozen)

All methods ranked within information regimes; regimes are never mixed into one "fair" leaderboard.

| Regime | Required models |
|---|---|
| Analytic/local | exact random; GC; corrected thermodynamic scorer; train-only-preprocessed biophysics-only and sequence+biophysics LightGBM |
| Official classic | Angenent–Mari MLP-O and CNN/VIS4Map (official code); Valeri STORM/NuSpeak scoreable CNN cores (official code) |
| 2024 benchmark | BEACON official ResNet, LSTM, BEACON-B512, SpliceBERT-MS1024, RNA-FM, UTR-LM-MRL (official repo) |
| 2025 design predictors | SANDSTORM (official GARDN-SANDSTORM code + released data) |
| 2026 pretrained RNA | RNAElectra backbone (preprint; task-head adaptation; labeled as preprint) |
| Full target/native external | Toehold-VISTA exact VISTA/tsgen2 on native 36-nt/full-transcript external track only |
| Architecture-shift | 2026 crowdsourced riboregulator preprint's 100 heterogeneous regulators, native continuous outcomes, structural grouping; no artificial candidate-set NDCG |

Execution boundaries:

- STORM/NuSpeak/GARDN/TSGEN full generation systems are out of scope as systems; only their scoreable official cores on fixed candidates, or their published experiments as native external analyses.
- SANDSTORM/GARDN's own published sequences never serve as SANDSTORM's independent validation; they are selection-conditioned data for other methods or architecture-shift analysis.
- Every method first passes identity reproduction on its official original split/metric: within reported mean ±2 SD when SD exists, else main-metric absolute difference ≤ 0.03; failing methods are `adapted reimplementation` and never authoritative comparators.
- 100% score coverage on the pre-declared eligible candidate set; no silent row drops or score imputation.
- NUPACK 4 standardizes newly computed thermodynamic features; official legacy models keep their original precomputed features, explicitly distinguished.

## 7. TBLR — Target-Balanced LambdaRank

Backbones: `TBLR-CNN` (30-nt trigger + 30-nt switch/construct), `TBLR-SANDSTORM` (official representation), `TBLR-RNAElectra-construct`, `TBLR-RNAElectra-context` (dual-tower construct+context512 fusion; context-eligible subset only; the construct-vs-context gap is its own ablation).

Sampling/training unit: one epoch = each training target sampled once, random order; batch = 32 targets; ≤64 candidates per target all in loss, >64 sampled as 8 per each of 8 training-label relevance quantiles, rotating across epochs; every target contributes equal total loss; evaluation scores all candidates.

Heads (identical across objective ablations): ranking score, predicted ON, predicted OFF. Loss = `L_LambdaRank@10 + λaux × [Huber(ON)+Huber(OFF)]/2`, λaux ∈ {0.1, 0.25, 0.5} chosen on inner validation. Pair weights = `ΔNDCG@10` of swapping the pair. No 0.5/0.5 hit head.

Matched ablations per backbone (same parameters/folds/preprocessing/tuning budget; unused heads keep loss weight 0): legacy row-weighted pointwise MSE; target-balanced pointwise MSE; target-balanced dual ON/OFF regression; target-balanced LambdaRank-only; full TBLR.

Model selection: outer 5-fold × 3-fold target-cluster inner CV; ≤12 pre-declared configs per trainable family (encoder LR multiplier {0.5,1,2} on the identity-reproduction LR, custom CNN base 3e-4; weight decay {0, official}; TBLR λaux {0.1,0.5} or dropout {0, official} for non-auxiliary models); ≤100 epochs; inner-validation NDCG@10 early stopping patience 10, min improvement 1e-4; tuning seed 20260821; final seeds 20260821–20260825. After outer predictions exist: no re-selection of backbone/threshold/loss/epoch. Transfer models: config chosen by full-canonical inner CV without external labels, trained on full canonical (5 seeds), frozen, then score external studies.

## 8. Corrected Biophysical Baselines

Salis `log1p` then standardize; MFE/GC/continuous features scaled by outer-train/inner-train median/mean/scale only; train-set-median imputation with missingness indicators; Salis missing never backfills to MFE; biophysics-only/sequence-only/combined share folds and target-balanced budget; "biophysics hurts" downgraded to "naive preprocessing failed" until corrected results exist.

## 9. Implementation Batches

**Batch 1 (done items checked)** — baseline preservation, reviewer critiques, contract freeze, data identity:
- [x] local branch `reviewer-revision-v0.3`, staged checkpoint commit, tag `reviewer-baseline-v0.2.1-20260821`; v0.2.1 paper-facing results copied to `/mnt/cunyuliu/ToeholdDesignBench/releases/v0.2.1/`.
- [ ] `reviewer_critique_v0.2.1.md`, `task_contract_v0.3.0.md`, `task_contract_v0.2.1_to_v0.3.0_redline.md`.
- [ ] Global study/target/candidate registry, context512, mapping-status ledger, exclusion ledger, 5-fold cluster split.
Acceptance: checkpoint Git-identifiable; v0.2.1 results never overwritten by `_v03` reruns; cross-fold exact/RC trigger overlap = 0; accession/homology components never cross folds; BEACON `[3:33]` equals authoritative trigger; every mapping has a status; shared study identity; legacy test labeled `legacy_development`.

**Batch 2** — single evaluator: `src/toeholdbench/` package (dataset/track registry; method registry; score adapter; target evaluator; cluster statistics; paper artifact builder); all analyses consume one evaluator; random/ties/NDCG/success/regret/coverage/bootstrap/sign-flip from one kernel; runs under `/mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/<run_id>/` never overwritten; locked environments with explicit interpreter paths; `run_v03.sh` test discovery (no hand-written test counts in the manuscript); locked-environment end-to-end run as the reproduction evidence (Docker not a hard gate).
Acceptance: hand-computed analytic random/tie/NDCG/success/regret on tiny data match; all callers produce identical evaluator output; bootstrap and sign-flip unbiased on zero-effect synthetic data; no sampled-random paper results; single test entry point; incomplete/duplicate/non-finite scores fail loudly.

**Batch 3** — official models, TBLR, ablations: per-model adapters/environments with frozen commits/checkpoints/input semantics/score direction/exposure; original-split identity reproduction before new folds; full core panel (failures never silently skipped); TBLR on three main backbones + full matched ablations; BEACON fixed-capacity segment masking; corrected biophysical baselines; controlled leakage experiment (fixed 20% evaluation candidates on candidate-rich test targets; leaky arm adds same-target neighboring windows; clean arm adds target-cluster-disjoint matched rows; identical row counts and test candidates; 5 seeds; per-target paired comparison); independent protocol/code freeze audit before outer predictions; post-hoc performance is never a contract-change reason.
Acceptance: identity tolerance or honest `adapted reimplementation`; 100% score coverage per eligible track; equal per-target loss weight; train-fold-only preprocessing; early stopping/hyperparameters never read outer labels; matched-ablation parity; BEACON conclusions unconfounded by slicing/capacity; leakage arms share test candidates exactly.

**Batch 4** — external tracks, paper, final review: traceable download scripts for VISTA, GARDN/SANDSTORM released data, crowdsourced regulator data (redistribution per license); method×dataset exposure matrix (exposed data is never independent validation); external models frozen before external scoring; VISTA mCherry native site ranking/NDCG@10 with site bootstrap and single-target boundaries; VISTA SARS-CoV groups as selection-conditioned analysis; crowdsourced 100-regulator Spearman + architecture-cluster bootstrap; GARDN/SANDSTORM released designs as exposure-aware description only; no cross-study label pooling; manuscript with data lineage, split/leakage, regime-stratified model comparison, TBLR ablations, BEACON masking + external shift; superseded exhibits demoted to supplementary; literature cutoff 2026-08-21; clean-environment full reproduction; three final reviewer reports + editor synthesis; deliverables copied to local `outputs/`.

## 10. Public Interfaces

Dataset/track manifest (per record): `record_id, study_id, assay_id, label_view, target_id, target_cluster_id, candidate_id, outer_fold, information_regime, source_accession_version, trigger_sequence, switch_or_construct_sequence, candidate_start, candidate_end, strand, context_512, context_mask, mapping_status, label_on, label_off, label_semantics, eligibility_status`.

Method registry (per method): `method_id, family, official_source, source_commit, checkpoint, official_or_adapted, information_regime, training_mode, objective, original_score_direction, benchmark_score_transform, parameter_count, tuning_budget, seeds, environment, dataset_exposure`.

Prediction schema (one row per eligible candidate): `run_id, track_id, fold, target_id, target_cluster_id, record_id, method_id, seed, score` (+ optional `predicted_on, predicted_off`). Higher-is-better internally; adapters own direction conversion; eligible sets frozen before scoring; missing/duplicate/non-finite scores fail the method-track; evaluator never imputes.

Unified entry: `python -m toeholdbench evaluate --track <track_manifest> --predictions <score_file> --output <run_directory>` producing target-level metrics, cluster-level contrasts, CIs and formal comparisons, coverage/exclusion report, exposure report, table/figure source data, machine-readable execution manifest.

## 11. Test Scenarios (frozen)

Data/splits: components never cross folds; the 46 legacy exact overlaps land in one component; reference context center-30 equals trigger/strand (else unresolved); BEACON `[3:33]`/RC-segment/template coordinates locked by tests; all ambiguous mappings in ledger and absent from main analysis; canonical+BEACON never counted as two studies; singleton/flat/no-feasible denominators per contract; context-only comparisons on identical eligible-target intersections.

Evaluator/statistics: tiny hand-enumerated sets verify analytic random, ties, NDCG, success, regret; identical results across all callers; cluster-intact bootstrap; sign-flip direction on known zero/positive synthetic effects; Holm family = exactly the two pre-declared secondary contrasts; seed averaging precedes target metrics; no pooled-scale cross-study computation.

Training/models: equal per-target epoch weight; candidate subsampling uses training labels only; validation/outer access isolated by tests and manifests; ablation parameter parity; train-fold-only feature fitting; official slice/tokenization/polarity/coverage locked by adapter tests; failed identity reproduction disables `official_reproduction=true`; per-seed and ensemble results both retained.

External: native endpoints and units per study; exposure checked before formal comparison; VISTA CI site-level only; selection-conditioned data labeled; non-redistributable data keeps scripts/metadata/derived scores only.

End-to-end/manuscript: single entry runs tests, scoring, statistics, figures, and manuscript numbers in a clean environment; test counts auto-reported; every manuscript number traces to the final run directory; figures/tables registry-driven; v0.2.1 files unchanged; final artifacts copied to local `outputs/`.

## 12. Outlet Gates and Stop Rules

High-impact (Nature Communications-tier computational methods/synbio Article) requires ALL of:
1. All data-integrity, official-reproduction, statistics, and end-to-end hard gates pass.
2. Primary `TBLR-SANDSTORM − pointwise SANDSTORM` mean NDCG@10 gain ≥ 0.02 with 95% cluster-bootstrap CI lower bound > 0.
3. `TBLR-CNN` or `TBLR-RNAElectra` secondary matched effect positive, Holm-adjusted P < 0.05, CI excluding 0.
4. SOTA wording only via simultaneous comparison against all pre-declared same-regime published comparators; otherwise deleted.
5. VISTA and crowdsourced studies both show same-direction gains on pre-declared native metrics with interval lower bounds > 0.
6. Excluding ambiguous BEACON rows, legacy exact-overlap targets, and context-unresolved targets does not reverse the main effect or its statistical conclusion.
7. Three final reviewers find no major blocker (technical, novelty, claim boundaries); editor synthesis judges the tier achieved.

No new wet-lab this round; passing means internal submission readiness only; no prospective-validation claims.

Professional-journal exit (hard gates pass but 2/3/4/5 not all met): stop adding models/thresholds/subsets; convert honestly to a modern target-level benchmark/resource paper; negative results, regime-stratified orderings, split contamination, objective mismatch, and external architecture shift are legitimate results; stable-method-gain-with-thin-external-evidence → Bioinformatics Original Paper tier; benchmark/identity/audit-centric → ACS Synthetic Biology tier; final three-reviewer + editor sign-off still required.

Iteration rules: before outer/external results — code fixes, tests, identity reproduction, inner tuning allowed; after — bad performance is a result, not a contract-change reason; only concrete implementation/statistical/data-identity errors or unsupported claims get fixed, with affected dependency chains rerun wholesale (never only favorable models); failed formal runs keep their records; final stop = three reviewers with no major blocker on the pre-declared outlet + editor synthesis explicitly clearing submission.

## 13. Assumptions and Authorization

- Compute-only reanalysis of public/legal data; no new wet-lab.
- NUPACK 4 provided/confirmed legally installed by the user; never redistributed by the project.
- Local branch/commit/tag authorized; push authorization is governed by the latest owner instruction, recorded in the repository when exercised.
- No submission, public repo release, author/journal contact without explicit owner authorization.
- Preprints allowed, always labeled.
- External raw data redistributed only per license; otherwise scripts + citations + derived scores.
- No unrelated security frameworks, migration layers, or checksum systems.
- 8×A100 shared; queue by real-time idle capacity; no exclusivity assumed.
- Author/ORCID/funding/journal formatting deferred to final stage; never blocks technical iteration.
