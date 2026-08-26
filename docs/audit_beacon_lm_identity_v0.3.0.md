# BEACON / RNABenchmark 4-LM PRS Identity Reproduction — Audit (2026-08-24)

**Contract ref**: `docs/task_contract_v0.3.0.md` §3.1 (identity reproduction) &
hard rules (GPU-only, no silent CPU fallback, no fabricated numbers, honest
negative records).

## 1. Objective
Reproduce the four pretrained RNA-LM rows of **BEACON Table 3** on the official
**ProgrammableRNASwitches (PRS)** split, using the official
`terry-r123/RNABenchmark` fine-tuning code, and report whether each run falls
within **paper mean ± 2·paper_sd** (§3.1 verdict).

| LM | paper PRS r²_mean (%) |
|----|------------------------|
| BEACON-B512 | 55.20 (0.26) |
| SpliceBERT-MS1024 | 57.72 (0.45) |
| RNA-FM | 55.98 (0.09) |
| UTR-LM-MRL | 57.28 (0.10) |

## 2. Protocol (official, per `scripts/BEACON-B/all_task.sh` PRS block + paper Table 6)
- Full fine-tune of the 3-output regression head (ON/OFF/ON_OFF) on official
  train/val/test CSVs (`train.csv` 73227 / `val.csv` 9153 / `test.csv` 9154).
- Optimizer AdamW, `--fp16`, batch 32, epochs 30, `model_max_length` per model,
  `token_type=single`, warmup 50, eval/save steps as official.
- BEACON-B512 uses the **official pinned lr=1e-5**.
- Opensource LMs (SpliceBERT / RNA-FM / UTR-LM) follow **paper Table 6**: lr
  searched over `[1e-5, 5e-3]` (log grid), selected by **validation** R²
  (`trainer_state.json` `best_metric`, since the script sets
  `metric_for_best_model='r^2_mean'` + `load_best_model_at_end=True`), then **3
  reproducible seeds `[666, 20260821, 20260822]`** at the best lr.
- Metric = mean over 3 seeds of per-output Pearson R² (`eval_r^2_mean`), scaled
  to percent. Offical seed scheme is unpublished; the seed set anchors on the
  official single-run seed 666.

## 3. Deployment & blockers cleared
- **Checkpoints**: all four owner-provided checkpoints verified complete (SHA256),
  transferred to `external_src/RNABenchmark/checkpoint`, **smoke load + forward
  4/4 passed** (2026-08-24). `method_registry.json` checkpoint field:
  `BLOCKED -> available`; `blockers["BEACON LM checkpoints"] -> RESOLVED`.
- **flash_attn**: compiled (sm80+sm90) into `envs/beacon`; required by
  `model/rnalm/modeling_rnalm.py` top-level import.
- **Environment, scientifically-neutral**:
  1. `--attn_implementation eager` (the script default) is used; smoke mirrors
     eager + fp16 to match the real training regime.
  2. `tensorboard` installed (official default `report_to="tensorboard"`).
  3. A 6-line **import-guard** patch to `train_programmable_rna_switches.py`
     wraps the `model.rnalm.*` import so the opensource branches (which never
     reference rnalm symbols) do not hard-require flash_attn. BEACON-B512 branch
     is byte-for-byte unchanged. Loss, optimizer, metrics, architecture untouched.

## 4. Results & verdict (contract §3.1: within_mean ± 2·sd)

| LM | lr | per-seed test r²_mean | repro mean±sd | paper ±2SD | within? |
|----|----|------------------------|---------------|------------|---------|
| SpliceBERT-MS1024 | 1e-4 (search) | [58.06, 58.60, 57.84] | **58.17** ± 0.39 | 57.72 ± 0.90 [56.82, 58.62] | ✅ yes |
| RNA-FM | 5e-5 (recovered search) | [57.56, 57.82, 57.65] | **57.67** ± 0.13 | 55.98 ± 0.18 [55.80, 56.16] | ❌ above |
| UTR-LM-MRL | 5e-4 (search) | [56.79, 55.77, 56.97] | **56.51** ± 0.65 | 57.28 ± 0.20 [57.08, 57.48] | ❌ below |
| BEACON-B512 | 1e-5 (official) | [49.82, 50.97, 50.99] | **50.59** ± 0.67 | 55.20 ± 0.52 [54.68, 55.72] | ❌ below |

Only **SpliceBERT-MS1024** reproduces the paper value within ±2 SD. The other
three are **honest negatives** (two below paper, RNA-FM above paper).

## 5. Incidents & remedies (audited)
- **RNA-FM LR search crash (lr=0.005)**: the sweep aborted on the most unstable
  lr with `subprocess.CalledProcessError`, so no report was written. Fixed by
  making `search_sweep` resilient: a failing lr is recorded as `failed` and the
  sweep continues; `pick_best_lr` skips NaN/None rows (unit-tested). Recovered
  RNA-FM's best lr **5e-5** (validation R² 57.85) from the completed search
  records and re-ran the 3-seed report.
- This is **not** a solver swap or result-flipping retry; it is a resume of the
  interrupted official protocol at the evidence-based best lr.

## 6. Integrity statements (contract hard rules)
- All training/validation on GPU (`--cuda-device`, CUDA assert in adapter, no
  silent CPU fallback).
- No fabricated numbers; every figure above traces to a
  `runs/v0.3.0/beacon_identity_<MODEL>_*/identity_results.json` + per-seed
  `test_results.json` + `trainer_state.json`.
- Per contract §14.x: 3 negative identity results are **terminal for any
  superiority claim** of those LMs from these runs; they are recorded honestly
  and **not re-run to flip the verdict**.

## 7. Artifacts
- Adapter + tests: `src/v03_beacon_identity.py`, `tests/test_v03_beacon_identity.py` (20 pass).
- Orchestration: `run_opensource_seq.sh`, `run_beacon_seq.sh`.
- Registry: `outputs/v0.3.0/method_registry.json` (checkpoint available + identity verdicts).
- Runs: `runs/v0.3.0/beacon_identity_*/*identity_results.json`.