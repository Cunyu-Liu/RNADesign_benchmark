# CHANGELOG

All notable changes to ToeholdDesignBench are documented here. Versioning follows Semantic Versioning.

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