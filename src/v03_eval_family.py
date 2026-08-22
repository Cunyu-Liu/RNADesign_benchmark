"""Evaluate a completed TBLR backbone family (all folds x ablations x seeds)
against the biophysical baselines through the single evaluator.

Usage: python v03_eval_family.py --backbone cnn60 [--extra preds.parquet ...]
"""
import argparse
import glob
import subprocess
import sys

import pandas as pd

REG = "/mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/registry_v3"
BASE = "/mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0"

PRIMARY = {"cnn60": "cnn60/full_tblr:cnn60/tb_mse",
           "sandstorm": "sandstorm/full_tblr:sandstorm/tb_mse",
           "rnaelectra": "rnaelectra/full_tblr:rnaelectra/tb_mse"}
SECONDARY = {"cnn60": ["cnn60/full_tblr:cnn60/rowwise_mse",
                       "cnn60/full_tblr:cnn60/tb_dual"],
             "sandstorm": ["sandstorm/full_tblr:sandstorm/rowwise_mse"],
             "rnaelectra": ["rnaelectra/full_tblr:rnaelectra/rowwise_mse"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backbone", required=True)
    ap.add_argument("--extra", action="append", default=[])
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    bb = args.backbone
    finals = sorted(glob.glob(f"{BASE}/final_{bb}_f*/predictions.parquet"))
    print(f"final prediction files: {len(finals)}")
    if not finals:
        sys.exit("no finals found")
    preds = pd.concat([pd.read_parquet(p) for p in finals],
                      ignore_index=True)
    extra_rows = []
    for e in args.extra:
        df = pd.read_parquet(e)
        extra_rows.append(df[df["method_id"].isin(
            ["lightgbm-biophys", "lightgbm-seq", "lightgbm-combined",
             "gc-baseline", "thermo-scorer"])])
    if extra_rows:
        preds = pd.concat([preds] + extra_rows, ignore_index=True)
    print("total predictions:", len(preds),
          "methods:", preds["method_id"].nunique())

    df = pd.read_parquet(f"{REG}/canonical_manifest.parquet")
    track = df[df["eligibility_status"] == "eligible_ranking"].copy()
    track_path = f"{BASE}/eval_{bb}_family_track.parquet"
    track.to_parquet(track_path)

    out = args.out or f"{BASE}/eval_{bb}_family"
    cmd = ["/home/cunyuliu/miniconda3/envs/toeholdbench/bin/python", "-m",
           "toeholdbench", "evaluate",
           "--track", track_path, "--predictions",
           f"{BASE}/eval_{bb}_family_preds.parquet",
           "--output", out,
           "--primary-contrast", PRIMARY[bb]]
    for s in SECONDARY[bb]:
        cmd += ["--secondary-contrast", s]
    preds.to_parquet(f"{BASE}/eval_{bb}_family_preds.parquet", index=False)
    rc = subprocess.run(cmd, cwd="/home/cunyuliu/ToeholdDesignBench",
                        env={"PYTHONPATH": "/home/cunyuliu/ToeholdDesignBench/src",
                             "PATH": "/usr/bin:/bin"},
                        capture_output=True, text=True)
    print(rc.stdout[-2000:])
    if rc.returncode != 0:
        print("STDERR:", rc.stderr[-2000:])
        sys.exit(1)

    s = pd.read_csv(f"{out}/method_summary.csv")
    cols = [c for c in ["method_id", "n_targets", "ndcg@10",
                        "random_ndcg@10", "spearman", "regret@1",
                        "success@1_0.5_0.5"] if c in s.columns]
    print(s[cols].sort_values("ndcg@10", ascending=False).to_string(index=False))
    print()
    c = pd.read_csv(f"{out}/contrasts.csv")
    print(c.to_string(index=False))


if __name__ == "__main__":
    main()
