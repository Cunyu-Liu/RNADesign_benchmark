# Redline: task_contract_v0.2.1 → task_contract_v0.3.0

Legend: `[REMOVED]` gate deleted in v0.2.1; `[RESTORED]` v0.1 gate re-instated by v0.3.0; `[NEW]` added by v0.3.0; `[CHANGED]` semantics altered; `[UNCHANGED]` carried forward.

## Data identity and splits

| Item | v0.2.1 | v0.3.0 |
|---|---|---|
| Exact dedup across train/test | `[REMOVED]` — 46 identical 30-nt triggers crossed the 140-target split | `[RESTORED]` — exact/RC trigger closure inside `target_cluster_id`; cross-fold overlap must be 0 (tested) |
| Overlap-component / interval overlap | `[REMOVED]` | `[RESTORED]` — same-accession overlapping candidate intervals merge into one component |
| Sequence-cluster OOD | `[REMOVED]` | `[RESTORED]` — ≥80% identity over ≥80% coverage of the shorter 512-nt context merges components |
| Study identity | canonical and BEACON presented as separate datasets | `[CHANGED]` — both are `study_id=angenent_mari_2020`, distinct `label_view`; never counted as two studies |
| 140-target test | "pre-registered confirmation set" | `[CHANGED]` — `legacy_development` only; 0.5/0.5 threshold was post-hoc and is demoted to a legacy continuity cell |
| Main split | single 70/15/15 with contaminated test | `[CHANGED]` — 5-fold retrospective nested CV; group-stratified (category, target count, pool size); components never split |
| context512 | not defined | `[NEW]` — 241+30+241 rebuilt from frozen accession versions; N+mask at boundaries; unverifiable → `context_unresolved`; context-track sensitivity analysis excludes them |
| BEACON trigger slice | `[0:30]` (wrong) | `[CHANGED]` — `[3:33]`; tests lock the slice; RC copy `[53:83]` handled by fixed-capacity masking ablations |
| Mapping ambiguity | silent `setdefault`/input-order resolution (396 multi-source, 568 multi-seqID rows) | `[NEW]` — explicit `mapping_status ∈ {unique, ambiguous, unresolved}` ledger; ambiguous excluded from main analysis, sensitivity-only |
| Ranking denominators | all targets with any labels | `[CHANGED]` — ≥2 candidates and nonzero within-target label range; singletons/flat labels stay in coverage/feasibility/unconditional-success reports |
| Cohort selection audit | absent | `[NEW]` — paired vs. single/no-label/excluded comparison on category/GC/MFE/pool/label availability; no IPW without label support |

## Endpoints and statistics

| Item | v0.2.1 | v0.3.0 |
|---|---|---|
| Primary metric | success@k at 0.5/0.5 (post-hoc) | `[CHANGED]` — mean per-target NDCG@10 (linear nonnegative gain on min-subtracted ON−OFF); threshold surface is secondary |
| Threshold surface | single 0.5/0.5 cell, chosen post-hoc | `[CHANGED]` — 5×5 surface {0.3..0.7}²; 0.5/0.5 = legacy continuity cell only |
| Random baseline | seed-0 sampled ordering | `[CHANGED]` — analytic per-target expectation computed by the evaluator |
| Ties | unresolved (record_id/input order effects) | `[CHANGED]` — analytic expectation over equiprobable permutations; one tie policy for NDCG/success/regret |
| P values | bootstrap zero-crossing proportions | `[CHANGED]` — 50,000 cluster-level paired sign-flip/randomization with add-one correction |
| CI | target bootstrap (clusters not intact) | `[CHANGED]` — 5,000 paired target-cluster bootstrap, clusters resampled whole |
| Multiple comparisons | per-pair P values manufactured | `[CHANGED]` — one primary contrast (TBLR-SANDSTORM vs pointwise SANDSTORM); two Holm-corrected secondaries; others effect+CI only |
| Seeds | single seed | `[CHANGED]` — 5 seeds averaged before metrics; seeds never biological replicates |

## Models and method

