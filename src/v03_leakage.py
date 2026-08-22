"""Controlled leakage experiment (contract §9 Batch 3, §6 leakage rules).

Design (frozen):
- Test fold 0; "candidate-rich" = test targets with >= 10 eligible candidates.
- Per eval target: a seed-frozen random 20% of its eligible candidates are the
  FIXED evaluation candidates (identical in both arms and in all seeds).
- Leaky arm:  outer-train rows + the remaining 80% same-target rows
  ("neighboring windows") added to training.
- Clean arm:  outer-train rows + an equal number of replacement rows sampled
  from training-fold targets that are target-cluster-disjoint from every eval
  target (guaranteed by the cluster-split) and matched per eval target by
  candidate count and ON-OFF label stratification.
- Both arms have identical row counts and identical evaluation candidates.
- Model: cnn60 backbone, tb_mse objective, the config selected by the fold-0
  tuning; 5 seeds (20260821..20260825); per-target paired comparison of
  NDCG@10 on the fixed evaluation candidates.

Outputs under /mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/leakage_<ts>/:
per-arm run manifests, eval predictions, and the paired analysis JSON.
"""
import json
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

PROJ = "/home/cunyuliu/ToeholdDesignBench"
MNT = "/mnt/cunyuliu/ToeholdDesignBench"
REG = f"{MNT}/runs/v0.3.0/registry_v3"
PY = "/home/cunyuliu/miniconda3/envs/toeholdbench/bin/python"
SEED = 20260821
SEEDS = [20260821, 20260822, 20260823, 20260824, 20260825]
MIN_CAND = 10
EVAL_FRAC = 0.20


