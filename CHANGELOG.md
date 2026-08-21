# CHANGELOG

All notable changes to ToeholdDesignBench are documented here. Versioning follows Semantic Versioning.

## [0.2.1-statistical-addendum] — 2026-08-21

- Replaced a single seeded random ranking with the exact per-target expectation
  under a uniformly random candidate permutation.
- Added finite-bootstrap add-one correction so paper results cannot report
  `P = 0`.
- Preserved BEACON's published row split under an unambiguous column name and
  added train/test target-overlap auditing.
- Made VISTA interpretation outcome-neutral and revised the objective-alignment
  figure title to match the observed evidence.
- Added regression tests for exact random expectations and BEACON split-column
  collisions.
- Completed the full remote v0.2.1 rerun and regenerated the machine-readable
  results, tables, vector/600-dpi figures, source data, and alt text.
- Replaced the superseded hypothesis-driven draft with the evidence-aligned
  `docs/manuscript_v0.2.1.md` and added a consolidated Markdown control contract.

## [0.2.1-unreleased] — 2026-08-21 — reviewer-driven correctness revision

- Corrected CNN nucleotide-channel layout and added a regression test that fails
  under the historical direct reshape.
- Preserved canonical signed `ON - OFF` labels; negative relevance is handled in
  NDCG without clipping.
- Replaced per-target percentiles with target-bootstrap confidence intervals and
  paired target-bootstrap method differences.
- Replaced within-top-K Pareto-front size with global-front coverage.
- Added target accounting, deterministic tie-breaking, and stricter submission
  validation to the runner; aligned the published schema.
- Moved learned canonical baselines to seeds 0–4 and made the robustness report
  consume those exact score files.
- Added separate source-disjoint/domain-OOD BEACON tracks and a paired single-target
  VISTA truncated/full stress test without merging label scales.
- Archived v0.1 result narratives, added the controlling Markdown v0.2 task
  contract, and replaced contradictory data-reconciliation language.
- Added the portable `scripts/run_v02.sh` core entry. Full server results remain
  pending at this changelog point.
- Added a fail-closed result-to-paper artifact builder with Markdown/CSV tables,
  source-data-backed PDF/opaque-PNG figures, alt text, and provenance metadata.

## [0.2.0] — 2026-08-20 — Publication-readiness (T1–T5 after reviewer evaluation)
- **T1**: obtain and preserve the full 91,534 sequence-mapped PRS dataset (BEACON/NeurIPS 2024 HF mirror,
  train 73,227 / val 9,153 / test 9,154; reproducible via `scripts/download_data.sh`); reproducible ≥70k
  sequence-level baseline (test R² 0.216, ρ 0.458) via `src/beacon_full_baseline.py`. Honest finding: the
  91,534 is a re-processed set (label normalization differs; only ~41% attributable to virus/TF), so the
  target-aware design benchmark remains on the 52,861 target-attributable records.
- **T2**: de-bind model names (B3_storm→B3_deep, B5_targetaware→B5_structrank); baselines are representative
  families, not STORM/NuSpeak/SANDSTORM/Toehold-VISTA implementations. Numbers unchanged (re-verified).
- **T3**: 5-seed mean ± 95% CI for all baselines + virus vs TF group robustness
  (`src/p3_robustness.py`, `processed/p3_robustness_multiseed.json`). Finding: design-utility signal is
  concentrated in virus targets (thermo success@1 0.83) and absent in TF targets — explaining pooled top-1≈random.

## [0.1.1] — 2026-08-20 — Strict-acceptance remediation (FIX-1..FIX-5)
Applied after a strict acceptance audit against the contract (§9/§13). Changes:

- **FIX-1 (P3 reproducibility):** `torch.manual_seed` / `torch.cuda.manual_seed_all` now run BEFORE any model
  construction in `src/p3_baselines.py` (models were previously built before the seed call). Deep baselines
  re-run; verified reproducible (2 identical runs). Old deep numbers invalidated (see p3_baseline_report.md).
- **FIX-2 (threshold leakage):** All success definitions unified to the pre-registered **absolute** threshold
  `ON>=0.5 AND OFF<=0.5` (test-independent). Removed the leaky per-target top-20% ON/OFF quantile that
  touched test data from P2/P3/P4-E1. Re-ran P2 (oracle/random sanity), P3 (8 baselines), P4 (E1/E2/E5).
- **FIX-3 (data disclosure):** Added `docs/data_reconciliation.md` — discloses that the sequence-mapped
  paired canonical set is 52,861 (< contract's ≥70k), that the official 91,534 QC2 labels are preserved
  (`raw/npz/scaling_data.npz`) but not sequence-mappable, and documents the reconstruction path. No labeled
  record is fail-closed-dropped; coordinate-unresolved labeled rows are retained (`coordinate_status=no_coord`).
- **FIX-4 (release):** Added `scripts/download_data.sh` (relative-path downloads of primary CSV, official QC2
  npz, VISTA external set). Dockerfile present; image build pending docker-group authorization.
- **FIX-5 (governance):** Added CHANGELOG.md, docs/pollution_statement.md, logs/ run records; extended
  metric unit tests (bootstrap CI, runner, rank metrics).

## [0.1.0] — 2026-08-19 — Initial benchmark (P0–P5)
- P0 Gate-0 GO decision pack (8 deliverables).
- P1 canonical_records.parquet (92,731 rows; 87,989 with absolute coordinates), provenance registry,
  license matrix, exclusion ledger, sha256 manifest.
- P2 source-disjoint splits (overlap=0), leakage report, oracle/random sanity, metric tests.
- P3 8 baselines / 6 families (this release: numbers superseded by 0.1.1 FIX-1/FIX-2).
- P4 experiments E1–E6 (this release: E1/E2 numbers superseded by 0.1.1 FIX-2).
- P5 runner.py, README, datasheet, leaderboard schema, Dockerfile, paper draft.
