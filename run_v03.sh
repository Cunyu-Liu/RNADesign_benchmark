#!/usr/bin/env bash
# ToeholdDesignBench v0.3.0 single execution entry (contract §9 Batch 2).
# Test discovery: the test count is auto-reported, never hand-written.
set -euo pipefail
cd "$(dirname "$0")"

PY=/home/cunyuliu/miniconda3/envs/toeholdbench/bin/python
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"

echo "=== environment ==="
"$PY" --version
"$PY" -c "import numpy, pandas, pyarrow; print('numpy', numpy.__version__, '| pandas', pandas.__version__)"

echo "=== full test suite (discovery-based) ==="
"$PY" -m pytest tests/ -q --tb=short

echo "=== test count ==="
"$PY" -m pytest tests/ --collect-only -q 2>/dev/null | tail -1