| Item | v0.2.1 | v0.3.0 |
|---|---|---|
| Model panel | legacy MLP/CNN variants + thermodynamic proxy | `[CHANGED]` — frozen panel: official Angenent–Mari MLP-O/CNN-VIS4Map; Valeri STORM/NuSpeak CNN cores; BEACON ResNet/LSTM/BEACON-B512/SpliceBERT-MS1024/RNA-FM/UTR-LM-MRL; SANDSTORM; RNAElectra (preprint); VISTA/tsgen2 external-only; crowdsourced 100-regulator architecture-shift |
| Identity reproduction | not required | `[NEW]` — official split/metric reproduction (±2 SD or ≤0.03) before benchmark use; failures → `adapted reimplementation`, never authoritative comparators |
| 148-nt "context" experiments | 30-nt model vs 3.54×-parameter 148-nt model | `[CHANGED]` — one fixed-capacity 148-position model with segment-masking ablations ([3:33], [53:83], both, scaffold, template-variable, full, shuffle) |
| B5_structrank | "ranker" (actually MSE MLP +5 steps) | `[REPLACED]` — TBLR (Target-Balanced LambdaRank) with ΔNDCG@10 pair weights, 3 heads, λaux ∈ {0.1,0.25,0.5} |
| Training objective | row-weighted full-batch MSE, fixed 15/20 steps | `[CHANGED]` — target-balanced sampling (32 targets/batch, 8×8 quantile subsample >64, rotating), equal per-target loss, ≤100 epochs, inner-CV early stopping |
| Matched ablations | none | `[NEW]` — per backbone: row-weighted MSE / target-balanced MSE / dual regression / LambdaRank-only / full TBLR, same capacity, folds, budget |
| Tuning | none (fixed 15/20 steps; validation unused) | `[CHANGED]` — ≤12 pre-declared configs; 3-fold target-cluster inner CV; tuning seed 20260821; final seeds 20260821–20260825; no post-hoc re-selection |
| salis_onoff | zero-filled, unstandardized, mixed with MFE | `[CHANGED]` — log1p + train-fold standardization; median imputation + missingness indicator; never MFE backfill |
| "Biophysics hurts" | broad claim | `[CHANGED]` — downgraded to "naive preprocessing failed" until corrected baselines exist |
| Leakage experiment | different test candidate sets | `[CHANGED]` — fixed identical 20% evaluation candidates; leaky vs. clean arms with equal row counts; 5 seeds; per-target paired |
| Score coverage | silent drops allowed | `[NEW]` — 100% coverage on frozen eligible sets; missing/duplicate/non-finite → method-track failure |

## Engineering

| Item | v0.2.1 | v0.3.0 |
|---|---|---|
| Evaluator | per-module metric re-implementations | `[CHANGED]` — single `src/toeholdbench/` evaluator kernel; all callers consume identical outputs |
| Test count claim | hand-written "20 tests" (18 ran) | `[CHANGED]` — test discovery; counts auto-reported |
| Runs | ad-hoc output paths, overwrite risk | `[NEW]` — immutable `/mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/<run_id>/`; existing directories never overwritten |
| Environments | implicit `python` | `[CHANGED]` — locked envs, explicit interpreter paths |
| Reproduction | Docker implied, never executed | `[CHANGED]` — locked-environment clean end-to-end run as the evidence; Docker not a hard gate |
| Workspace hygiene | 28 modified + 22 untracked paths; stale PIDs | `[CHANGED]` — checkpoint commit + tag `reviewer-baseline-v0.2.1-20260821`; v0.2.1 results archived to `releases/v0.2.1/`; stale PID files excluded from history |

## Outlets

| Item | v0.2.1 | v0.3.0 |
|---|---|---|
| Outlet criteria | none | `[NEW]` — two-tier pre-declared gates (high-impact vs professional journal) with explicit stop rules; negative results legitimate; no post-hoc model/threshold/subset shopping |

## Explicitly unchanged

Signed ON−OFF labels; target as independent decision unit; no-feasible-candidate targets kept in denominators; per-target analytic random expectation; label-view separation; target-level bootstrap (now cluster-intact); no wet-lab claims; NUPACK-4-legal-installation boundary; 8×A100 shared-queue resource model.
