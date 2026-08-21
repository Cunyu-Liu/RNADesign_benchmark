"""Summarize v0.2 multi-seed scores by canonical target group.

Model fitting happens once in ``p3_baselines.py``.  This script consumes those
exact scores so the robustness report cannot silently use a different network.
Confidence intervals resample targets; seed sensitivity is reported separately.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from metrics.metrics import (  # noqa: E402
    mean_with_ci, ndcg_at_k, normalized_regret, pareto_front_coverage, success_at_k,
    expected_random_ranking_metrics,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TD_ROOT = os.environ.get("TD_BENCH_ROOT", os.path.join(PROJECT_ROOT, "data"))
TD_PROC = os.environ.get("TD_BENCH_PROCESSED", os.path.join(TD_ROOT, "processed"))
SCORES = os.path.join(TD_PROC, "p3_test_scores_v02.csv")
OUT = os.path.join(TD_PROC, "p3_robustness_multiseed_v02.json")
SEEDS = (0, 1, 2, 3, 4)
METHODS = (
    "B0_random", "B0_gc", "B1_thermo", "B2_mlp", "B2_cnn", "B3_deep",
    "B4_struct", "B5_structrank",
)
LEARNED = {"B2_mlp", "B2_cnn", "B3_deep", "B4_struct", "B5_structrank"}


def target_metrics(frame: pd.DataFrame, score_col: str) -> pd.DataFrame:
    rows = []
    for target_id, group in frame.groupby("target_id", sort=True):
        group = group.sort_values([score_col, "record_id"], ascending=[False, True])
        ranked = group["record_id"].tolist()
        success = dict(zip(group["record_id"], group["success"].astype(bool)))
        relevance = dict(zip(group["record_id"], group["ON_OFF"]))
        on = dict(zip(group["record_id"], group["ON"]))
        off = dict(zip(group["record_id"], group["OFF"]))
        rows.append({
            "target_id": target_id,
            "success_at_1": success_at_k(ranked, success, 1),
            "success_at_3": success_at_k(ranked, success, 3),
            "success_at_5": success_at_k(ranked, success, 5),
            "ndcg_at_10": ndcg_at_k(ranked, relevance, 10),
            "normalized_regret_at_10": normalized_regret(ranked, relevance, 10),
            "pareto_front_coverage_at_10": pareto_front_coverage(ranked, on, off, 10),
        })
    return pd.DataFrame(rows)


def expected_random_target_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for target_id, group in frame.groupby("target_id", sort=True):
        ids = group["record_id"].tolist()
        metrics = expected_random_ranking_metrics(
            ids,
            dict(zip(ids, group["success"].astype(bool))),
            dict(zip(ids, group["ON_OFF"])),
            dict(zip(ids, group["ON"])),
            dict(zip(ids, group["OFF"])),
        )
        rows.append({
            "target_id": target_id,
            **{metric: metrics[metric] for metric in (
                "success_at_1", "success_at_3", "success_at_5", "ndcg_at_10",
                "normalized_regret_at_10", "pareto_front_coverage_at_10",
            )},
        })
    return pd.DataFrame(rows)


def summarize(metrics: pd.DataFrame) -> dict:
    result = {}
    for column in metrics.columns.drop("target_id"):
        values = metrics[column].astype(float).tolist()
        mean, lo, hi = mean_with_ci(values, rng=np.random.default_rng(0))
        result[column] = {
            "mean": round(mean, 5),
            "ci95": [round(lo, 5), round(hi, 5)],
            "n_targets": len(values),
        }
    return result


def main():
    scores = pd.read_csv(SCORES)
    scores["group"] = np.where(
        scores["target_id"].astype(str).str.startswith("human_"), "TF", "virus"
    )
    result = {"version": "0.2", "by_group": {}, "seed_sensitivity": {}}
    for group_name in ("all", "virus", "TF"):
        group = scores if group_name == "all" else scores[scores["group"] == group_name]
        result["by_group"][group_name] = {
            method: summarize(
                expected_random_target_metrics(group)
                if method == "B0_random" else target_metrics(group, method)
            )
            for method in METHODS
        }

    for method in sorted(LEARNED):
        per_seed = {}
        for seed in SEEDS:
            column = f"{method}_seed_{seed}"
            if column not in scores:
                raise ValueError(f"missing required multi-seed score column: {column}")
            metrics = target_metrics(scores, column)
            per_seed[str(seed)] = {
                metric: round(float(metrics[metric].mean()), 5)
                for metric in metrics.columns.drop("target_id")
            }
        result["seed_sensitivity"][method] = per_seed

    with open(OUT, "w") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
    print(json.dumps(result, indent=2))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