def main():
    ts = time.strftime("%Y%m%dT%H%M%S")
    out_dir = f"{MNT}/runs/v0.3.0/leakage_{ts}"
    os.makedirs(out_dir)

    # ---- frozen selection of eval targets and fixed eval candidates ----
    df = pd.read_parquet(f"{REG}/canonical_manifest.parquet")
    df = df[df["eligibility_status"] == "eligible_ranking"].copy()
    test = df[df["outer_fold"] == 0]
    train = df[df["outer_fold"] != 0]
    rng = np.random.default_rng(SEED)
    eval_sets = {}
    for tid, sub in test.groupby("target_id"):
        if len(sub) < MIN_CAND:
            continue
        idx = sub.index.values
        n_eval = max(2, int(round(len(idx) * EVAL_FRAC)))
        pick = rng.choice(idx, size=n_eval, replace=False)
        eval_sets[tid] = {"eval_idx": sorted(pick.tolist()),
                          "leak_idx": sorted((set(idx) - set(pick)))}
    n_eval_targets = len(eval_sets)
    print(f"candidate-rich test targets: {n_eval_targets}")
    leak_rows = sum(len(v["leak_idx"]) for v in eval_sets.values())
    print(f"leaky rows to add: {leak_rows}")

    # ---- clean-arm replacement rows ----
    # Contract: replacement rows are target-cluster-disjoint from every eval
    # target (training-fold targets are, by the cluster split), matched per
    # eval target by candidate count (nearest-size donor target) and ON-OFF
    # label stratification (quintile-matched sampling WITH replacement --
    # all labeled cluster-disjoint rows already sit in the base training set,
    # so the clean arm matches the leaky arm's row count via duplicated
    # upweighting rather than new information).
    train_counts = train.groupby("target_id").size()
    train_onoff = (train["label_on"] - train["label_off"])
    clean_records = []  # record ids, with replacement
    for tid, v in sorted(eval_sets.items()):
        need = len(v["leak_idx"])
        donor = (train_counts - need).abs().idxmin()
        donor_rows = train[train["target_id"] == donor]
        t_onoff = test.loc[v["leak_idx"], "label_on"] - \
            test.loc[v["leak_idx"], "label_off"]
        tq = pd.qcut(t_onoff, 5, labels=False, duplicates="drop")
        dq = pd.qcut(train_onoff.loc[donor_rows.index], 5, labels=False,
                     duplicates="drop")
        sel = []
        for b in sorted(set(tq.dropna().astype(int)) | {0, 1, 2, 3, 4}):
            want = int((tq == b).sum())
            if want <= 0:
                continue
            rows_b = donor_rows.index.values[dq.values == b]
            if len(rows_b) == 0:
                rows_b = donor_rows.index.values
            sel.extend(rng.choice(rows_b, size=want, replace=True))
        # top up from the full donor if quintile matching fell short
        while len(sel) < need:
            sel.extend(rng.choice(donor_rows.index.values,
                                  size=need - len(sel), replace=True))
        clean_records.extend(train.loc[sel[:need], "record_id"].tolist())
    print(f"clean replacement rows (with replacement): "
          f"{len(clean_records)} (target: {leak_rows})")
    leak_records_all = df.loc[
        [i for v in eval_sets.values() for i in v["leak_idx"]], "record_id"]\
        .tolist()
    assert len(leak_records_all) == leak_rows == len(clean_records)
    leak_all = leak_records_all
    clean_all = clean_records

    with open(f"{out_dir}/design.json", "w") as fh:
        json.dump({
            "test_fold": 0, "min_candidates": MIN_CAND,
            "eval_fraction": EVAL_FRAC, "seed": SEED,
            "n_eval_targets": n_eval_targets,
            "n_added_rows_per_arm": leak_rows,
            "clean_arm_semantics": (
                "replacement rows sampled with replacement from "
                "candidate-count-matched training-fold donor targets "
                "(label-quintile stratified); duplicated copies appended so "
                "both arms have base+leak_rows rows"),
            "eval_targets": {t: {"n_eval": len(v["eval_idx"]),
                                 "n_leak": len(v["leak_idx"])}
                             for t, v in eval_sets.items()},
        }, fh, indent=2)

    # ---- build the two training sets ----
    # rows as record ids; the trainer gets a modified manifest per arm
    base_manifest = f"{REG}/canonical_manifest.parquet"
    leak_records = set(leak_all)
    clean_records = set(clean_all)
    assert not (leak_records & clean_records)

    # training manifests: outer-train rows + arm rows. The leaky arm REMAPS
    # its extra rows to fold 1; the clean arm APPENDS duplicate copies of the
    # replacement rows (already present once in base) so that both manifests
    # have exactly base + leak_rows rows.
    with open(f"{REG}/split_manifest.json") as fh:
        sm = json.load(fh)
    inner_map = sm["inner_fold_of_target"]
    from collections import Counter
    for arm in ("leaky", "clean"):
        m = df.copy()
        m["inner_fold"] = m["target_id"].map(inner_map)
        if arm == "leaky":
            extra = m["record_id"].isin(leak_records)
            m.loc[extra, "outer_fold"] = 1
            m.loc[extra, "eligibility_status"] = "eligible_ranking"
            m.loc[extra, "inner_fold"] = 1
            n_extra = int(extra.sum())
        else:
            cnt = Counter(clean_all)
            appends = []
            for rid, c in cnt.items():
                row = df[df["record_id"] == rid]
                appends.append(pd.concat([row] * c, ignore_index=True))
            dup = pd.concat(appends, ignore_index=True)
            dup["outer_fold"] = 1
            dup["eligibility_status"] = "eligible_ranking"
            dup["inner_fold"] = 1
            m = pd.concat([m, dup], ignore_index=True)
            n_extra = int(len(dup))
        path = f"{out_dir}/manifest_{arm}.parquet"
        m.to_parquet(path, index=False)
        assert n_extra == leak_rows, (n_extra, leak_rows)
        print(f"{arm} manifest: {n_extra} extra rows -> {path}")

    # ---- fixed evaluation candidate track ----
    eval_rows = df.loc[sorted(i for v in eval_sets.values()
                              for i in v["eval_idx"])]
    eval_rows.to_parquet(f"{out_dir}/eval_track.parquet", index=False)
    print(f"eval track: {len(eval_rows)} rows, "
          f"{eval_rows['target_id'].nunique()} targets")

    # ---- train both arms x 5 seeds ----
    with open(f"{REG}/../tune_cnn60_f0/selection.json") as fh:
        sel = json.load(fh)["config"]
    print("selected config:", sel)
    env = dict(os.environ)
    env["CUDA_VISIBLE_DEVICES"] = "6"
    for arm in ("leaky", "clean"):
        for seed in SEEDS:
            rid = f"leakage_{arm}_s{seed}"
            manifest = f"{out_dir}/manifest_{arm}.parquet"
            # custom trainer call: the trainer reads MANIFEST constant, so we
            # inject via env override
            env2 = dict(env)
            env2["TBLR_MANIFEST_OVERRIDE"] = manifest
            env2["PYTHONPATH"] = f"{PROJ}/src"
            cmd = [PY, "-u", "src/v03_leakage_train.py", "--arm", arm,
                   "--seed", str(seed), "--manifest", manifest,
                   "--run-id", rid, "--out-dir", out_dir,
                   "--lr-mult", str(sel["lr_mult"]),
                   "--weight-decay", sel["weight_decay"],
                   "--aux-weight", str(sel["aux"])]
            log = f"{PROJ}/logs/v03_leakage_{arm}_s{seed}.log"
            with open(log, "w") as lf:
                r = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT,
                                   cwd=PROJ, env=env2)
            if r.returncode != 0:
                print(f"FAILED {rid}; see {log}")
                sys.exit(1)
            print(f"done {rid}")

    # ---- paired analysis on the fixed evaluation candidates ----
    sys.path.insert(0, f"{PROJ}/src")
    from toeholdbench.evaluator import expected_ndcg
    et = pd.read_parquet(f"{out_dir}/eval_track.parquet")
    per_target = {}
    for tid, sub in et.groupby("target_id"):
        per_target[tid] = sub
    res = {"per_target": [], "seeds": SEEDS}
    for tid, sub in per_target.items():
        onoff = (sub["label_on"] - sub["label_off"]).values
        for seed in SEEDS:
            lp = pd.read_parquet(f"{out_dir}/pred_leaky_s{seed}.parquet")
            cp = pd.read_parquet(f"{out_dir}/pred_clean_s{seed}.parquet")
            ls = lp[lp["target_id"] == tid].set_index("record_id")["score"]
            cs = cp[cp["target_id"] == tid].set_index("record_id")["score"]
            ls = ls.reindex(sub["record_id"]).values
            cs = cs.reindex(sub["record_id"]).values
            res["per_target"].append({
                "target_id": tid, "seed": seed,
                "ndcg_leaky": expected_ndcg(ls, onoff, 10),
                "ndcg_clean": expected_ndcg(cs, onoff, 10)})
    pt = pd.DataFrame(res["per_target"])
    diff = pt.groupby("target_id").apply(
        lambda g: g["ndcg_leaky"].mean() - g["ndcg_clean"].mean())
    summary = {
        "n_targets": int(diff.shape[0]),
        "mean_ndcg_leaky": float(pt["ndcg_leaky"].mean()),
        "mean_ndcg_clean": float(pt["ndcg_clean"].mean()),
        "mean_paired_diff": float(diff.mean()),
        "n_targets_leaky_better": int((diff > 0).sum()),
        "n_targets_clean_better": int((diff < 0).sum()),
    }
    with open(f"{out_dir}/paired_analysis.json", "w") as fh:
        json.dump({"summary": summary,
                   "per_target_diff": diff.describe().to_dict()}, fh, indent=2)
    pt.to_csv(f"{out_dir}/per_target_seed_metrics.csv", index=False)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
