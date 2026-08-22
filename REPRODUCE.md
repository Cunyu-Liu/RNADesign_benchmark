# REPRODUCE.md — ToeholdDesignBench v0.3.0

Clean-environment full reproduction guide (contract §9 Batch 2/4).
All commands are run from the project root (`/home/cunyuliu/ToeholdDesignBench`);
every path in the commands below is either relative to that root or an absolute
`/mnt` artifact path, so directory changes never break a step.

## 0. Layout

- Code + git: `/home/cunyuliu/ToeholdDesignBench` (branch `reviewer-revision-v0.3`)
- Large artifacts: `/mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/<run_id>/`
  (immutable; a run refuses to overwrite an existing directory)
- Environments:
  - `toeholdbench`: `/home/cunyuliu/miniconda3/envs/toeholdbench/bin/python`
    (numpy/pandas/pyarrow/torch/lightgbm/scipy/sklearn; evaluator + CNN/SANDSTORM training)
  - `rnaelectra`: `/mnt/cunyuliu/ToeholdDesignBench/envs/rnaelectra/bin/python`
    (torch 2.5.1+cu121, transformers 4.49.0 — required for the RNAElectra checkpoint;
    the toeholdbench env has transformers 5.x which cannot load it)
  - `sandstorm_official` (TF 2.11 GPU): official SANDSTORM identity reproduction
- GPU policy: training/validation must see CUDA; scripts exit with a distinct
  code on CUDA-requested-but-unavailable (no silent CPU fallback). Note
  `CUDA_DEVICE_ORDER=PCI_BUS_ID` is required for CUDA indices to match
  `nvidia-smi` indices on this server.

## 1. Test suite (single entry, discovery-based count)

```bash
./run_v03.sh
```

Runs the full pytest suite and prints the discovered test count (never
hand-written in the manuscript).

## 2. Data acquisition (traceable)

```bash
# crowdsourced 100-regulator preprint supplementary (PMC13370501, PoW-solved)
/home/cunyuliu/miniconda3/envs/toeholdbench/bin/python \
  scripts/download_crowdsourced.py \
  --out /mnt/cunyuliu/ToeholdDesignBench/external_data/crowdsourced

# Toehold-VISTA NAR 2026 supplementary (SARS-CoV selection groups)
/home/cunyuliu/miniconda3/envs/toeholdbench/bin/python \
  scripts/download_vista_nar.py \
  --out /mnt/cunyuliu/ToeholdDesignBench/external_data/vista_nar
```

Non-redistributable assets (canonical CSV via CC BY 4.0 pipeline, VISTA mCherry
workbook, BEACON data) are acquired by the scripts/ledgers under
`/mnt/cunyuliu/ToeholdDesignBench/external*`; accessions are recorded in
`docs/study_context_registry.yaml` and the registry ledgers.

## 3. Batch 1 — registry freeze

```bash
/home/cunyuliu/miniconda3/envs/toeholdbench/bin/python src/v03_registry.py
```

Outputs `runs/v0.3.0/registry_v3/` (canonical_manifest, split_manifest,
ledgers). v1/v2 registries are retained for audit only.

## 4. Batch 2 — single evaluator

Covered by `./run_v03.sh` (all analyses consume `src/toeholdbench/`).

## 5. Batch 3 — models, ablations, baselines, audits

```bash
PY=/home/cunyuliu/miniconda3/envs/toeholdbench/bin/python

# official identity reproductions (original split/metric)
$PY src/v03_sandstorm_identity.py        # SANDSTORM + Valeri CNN

# biophysical baselines (LightGBM seq/biophys/combined, GC, thermo)
$PY src/v03_biophys.py

# BEACON fixed-capacity masking (one variant per invocation)
$PY src/v03_beacon_masks.py --variant trigger_only --run-id beacon_mask_trigger_only_f0

# controlled leakage experiment (5 seeds, paired arms)
$PY src/v03_leakage.py

# TBLR family tuning + finals (one backbone x one outer fold per stream)
#   --cuda-device selects the physical GPU (PCI order); default is the MIG slice
$PY src/v03_tune.py --backbone cnn60     --outer-fold 0 --phase all --cuda-device 2
$PY src/v03_tune.py --backbone sandstorm --outer-fold 0 --phase all --cuda-device 2
# rnaelectra streams automatically use the dedicated transformers-4.49 env
$PY src/v03_tune.py --backbone rnaelectra --outer-fold 0 --phase all --cuda-device 2

# family evaluation (all folds x ablations x seeds vs baselines)
$PY src/v03_eval_family.py --backbone cnn60 \
    --extra /mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/biophys_20260822T023805/predictions.parquet
$PY src/v03_eval_family.py --backbone sandstorm \
    --extra /mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/biophys_20260822T023805/predictions.parquet

# independent protocol/code freeze audit (manifest-based)
$PY src/v03_freeze_audit.py
```

## 6. Batch 4 — external tracks

```bash
PY=/home/cunyuliu/miniconda3/envs/toeholdbench/bin/python

# frozen canonical-transfer models (no external labels read)
$PY src/v03_transfer.py --backbone cnn60     --run-id transfer_cnn60     --device cuda:0
$PY src/v03_transfer.py --backbone sandstorm --run-id transfer_sandstorm --device cuda:0

# VISTA mCherry native site ranking
$PY src/v03_vista.py --transfer-run transfer_cnn60

# crowdsourced 100-regulator architecture-shift track (Spearman + cluster bootstrap)
$PY src/v03_crowd.py --backbones cnn60 sandstorm

# VISTA SARS-CoV selection groups (selection-conditioned description)
$PY src/v03_vista_sars.py

# method x dataset exposure matrix + method registry
$PY src/v03_exposure_matrix.py
$PY src/v03_method_registry.py
```

## 7. Watchdog (optional, long families)

```bash
$PY -u src/v03_watchdog.py
```

Start-only stream supervisor: relaunches dead orchestrator streams
(resume-safe — completed run manifests are skipped) and advances the
rnaelectra fold queue with bounded concurrency. Never kills processes.

## 8. Manuscript number-provenance audit

After the paper draft is updated, verify every manuscript number traces to
a run artifact (exits nonzero on any mismatch):

```bash
$PY src/v03_number_audit.py
```

## 9. Acceptance evidence (as of 2026-08-22)

- `./run_v03.sh`: full suite green (discovery-based count reported by the script)
- `runs/v0.3.0/protocol_freeze_audit_*.json`: PASSED (parameter parity, fixed
  seeds, config grids, per-fold target AND record coverage for all completed
  families)
- `runs/v0.3.0/eval_cnn60_family/`, `eval_sandstorm_family/`: 5 folds x
  5 objectives x 5 seeds each; primary contrasts in `contrasts.csv`
- `runs/v0.3.0/crowd_external_*/`: exposure 0/100; Spearman + cluster
  bootstrap CIs in `spearman_summary.csv`
- `runs/v0.3.0/vista_sars_*/`, `runs/v0.3.0/vista_external_*/`: execution
  manifests record single-target / selection-conditioned boundaries
- `runs/v0.3.0/exposure_matrix/`: 26 methods x 5 datasets

Known pending assets (recorded in the method registry, never silently
omitted): BEACON 2024 LM checkpoints (network-blocked), GARDN design dump
(Zenodo-blocked), RNAElectra family finals (in flight).
