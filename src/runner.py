"""ToeholdDesignBench — unified evaluation runner (P5).

Usage:
  python runner.py --method B1_thermo            # evaluate a built-in baseline
  python runner.py --method my_method --scores /path/to/scores.csv   # external submission

A "method" produces per-record candidate scores; the runner loads the canonical
records + source-disjoint split, computes per-target top-K design utility with
target-level bootstrap CI, and emits a leaderboard entry + per-target predictions.
"""
import argparse
import json
import sys
import os
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from metrics.metrics import (  # noqa: E402
    success_at_k, ndcg_at_k, normalized_regret, pareto_front_coverage, mean_with_ci,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TD_ROOT = os.environ.get("TD_BENCH_ROOT", os.path.join(PROJECT_ROOT, "data"))
TD_PROC = os.environ.get("TD_BENCH_PROCESSED", os.path.join(TD_ROOT, "processed"))
CANON = os.path.join(TD_PROC, "canonical_records.parquet")
SPLIT = os.path.join(TD_PROC, "split_manifests.csv")
SEED = 0


def load():
    df = pd.read_parquet(CANON)
    df = df[df["admission_status"] == "admitted_paired"].copy()
    df = df[df["ON_OFF"].notna()].reset_index(drop=True)
    sp = pd.read_csv(SPLIT)
    return df.merge(sp, on="target_id", how="left")


def builtin_scores(method, tr, te):
    rng = np.random.default_rng(SEED)
    if method == "B0_random":
        return rng.random(len(te))
    if method == "B0_gc":
        return te["gc_trigger"].fillna(0).values
    if method == "B1_thermo":
        return te["salis_onoff"].replace(0.0, np.nan).fillna(te["mfe_switch_off"]).fillna(0).values
    raise ValueError(f"unknown builtin method {method} (use external --scores for deep models)")


def evaluate(df, test_scores, K_list=(1, 3, 5), out_prefix="result"):
    te = df[df["split"] == "test"].copy()
    scores = np.asarray(test_scores, dtype=float)
    if len(scores) != len(te):
        raise ValueError(f"expected {len(te)} test scores, received {len(scores)}")
    if not np.isfinite(scores).all():
        raise ValueError("test scores must all be finite")
    te["score"] = scores
    # success: absolute pre-registered (ON>=0.5 & OFF<=0.5)
    te["success"] = ((te["ON"] >= 0.5) & (te["OFF"] <= 0.5)).astype(int)
    per_target = []
    agg = {}
    for K in K_list:
        vals = []
        for tid, g in te.groupby("target_id", sort=True):
            g = g.sort_values(["score", "record_id"], ascending=[False, True])
            ranked = g["record_id"].tolist()
            succ = dict(zip(g["record_id"], g["success"].astype(bool)))
            rel = dict(zip(g["record_id"], g["ON_OFF"]))
            vals.append(success_at_k(ranked, succ, K))
            if K == 1:
                on = dict(zip(g["record_id"], g["ON"]))
                off = dict(zip(g["record_id"], g["OFF"]))
                per_target.append({"target_id": tid, "success_at_1": success_at_k(ranked, succ, 1),
                                   "ndcg_at_10": ndcg_at_k(ranked, rel, 10),
                                   "normalized_regret_at_10": normalized_regret(ranked, rel, 10),
                                   "pareto_front_coverage_at_10": pareto_front_coverage(
                                       ranked, on, off, 10
                                   ),
                                   "has_feasible_candidate": int(g["success"].any()),
                                   "top1": ranked[0]})
        m, lo, hi = mean_with_ci(vals, rng=np.random.default_rng(SEED))
        agg[f"success_at_{K}"] = {"mean": round(m, 4), "ci": [round(lo, 4), round(hi, 4)]}
    per_target_df = pd.DataFrame(per_target)
    for column in ("ndcg_at_10", "normalized_regret_at_10", "pareto_front_coverage_at_10"):
        m, lo, hi = mean_with_ci(per_target_df[column].tolist(), rng=np.random.default_rng(SEED))
        agg[column] = {"mean": round(m, 4), "ci": [round(lo, 4), round(hi, 4)]}
    agg["target_accounting"] = {
        "n_targets": int(len(per_target_df)),
        "n_targets_with_feasible_candidate": int(per_target_df["has_feasible_candidate"].sum()),
        "n_targets_without_feasible_candidate": int((1 - per_target_df["has_feasible_candidate"]).sum()),
    }
    te[["target_id", "record_id", "score"]].to_csv(f"{out_prefix}_scores.csv", index=False)
    per_target_df.to_csv(f"{out_prefix}_per_target.csv", index=False)
    return agg


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", default="B0_random")
    ap.add_argument("--scores", default=None, help="CSV with columns record_id,score (external submission)")
    ap.add_argument("--out", default=os.path.join(TD_PROC, "runner_result"))
    a = ap.parse_args()

    df = load()
    tr = df[df["split"] == "train"].reset_index(drop=True)
    te = df[df["split"] == "test"].reset_index(drop=True)

    if a.scores:
        ext = pd.read_csv(a.scores)
        if not {"record_id", "score"}.issubset(ext.columns):
            raise ValueError("external score file must contain record_id and score columns")
        if ext["record_id"].duplicated().any():
            raise ValueError("external score file contains duplicate record_id values")
        te = te.merge(ext, on="record_id", how="left")
        if te["score"].isna().any():
            raise ValueError("external score file is missing test record_id values")
        scores = te["score"].values
    else:
        scores = builtin_scores(a.method, tr, te)

    agg = evaluate(df, scores, out_prefix=a.out)
    entry = {"method": a.method, "seed": SEED, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
             "metrics": agg}
    json.dump(entry, open(f"{a.out}_leaderboard_entry.json", "w"), indent=2)
    print(json.dumps(entry, indent=2))
