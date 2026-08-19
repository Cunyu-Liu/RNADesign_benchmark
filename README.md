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

## Data pipeline
1. **raw** — `raw/Toehold_Dataset_Final_2019-10-23.csv` (Angenent-Mari 2020, CC BY 4.0, LFS sha256 `1b3aec89…`).
2. **canonical build** — `src/data/build_canonical.py` → `processed/canonical_pilot.parquet` (92,731 virus+TF records, 931 targets).
3. **coordinate reconstruction** — `src/data/map_virus_genomes.py` / `map_tf.py` (resolve NCBI accessions,
   map 30-nt triggers) + `src/build_canonical_final.py` → `processed/canonical_records.parquet`
   (87,989 / 92,731 = 94.9% with absolute window_start/end + strand + source_accession).
4. **splits** — `src/p2_build.py` → `processed/split_manifests.json/csv` (source-disjoint 70/15/15, overlap=0).
5. **metrics** — `src/metrics/metrics.py` (success@K, NDCG@K, normalized regret, Pareto front; target-level bootstrap CI).

## Baselines (P3) & experiments (P4)
- `src/p3_baselines.py` — 8 baselines / 6 families (random, GC rule, thermodynamic RBS/MFE, Angenent-Mari MLP/CNN,
  STORM/NuSpeak-equiv, SANDSTORM-equiv seq+structure, VISTA-like structure-rich).
- `src/p4_experiments.py` — E1 prediction!=design, E2 split stress, E5 ratio pathology.
- Reports: `docs/p3_baseline_report.md`, `docs/p4_report.md`.

## Quick reproduction
```bash
cd /home/cunyuliu/ToeholdDesignBench
# metric unit tests
python tests/test_metrics.py
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