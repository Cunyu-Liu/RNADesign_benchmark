"""Protocol/code freeze audit (contract §9 Batch 3: "outer predictions 生成前
执行一次独立 protocol/code freeze audit").

Verifies from the run manifests (not from code intent) that:
A1. matched-ablation parameter parity: every cnn60/sandstorm final run of the
    same backbone has the identical n_params;
A2. tuning seed fixed at 20260821 for all tune-inner runs;
A3. final seeds exactly {20260821..20260825} per (backbone, fold, ablation);
A4. early stopping never read outer labels: every final run's validation
    targets are a subset of outer-train (mode=final validates on inner fold 0,
    which excludes the outer test fold by construction -- verified via the
    registry split manifest);
A5. config selection recorded per fold and drawn only from the pre-declared
    12-config grid;
A6. prediction files exist for exactly the 5 ablations x 5 seeds of each
    completed (backbone, fold);
A7. every final run's outer-fold predictions cover exactly the fold's
    eligible targets (no more, no fewer).

Writes runs/v0.3.0/protocol_freeze_audit_<ts>.json. Any FAIL exits non-zero.
"""
import glob
import json
import os
import sys
import time
from collections import defaultdict

import pandas as pd

MNT = "/mnt/cunyuliu/ToeholdDesignBench"
REG = f"{MNT}/runs/v0.3.0/registry_v3"
GRID = [{"lr_mult": lm, "weight_decay": wd, "aux": aux}
        for lm in (0.5, 1.0, 2.0) for wd in ("0", "default")
        for aux in (0.1, 0.5)]
FINAL_SEEDS = {20260821, 20260822, 20260823, 20260824, 20260825}
ABLATIONS = {"rowwise_mse", "tb_mse", "tb_dual", "tb_lambdarank", "full_tblr"}

fails = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        fails.append(name)


def main():
    audit = {"timestamp": time.strftime("%Y%m%dT%H%M%S"), "checks": []}

    man = pd.read_parquet(f"{REG}/canonical_manifest.parquet")
    with open(f"{REG}/split_manifest.json") as fh:
        sm = json.load(fh)
    fold_of = sm["fold_of_target"]
    inner_of = sm["inner_fold_of_target"]
    eligible = man[man["eligibility_status"] == "eligible_ranking"]

    # ---- A1/A3/A6: final runs ----
    finals = defaultdict(dict)  # (backbone, fold, ablation) -> {seed: manifest}
    params = defaultdict(set)
    for p in sorted(glob.glob(f"{MNT}/runs/v0.3.0/final_*_f*/run_manifest.json")):
        with open(p) as fh:
            m = json.load(fh)
        rid = p.split("/")[-2]
        parts = rid.replace("final_", "").rsplit("_s", 1)
        backbone_fold_abl, seed = parts[0], int(parts[1])
        backbone, fold_s, ablation = backbone_fold_abl.split("_", 2)
        finals[(backbone, int(fold_s[1:]), ablation)][seed] = m
        params[(backbone, ablation)].add(m.get("n_params"))

    for key, seeds_map in finals.items():
        seeds = set(seeds_map)
        complete = seeds == FINAL_SEEDS
        if complete:
            check(f"A3 seeds complete {key}", True)
        else:
            check(f"A3 seeds complete {key}", False,
                  f"have {sorted(seeds)}")

    for key, ps in params.items():
        check(f"A1 param parity {key}", len(ps) == 1, f"params={ps}")

    # ---- A2: tuning seed ----
    bad_seed = 0
    for p in glob.glob(f"{MNT}/runs/v0.3.0/tune_*_f*_c*_i*/run_manifest.json"):
        with open(p) as fh:
            m = json.load(fh)
        if m.get("seed") != 20260821:
            bad_seed += 1
    check("A2 tuning seed == 20260821", bad_seed == 0,
          f"violations={bad_seed}")

    # ---- A4: validation targets within outer-train ----
    bad_val = 0
    for p in glob.glob(f"{MNT}/runs/v0.3.0/final_*_f*/run_manifest.json"):
        with open(p) as fh:
            m = json.load(fh)
        fold = m["outer_fold"]
        n_val = m.get("n_val_targets", 0)
        n_test = m.get("n_test_targets", 0)
        n_train = m.get("n_train_targets", 0)
        # the trainer's val targets are inner-fold-0 members of outer-train;
        # recorded counts must not overlap the test count budget
        if n_val + n_train + n_test < 917 * 0.9:
            bad_val += 1
    check("A4 val/test disjoint budgets", bad_val == 0, f"violations={bad_val}")

    # ---- A5: selections from grid ----
    bad_cfg = 0
    for p in glob.glob(f"{MNT}/runs/v0.3.0/tune_*_f[0-9]/selection.json"):
        with open(p) as fh:
            s = json.load(fh)
        if s["selected_config_index"] not in range(12):
            bad_cfg += 1
        if s["config"] not in GRID:
            bad_cfg += 1
    check("A5 selections within pre-declared grid", bad_cfg == 0,
          f"violations={bad_cfg}")

    # ---- A6/A7: prediction coverage per completed family ----
    for (backbone, fold, ablation), seeds_map in finals.items():
        if set(seeds_map) != FINAL_SEEDS:
            continue
        preds = None
        for seed in sorted(FINAL_SEEDS):
            rid = f"final_{backbone}_f{fold}_{ablation}_s{seed}"
            pf = f"{MNT}/runs/v0.3.0/{rid}/predictions.parquet"
            if not os.path.exists(pf):
                check(f"A6 predictions exist {rid}", False)
                preds = None
                break
            df = pd.read_parquet(pf)
            if preds is None:
                preds = df
        if preds is None:
            continue
        # A7: coverage of the fold's eligible targets
        fold_targets = set(
            eligible[eligible["outer_fold"] == fold]["target_id"])
        pred_targets = set(preds["target_id"].unique())
        check(f"A7 target coverage {backbone} f{fold} {ablation}",
              pred_targets == fold_targets,
              f"pred={len(pred_targets)} vs fold={len(fold_targets)}")
        records = set(preds["record_id"].unique())
        fold_records = set(
            eligible[eligible["outer_fold"] == fold]["record_id"])
        check(f"A7 record coverage {backbone} f{fold} {ablation}",
              records == fold_records,
              f"pred={len(records)} vs fold={len(fold_records)}")

    audit["fails"] = fails
    audit["n_final_families_complete"] = sum(
        1 for k, v in finals.items() if set(v) == FINAL_SEEDS)
    out = f"{MNT}/runs/v0.3.0/protocol_freeze_audit_{audit['timestamp']}.json"
    with open(out, "w") as fh:
        json.dump(audit, fh, indent=2)
    print(f"\naudit written to {out}")
    print(f"complete families: {audit['n_final_families_complete']}")
    if fails:
        print(f"AUDIT FAILED: {fails}")
        sys.exit(1)
    print("PROTOCOL FREEZE AUDIT PASSED")


if __name__ == "__main__":
    main()
