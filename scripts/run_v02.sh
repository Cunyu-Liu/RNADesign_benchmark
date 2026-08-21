#!/usr/bin/env bash
# Rebuild the v0.2 paper-facing result package from prepared public/derived data.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export TD_BENCH_ROOT="${TD_BENCH_ROOT:-$PROJECT_ROOT/data}"
export TD_BENCH_PROCESSED="${TD_BENCH_PROCESSED:-$TD_BENCH_ROOT/processed}"
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

required=(
  "$TD_BENCH_PROCESSED/canonical_records.parquet"
  "$TD_BENCH_PROCESSED/split_manifests.csv"
  "$TD_BENCH_ROOT/external/beacon_prs/beacon_authoritative_mapping.csv"
  "$TD_BENCH_ROOT/external/mCH_on_off_rank.xlsx"
)
for path in "${required[@]}"; do
  if [ ! -s "$path" ]; then
    echo "missing required prepared data: $path" >&2
    exit 2
  fi
done

python "$PROJECT_ROOT/tests/test_metrics.py"
python "$PROJECT_ROOT/tests/test_extended.py"
python "$PROJECT_ROOT/src/p3_baselines.py"
python "$PROJECT_ROOT/src/p3_robustness.py"
python "$PROJECT_ROOT/src/revision_analysis.py"
python "$PROJECT_ROOT/src/beacon_target_benchmark.py"
python "$PROJECT_ROOT/src/vista_paired_context.py"
python "$PROJECT_ROOT/src/runner.py" \
  --method B1_thermo \
  --out "$TD_BENCH_PROCESSED/runner_B1_thermo_v02"
python "$PROJECT_ROOT/src/build_paper_artifacts.py"

echo "v0.2 core analyses completed in $TD_BENCH_PROCESSED"
