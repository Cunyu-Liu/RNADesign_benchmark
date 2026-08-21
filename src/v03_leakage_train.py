"""Leakage-arm trainer: trains cnn60/tb_mse on a custom arm manifest and
scores the fixed evaluation-candidate track (v03_leakage.py driver)."""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd
import torch

PROJ = "/home/cunyuliu/ToeholdDesignBench"
MNT = "/mnt/cunyuliu/ToeholdDesignBench"
sys.path.insert(0, f"{PROJ}/src")
import v03_tblr as vr  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--lr-mult", type=float, default=1.0)
    ap.add_argument("--weight-decay", default="default")
    ap.add_argument("--aux-weight", type=float, default=0.25)
    args = ap.parse_args()

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("FATAL: CUDA unavailable (contract: no silent CPU fallback)")
        sys.exit(3)

    # load the ARM manifest (outer-train rows + arm-specific extra rows;
    # inner_fold column is embedded by the driver)
    df = pd.read_parquet(args.manifest)
    df = df[df["eligibility_status"] == "eligible_ranking"].copy()
    data = vr.TargetData(df, "cnn60")

    all_targets = sorted(data.cands.keys())
    train_pool = [t for t in all_targets if data.fold[t] != 0]
    # early-stop validation: inner fold 0 (same convention as final runs)
    val_targets = [t for t in train_pool if data.inner.get(t) == 0]
    train_targets = [t for t in train_pool if data.inner.get(t) != 0]

    cfg = {"lr": vr.LR["cnn60"] * args.lr_mult,
           "weight_decay": (vr.WD_DEFAULT["cnn60"]
                            if args.weight_decay == "default"
                            else float(args.weight_decay)),
           "aux_weight": args.aux_weight, "dropout": 0.0}
    model = vr.build_model("cnn60", 0.0)
    info = vr.train_one(model, data, train_targets, val_targets, cfg, device,
                        args.seed, "tb_mse", "cnn60")
    info.update({"arm": args.arm, "seed": args.seed, "config": cfg})

    # score the FIXED evaluation-candidate track only
    et = pd.read_parquet(f"{args.out_dir}/eval_track.parquet")
    eval_targets = sorted(et["target_id"].unique())
    scores = vr.score_targets(model, data, eval_targets, device, "cnn60")
    rows = []
    for tid in eval_targets:
        sub = et[et["target_id"] == tid].sort_values("record_id")
        sc = scores[tid]
        rec_pos = {r: i for i, r in enumerate(data.cands[tid]["records"])}
        for _, r in sub.iterrows():
            i = rec_pos[r["record_id"]]
            rows.append({
                "run_id": args.run_id, "track_id": "leakage_eval",
                "fold": 0, "target_id": tid,
                "target_cluster_id": r["target_cluster_id"],
                "record_id": r["record_id"], "method_id": f"leakage/{args.arm}",
                "seed": args.seed, "score": float(sc["score"][i])})
    out_pred = f"{args.out_dir}/pred_{args.arm}_s{args.seed}.parquet"
    pd.DataFrame(rows).to_parquet(out_pred, index=False)
    info["n_eval_predictions"] = len(rows)
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
