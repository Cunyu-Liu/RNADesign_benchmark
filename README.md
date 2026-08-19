# ToeholdDesignBench — Target-aware Toehold Sensor Design Benchmark

A source-isolated, target-level, design-utility benchmark for prokaryotic translation-activating
toehold RNA sensors. It reframes the Angenent-Mari 2020 (91,534 paired ON/OFF) dataset from a
single-sequence regression task into a **per-target top-K candidate-selection problem**.

Frozen task: given a full target RNA + fixed first-gen-30nt architecture + submission budget K,
rank candidate trigger sites so the top-K contains high-ON / low-OFF, grammar-valid switches —
without access to test labels.

## Repository layout
- `/home/cunyuliu/ToeholdDesignBench` — code (`src/`, `tests/`, `docs/`)
- `/mnt/cunyuliu/ToeholdDesignBench` — data (`raw/`, `processed/`, `external/`), symlinked as `data/`

## Dependencies
conda env `toeholdbench` (Python 3.10, pandas, pyarrow, numpy, scikit-learn, scipy, torch 2.5+cu121).
Reproduce: `conda create -n toeholdbench --clone editflow` (or install per `requirements.txt`).
Data paths can be overridden with `TD_BENCH_PROCESSED=/path/to/processed` (see src/runner.py).

## Data pipeline (automatic download)
```bash
# 1) download public raw assets (Angenent-Mari CSV, official QC2 npz, VISTA external) into ./data
bash scripts/download_data.sh
# 2) build canonical records (coordinate reconstruction uses NCBI efetch, cached in processed/sequences)
python src/build_canonical_final.py
# 3) splits + leakage + oracle/random sanity
python src/p2_build.py
# 4) reproducible baselines (seed=0, torch seeded before model init) and experiments E1-E6
python src/p3_baselines.py
python src/p4_experiments.py
```
> Data disclosure: the sequence-mapped paired canonical set is 52,861 records (of the paper's 91,534
> official paired labels, preserved in `raw/npz/scaling_data.npz` but not sequence-mappable). See
> `docs/data_reconciliation.md` for the full accounting and the reconstruction path to ≥70k.

## Quick reproduction
```bash
cd /home/cunyuliu/ToeholdDesignBench
# metric unit tests (incl. bootstrap CI and runner integration)
python tests/test_metrics.py && python tests/test_extended.py
# evaluate a built-in baseline
python src/runner.py --method B1_thermo
# evaluate an external submission (record_id,score CSV)
python src/runner.py --method my_method --scores my_scores.csv
```

## Key results (source-disjoint split, seed=0)
- Prediction correlation (Spearman ρ) and design utility (success@1) rank models inconsistently (E1).
- Row-random split leaks 99.9% of test sources (source-disjoint = 0%); source-disjoint is mandatory (E2).
- OFF-only ranking is unsuitable; ON/ratio/Pareto are far stronger (E5).

## Provenance / versioning
- `processed/hash_manifest.json` — sha256 of canonical artifacts.
- `processed/license_matrix.csv`, `processed/exclusion_ledger.csv` — data governance.
- `docs/study_context_registry.yaml` — assay/reporter/host/context registry.

## Allowed claims (per evidence)
R1 only ⇒ "source-isolated fused-context candidate-site ranking benchmark". R1+R2 ⇒ cross-context
target-aware prioritization. R1+R2+P1 ⇒ prospective hit-rate comparison (requires wet-lab).
Forbidden: "first AI toehold design", "first target-aware method", "OFF low ⇒ specific", circular validation.