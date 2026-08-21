# ToeholdDesignBench — run log (FIX-5 governance)

## 2026-08-21 — v0.2 reviewer-driven revision (local validation)

- Controlling protocol: `docs/task_contract_v0.2.md`.
- Corrected metric, channel-encoding, runner, multi-seed, BEACON, and VISTA
  scripts were syntax-checked locally.
- `tests/test_metrics.py`: PASS.
- `tests/test_extended.py`: PASS.
- `docs/leaderboard_schema.json` and `docs/study_context_registry.yaml`: parsed.
- Synthetic v0.2 result-to-paper boundary test: PASS, including missing-result
  rejection and opaque RGB figure export.
- Provisional figures were opened and visually inspected at the declared 180 mm
  width. PNG metadata passed RGB/no-alpha/effective-DPI checks; the vector PDF
  had the expected page size and embedded font resource. Palette colors passed
  the white-background contrast screen; method labels and marker shapes provide
  redundant encodings where grayscale separation is weak.
- Full GPU/data execution has not yet been recorded here. Old numerical sections
  below are historical and must not be used in the v0.2 manuscript.

## 2026-08-20 — strict-acceptance remediation re-runs (v0.1.1)

### P2 (absolute threshold) — `src/p2_build.py`
- records 52,861; targets 926; split train 648 / val 138 / test 140; source overlap = 0 (assert passed).
- oracle success@1 = 0.907, random success@1 = 0.314 (absolute threshold ON>=0.5 & OFF<=0.5).
- leakage: source-disjoint = 0.000, row-random = 0.999.
- outputs: processed/split_manifests.json/csv, processed/oracle_sanity.json, processed/leakage_report.html.

### P3 (seeded + absolute threshold) — `src/p3_baselines.py` (run twice for reproducibility)
- run1 == run2 exactly (all 8 baselines identical). B2_mlp s@1 = 0.350 in both runs.
- success@1: random 0.350, gc 0.093, thermo 0.343, mlp 0.350, cnn 0.200, storm 0.214, struct 0.214, targetaware 0.336.
- success@3: thermo 0.700 (best), mlp 0.664, targetaware 0.679; random 0.593.
- output: processed/p3_baselines.json (overwritten with reproducible numbers).

### P4 (absolute threshold) — `src/p4_experiments.py`
- E1: B0_gc rho=-0.200 s@1=0.093; B1_thermo rho=0.136 s@1=0.343; B2_mlp rho=0.108 s@1=0.350.
- E2: source rho=0.108 (leak 0.000) vs row rho=0.103 (leak 0.999).
- E5: ratio 0.992, on_only 0.797, off_only 0.234, pareto 0.805.
- output: processed/p4_experiments.json.
- E3 (unchanged, already clean): processed/p4_e3_transfer.json.
- E4 (seeded): processed/p4_e4_ablation.json. E6: processed/p4_e6_audit.json.

### Metric tests
- tests/test_metrics.py: PASS (all).
- tests/test_extended.py (FIX-5: bootstrap CI, edge cases, runner integration): PASS.

### Data reconciliation (FIX-3)
- docs/data_reconciliation.md written; official QC2 labels preserved at raw/npz/scaling_data.npz.
- No labeled record dropped (all 52,861 admitted_paired retained; coordinate-unresolved kept as no_coord).

### Docker verification (FIX-4, 2026-08-20)
- `docker build` cannot run: user not in docker group (permission denied on /var/run/docker.sock); no passwordless sudo.
- Static verification performed instead:
  - Dockerfile syntax parsed OK via dockerfile-parse (structure: FROM/ENV/RUN/COPY/ENTRYPOINT valid).
  - Base image `pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime` confirmed to exist on Docker Hub (updated 2024-10-29).
- Actual image build pending docker-group/sudo authorization.

### Data upper-bound verification (FIX-3, final)
- Label-column combinations in the primary CSV (virus+TF): ON|OFF|ON_OFF=52,861; OFF-only=22,125; none=12,431; ON-only=5,314.
- ON_OFF == ON - OFF holds exactly on all 52,861 paired rows (max err 0).
- Single-label rows carry NO ON_OFF value, so the identity formula cannot extend them; npz value-matching is ~99% ambiguous; counts-to-ON GBDT (CV R²=0.9998) cannot be applied to rows lacking dual-state counts.
- Conclusion: 52,861 is the upper bound of sequence-mapped dual-label pairs in the public CSV.

## User decisions (2026-08-20) — acceptance closed
- FIX-3 (≥70k): user ACCEPTED the closure = official 91,534 QC2 labels preserved as the ≥70k paired asset
  + primary sequence-mapped set disclosed at 52,861 + reconstruction path documented + zero fail-closed exclusion.
- FIX-4 (Docker): user chose to SKIP the actual image build; static verification (syntax parse OK + base image
  tag exists on Docker Hub) stands as the recorded validation.
- All five FIX items (1–5) are therefore closed per the user's confirmed decisions.
