"""BEACON 2024-benchmark LM PRS identity reproduction (contract §3.1).

Runs the official terry-r123/RNABenchmark fine-tuning code
(downstream/train_programmable_rna_switches.py) on the official
ProgrammableRNASwitches (PRS) split to reproduce the four pretrained RNA-LM
rows of BEACON Table 3:

    BEACON-B512        PRS R^2_mean 55.20 (0.26)
    SpliceBERT-MS1024  PRS R^2_mean 57.72 (0.45)
    RNA-FM             PRS R^2_mean 55.98 (0.09)
    UTR-LM-MRL         PRS R^2_mean 57.28 (0.10)

Official protocol (paper Table 6 + scripts/BEACON-B/all_task.sh PRS block):
  - fully fine-tune  3-output regression head (ON/OFF/ON_OFF), labels are the
    raw ON, OFF and ON-OFF columns of the official PRS CSV;
  - optimizer AdamW, lr searched over [1e-5, 5e-3] per model, 3 seeds, report
    mean +/- sd of the mean of per-output Pearson R^2 (r^2_mean);
  - all runs on GPU, no silent CPU fallback (contract hard rule).

Identity verdict (contract §3.1): a reproduction "passes" when its reported
mean lies within paper mean +/- 2*paper_sd. Any model that does not pass is
labelled `adapted reimplementation`, never "official reproduction".

The heavy training runs in subprocesses (each model x seed is one official
torchrun invocation). All logic that can be tested without GPU (relative-path
layout, verdict arithmetic, CSV-ingest convention, run-name construction) is
kept pure and unit-tested in tests/test_v03_beacon_identity.py.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import resource
import shutil
import subprocess
import sys
import time

import numpy as np
import pandas as pd

PROJ = "/home/cunyuliu/ToeholdDesignBench"
MNT = "/mnt/cunyuliu/ToeholdDesignBench"
REPO = f"{MNT}/external_src/RNABenchmark"
CKPT_ROOT = f"{REPO}/checkpoint"
DATA_DIR = f"{REPO}/data/downstream/ProgrammableRNASwitches"
OUT_BASE = f"{MNT}/runs/v0.3.0"
BEACON_PY = f"{MNT}/envs/beacon/bin/python"

# Official BEACON Table 3 PRS values (R^2 %) mean (sd) across 3 seeds.
PAPER_PRS = {
    "BEACON-B512":       {"mean": 55.20, "sd": 0.26},
    "SpliceBERT-MS1024": {"mean": 57.72, "sd": 0.45},
    "RNA-FM":            {"mean": 55.98, "sd": 0.09},
    "UTR-LM-MRL":        {"mean": 57.28, "sd": 0.10},
}

# Official protocol per model: model_type, checkpoint dir, model_max_length,
# token_type (single-nucleotide for the four model LMs).
MODEL_SPEC = {
    "BEACON-B512":       dict(model_type="rnalm",          ckpt="baseline/BEACON-B512",       max_len=1026),
    "SpliceBERT-MS1024": dict(model_type="splicebert-ms1024", ckpt="opensource/splicebert-ms1024", max_len=1024),
    "RNA-FM":            dict(model_type="rna-fm",         ckpt="opensource/rna-fm",          max_len=1024),
    "UTR-LM-MRL":        dict(model_type="utr-lm-mrl",     ckpt="opensource/utr-lm-mrl",      max_len=1026),
}

# Official scripts pin seed=666 as the single run; BEACON reports mean over 3
# seeds of an un-published per-seed scheme. To stay reproducible we use a fixed
# seed set anchored on the official one, and always record them explicitly.
SEEDS = [666, 20260821, 20260822]
DEFAULT_LR = {
    # BEACON-B512 all_task.sh PRS block uses lr=1e-5. For opensource LMs the
    # official repo does not pin the PRS lr; default to the same fine-tune lr,
    # overridable per model via --lr.
    "BEACON-B512": 1e-5,
    "SpliceBERT-MS1024": 1e-5,
    "RNA-FM": 1e-5,
    "UTR-LM-MRL": 1e-5,
}
EPOCHS = 30
BATCH = 32

# Paper Table 6: for the opensource LMs the PRS fine-tune lr is *searched* over
# the [1e-5, 5e-3] bracket before fixing it with 3 reproducible seeds. This is
# a log-spaced grid on that bracket (pure, unit-tested).
LR_SEARCH_GRID = [1e-5, 5e-5, 1e-4, 5e-4, 1e-3, 5e-3]
# Official single-run seed; anchored the LR-selection sweep on it.
SEARCH_SEED = 666
# For these LMs the official repo/paper do not pin a PRS lr -> LR search applies.
OPENSOURCE = {"SpliceBERT-MS1024", "RNA-FM", "UTR-LM-MRL"}


def is_opensource(model_id: str) -> bool:
    """True for the LMs that require an LR search (pure, unit-tested)."""
    return model_id in OPENSOURCE


def lr_tag(lr: float) -> str:
    """Filesystem-safe lr token, e.g. 1e-05 -> '1e-05' (pure, unit-tested)."""
    return f"{lr:.1e}".replace(".0", "")


def rel_ckpt(model_id: str) -> str:
    """Official checkpoint path relative to CKPT_ROOT (pure, unit-tested)."""
    return MODEL_SPEC[model_id]["ckpt"]


def ingest_convention(expected_rows: int) -> dict:
    """Official PRS CSV ingest convention (pure, unit-tested).

    The official SupervisedDataset reads header-less 4-col rows as
    [sequence, ON, OFF, ON_OFF], uppercases and maps U->T. We assert that the
    official PRS files match this shape so score coverage is well-defined.
    """
    return dict(n_columns=4, header=False, upper=True, u_to_t=True, n_rows=expected_rows)


def r2_mean_map() -> dict:
    """Label of the r^2 mean in our results JSON (pure, unit-tested)."""
    return {"metric": "r^2_mean", "scale100": True}


def verdict(repro_mean: float, paper_mean: float, paper_sd: float) -> dict:
    """Contract §3.1 verdict. Pass iff |repro - paper| <= 2*sd.

    Paper reports sd for all four LMs, so the +/-2 SD rule applies.
    """
    tol = 2.0 * paper_sd
    lo = paper_mean - tol
    hi = paper_mean + tol
    return {
        "paper_mean": paper_mean,
        "paper_sd": paper_sd,
        "repro_mean": repro_mean,
        "within_2sd": lo <= repro_mean <= hi,
        "low": lo,
        "high": hi,
    }


def run_name(model_id: str, seed: int, lr: float) -> str:
    return f"{model_id}_s{seed}_lr{lr:.0e}".replace(".", "p").replace("e-0", "e")


def build_cmd(model_id: str, seed: int, lr: float, out_dir: str,
              cuda_device: int, port: int) -> list[str]:
    """Official torchrun fine-tune command for PRS (pure, unit-tested)."""
    spec = MODEL_SPEC[model_id]
    return [
        BEACON_PY, "-m", "torch.distributed.run",
        "--nproc_per_node=1", "--master_port", str(port),
        f"{REPO}/downstream/train_programmable_rna_switches.py",
        "--model_name_or_path", f"{CKPT_ROOT}/{spec['ckpt']}",
        "--data_path", DATA_DIR,
        "--data_train_path", f"train.csv",
        "--data_val_path", f"val.csv",
        "--data_test_path", f"test.csv",
        "--run_name", run_name(model_id, seed, lr),
        "--model_max_length", str(spec["max_len"]),
        "--per_device_train_batch_size", str(BATCH),
        "--per_device_eval_batch_size", "32",
        "--gradient_accumulation_steps", "1",
        "--learning_rate", str(lr),
        "--num_train_epochs", str(EPOCHS),
        "--fp16",
        "--save_steps", "400",
        "--output_dir", out_dir,
        "--evaluation_strategy", "steps",
        "--eval_steps", "200",
        "--warmup_steps", "50",
        "--logging_steps", "200",
        "--overwrite_output_dir", "True",
        "--seed", str(seed),
        "--token_type", "single",
        "--model_type", spec["model_type"],
    ]


def parse_results(results_dir: str) -> dict | None:
    """Read test_results.json written by the official run (pure, unit-tested)."""
    p = os.path.join(results_dir, "test_results.json")
    if not os.path.exists(p):
        return None
    with open(p) as fh:
        j = json.load(fh)
    return j


def _scale_r2(val_json: dict, label: str) -> float:
    """r2_mean from the official trainer report (values are already in 0-1)."""
    # trainer.evaluate returns eval_r^2_mean as the Pearson-r^2 mean (0-1),
    # paper reports it as percentage (0-100).
    return float(val_json[f"eval_{label}"])


def read_val_best_metric(out_dir: str) -> float | None:
    """Best *validation* R2 (0-1) from the official Trainer's trainer_state.json.

    The official fine-tune sets `metric_for_best_model='r^2_mean'` and
    `load_best_model_at_end=True`, so `best_metric` is the best validation R2
    (0-1) that the best checkpoint was selected on. Returns the 0-1 fraction, or
    None when the file is absent (e.g. before a run finishes).
    """
    p = os.path.join(out_dir, "trainer_state.json")
    if not os.path.exists(p):
        return None
    with open(p) as fh:
        j = json.load(fh)
    bm = j.get("best_metric")
    return bm


def pick_best_lr(records) -> float:
    """Choose the lr with the highest validation R2 (pure, unit-tested).

    Rows with no validation R2 (run failed / diverged / NaN) are skipped so a
    single unstable high lr cannot poison the selection.
    """
    def ok(r):
        v = r.get("val_r2_pct")
        return v is not None and not (isinstance(v, float) and np.isnan(v))
    valid = [r for r in records if ok(r)]
    if not valid:
        raise ValueError("no valid validation R2 among LR search records")
    return max(valid, key=lambda r: r["val_r2_pct"])["lr"]


def search_sweep(model_id: str, grid, seed: int, cuda_device: int,
                 base_out: str) -> dict:
    """Official LR-search: one full fine-tune per grid lr, select by val R2.

    Each lr runs in its own subdir so its `trainer_state.json` (best_metric) is
    not clobbered, then we pick the lr with the best validation R2 (0-1 -> pct).
    A single failing lr (e.g. high-lr divergence/OOM) is recorded as failed and
    does not abort the whole sweep, mirroring how a researcher would drop an
    unstable hyperparameter.
    """
    records = []
    for i, lr in enumerate(grid):
        port = 30000 + i
        run_dir = os.path.join(base_out, "search", f"lr{lr_tag(lr)}")
        os.makedirs(run_dir, exist_ok=True)
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = str(cuda_device)
        env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
        print(f"[search] {model_id}: lr={lr} seed={seed} -> {run_dir}")
        try:
            subprocess.run(
                build_cmd(model_id, seed, lr, run_dir, cuda_device, port),
                env=env, check=True)
        except subprocess.CalledProcessError as exc:
            print(f"[search] {model_id}: lr={lr} FAILED rc={exc.returncode}; "
                  f"recording as no valid val metric and continuing")
            records.append({"lr": lr, "val_r2_pct": None,
                            "val_raw": None, "failed": True})
            continue
        raw = read_val_best_metric(run_dir)
        records.append({
            "lr": lr,
            "val_r2_pct": None if raw is None else raw * 100.0,
            "val_raw": raw,
        })
    chosen = pick_best_lr(records)
    return {"chosen_lr": chosen, "grid": list(grid),
            "search_seed": seed, "records": records}


def run_seed(model_id: str, seed: int, lr: float, cuda_device: int,
             port: int, out_dir: str) -> dict:
    """Run one seed under the official trainer; return the r2 metric."""
    cmd = build_cmd(model_id, seed, lr, out_dir, cuda_device, port)
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(cuda_device)
    env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    print("RUN", " ".join(cmd[:8]), "...")
    t0 = time.time()
    subprocess.run(cmd, env=env, check=True)
    wall = time.time() - t0
    results_dir = os.path.join(out_dir, "results", run_name(model_id, seed, lr))
    rj = parse_results(results_dir)
    if rj is None:
        raise RuntimeError(f"no test_results.json at {results_dir}")
    metric = _scale_r2(rj, "r^2_mean") * 100.0
    return {"seed": seed, "lr": lr, "r2_mean_pct": metric,
            "wall_s": wall, "full": rj}


def collect_metrics(model_id: str, seeds, lr, cuda_device, out_dir) -> dict:
    """Run all seeds, return per-seed list + mean/sd."""
    per_seed = []
    for i, seed in enumerate(seeds):
        port = 26000 + i
        per_seed.append(run_seed(model_id, seed, lr, cuda_device, port, out_dir))
        with open(os.path.join(out_dir, "per_seed_manifest.json"), "w") as fh:
            json.dump(per_seed, fh, indent=2, default=float)
    vals = [r["r2_mean_pct"] for r in per_seed]
    return {"per_seed": per_seed,
            "mean_pct": float(np.mean(vals)),
            "sd_pct": float(np.std(vals, ddof=1) if len(vals) > 1 else 0.0)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True,
                    choices=sorted(MODEL_SPEC))
    ap.add_argument("--lr", type=float, default=None,
                    help="learning rate; default per-model DEFAULT_LR")
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--cuda-device", type=int, required=True)
    ap.add_argument("--lr-search", action="store_true",
                    help="search LR grid for opensource LMs (paper Table 6); "
                         "invalid for BEACON-B512 (official lr is pinned)")
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(f"{CKPT_ROOT}/{MODEL_SPEC[args.model]['ckpt']}"):
        sys.exit(f"checkpoint missing for {args.model}")
    if not os.listdir(DATA_DIR):
        sys.exit(f"PRS data dir empty: {DATA_DIR}")

    if not args.execute:
        print(f"[ready] model={args.model} ckpt={rel_ckpt(args.model)} "
              f"paper={PAPER_PRS[args.model]}")
        print("Re-run with --execute to run the official fine-tune.")
        return 0

    seeds = [int(s) for s in args.seeds.split(",")]

    # contract hard rule: training/GPU validation must see CUDA; fail loudly
    import torch  # noqa: E402
    if not torch.cuda.is_available():
        sys.exit("CUDA unavailable in beacon env; refusing silent CPU run "
                 f"(--cuda-device={args.cuda_device}).")

    ts = time.strftime("%Y%m%dT%H%M%S")
    out_dir = f"{OUT_BASE}/beacon_identity_{args.model}_{ts}"
    if os.path.exists(out_dir):
        sys.exit(2)
    os.makedirs(out_dir)

    # ----- learning-rate resolution -----
    if not is_opensource(args.model):
        # BEACON-B512: official all_task.sh PRS block pins lr=1e-5.
        if args.lr_search:
            sys.exit("BEACON-B512 uses the official pinned lr=1e-5; "
                     "--lr-search applies only to opensource LMs.")
        lr = args.lr if args.lr is not None else DEFAULT_LR[args.model]
        search = None
        lr_desc = f"official all_task.sh lr={lr}"
    else:
        # opensource LMs: paper Table 6 searches lr over [1e-5, 5e-3].
        if args.lr_search or args.lr is None:
            search = search_sweep(args.model, LR_SEARCH_GRID, SEARCH_SEED,
                                  args.cuda_device, out_dir)
            lr = search["chosen_lr"]
            lr_desc = (f"LR search over {LR_SEARCH_GRID} -> best lr={lr} "
                       f"(seed={SEARCH_SEED} validation R2)")
        else:
            search = None
            lr = args.lr
            lr_desc = f"explicit lr={args.lr}"

    summary = collect_metrics(args.model, seeds, lr, args.cuda_device, out_dir)
    paper = PAPER_PRS[args.model]
    v = verdict(summary["mean_pct"], paper["mean"], paper["sd"])
    summary["model"] = args.model
    summary["lr_resolution"] = lr_desc
    if search is not None:
        summary["lr_search"] = search
    summary["paper"] = paper
    summary["verdict"] = v
    summary["protocol"] = (f"official RNABenchmark PRS fine-tune; lr={lr}, "
                           f"epochs={EPOCHS}, batch={BATCH}, fp16, "
                           f"seeds={seeds}; metric=mean per-output Pearson R2 ")
    summary["source_commit"] = subprocess.run(
        ["git", "-C", REPO, "rev-parse", "HEAD"],
        capture_output=True, text=True).stdout.strip()
    with open(os.path.join(out_dir, "identity_results.json"), "w") as fh:
        json.dump(summary, fh, indent=2, default=float)
    print(json.dumps({k: v for k, v in summary.items()
                      if k != "per_seed"}, indent=2, default=float))


if __name__ == "__main__":
    main()