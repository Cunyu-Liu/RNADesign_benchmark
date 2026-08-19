# ToeholdDesignBench — run log (FIX-5 governance)

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