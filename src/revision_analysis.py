"""v0.2 canonical-track analyses after the correctness repair.

This script consumes the score file produced by ``p3_baselines.py`` and emits:
E1 objective alignment across every method, E2 split diagnostics with corrected
MLP/CNN encodings, E4 local-feature concatenation, E5 oracle metric diagnostics,
and E6 evaluator disagreement.  Test labels are used only for evaluation/oracle
diagnostics, never as a submitted method.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
import torch
from scipy import stats

sys.path.insert(0, os.path.dirname(__file__))
from metrics.metrics import (  # noqa: E402
    mean_with_ci,
    ndcg_at_k,
    normalized_regret,
    paired_mean_difference_ci,
    pareto_front_coverage,
    pareto_front_ids,
    success_at_k,
    expected_random_ranking_metrics,
)
from model_utils import onehot_channels, onehot_flat, seed_everything, torch_device  # noqa: E402


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TD_ROOT = os.environ.get("TD_BENCH_ROOT", os.path.join(PROJECT_ROOT, "data"))
TD_PROC = os.environ.get("TD_BENCH_PROCESSED", os.path.join(TD_ROOT, "processed"))
CANON = os.path.join(TD_PROC, "canonical_records.parquet")
SPLIT = os.path.join(TD_PROC, "split_manifests.csv")
SCORES = os.path.join(TD_PROC, "p3_test_scores_v02.csv")
OUT = os.path.join(TD_PROC, "revision_analysis_v02.json")
TARGET_OUT = os.path.join(TD_PROC, "revision_target_metrics_v02.csv")
SEED = 0
METHODS = [
    "B0_random", "B0_gc", "B1_thermo", "B2_mlp", "B2_cnn", "B3_deep",
    "B4_struct", "B5_structrank",
]
DIAGNOSTIC_SEEDS = (0, 1, 2)


def metric_rows(frame: pd.DataFrame, score_col: str) -> pd.DataFrame:
    rows = []
    for target_id, group in frame.groupby("target_id", sort=True):
        ranked_group = group.sort_values([score_col, "record_id"], ascending=[False, True])
        ranked = ranked_group["record_id"].tolist()
        success = dict(zip(group["record_id"], group["success"].astype(bool)))
        relevance = dict(zip(group["record_id"], group["ON_OFF"]))
        on = dict(zip(group["record_id"], group["ON"]))
        off = dict(zip(group["record_id"], group["OFF"]))
        rows.append({
            "target_id": target_id,
            "method": score_col,
            "success_at_1": success_at_k(ranked, success, 1),
            "success_at_3": success_at_k(ranked, success, 3),
            "success_at_5": success_at_k(ranked, success, 5),
            "ndcg_at_10": ndcg_at_k(ranked, relevance, 10),
            "normalized_regret_at_10": normalized_regret(ranked, relevance, 10),
            "pareto_front_coverage_at_10": pareto_front_coverage(ranked, on, off, 10),
        })
    return pd.DataFrame(rows)


def expected_random_metric_rows(frame: pd.DataFrame) -> pd.DataFrame:
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
        rows.append({"target_id": target_id, "method": "B0_random", **{
            metric: metrics[metric] for metric in (
                "success_at_1", "success_at_3", "success_at_5", "ndcg_at_10",
                "normalized_regret_at_10", "pareto_front_coverage_at_10",
            )
        }})
    return pd.DataFrame(rows)


def summary(values) -> dict:
    mean, lo, hi = mean_with_ci(list(values), rng=np.random.default_rng(SEED))
    return {"mean": round(mean, 5), "ci95": [round(lo, 5), round(hi, 5)], "n_targets": len(values)}


def pairwise(a, b) -> dict:
    delta, lo, hi, p = paired_mean_difference_ci(
        list(a), list(b), rng=np.random.default_rng(SEED)
    )
    return {
        "mean_difference": round(delta, 5),
        "ci95": [round(lo, 5), round(hi, 5)],
        "two_sided_bootstrap_p": round(p, 5),
        "n_targets": len(a),
    }


def make_model(name: str):
    if name == "mlp":
        return torch.nn.Sequential(
            torch.nn.Linear(120, 64), torch.nn.ReLU(),
            torch.nn.Linear(64, 32), torch.nn.ReLU(), torch.nn.Linear(32, 1),
        )
    if name == "cnn":
        return torch.nn.Sequential(
            torch.nn.Conv1d(4, 64, 5), torch.nn.ReLU(),
            torch.nn.AdaptiveAvgPool1d(1), torch.nn.Flatten(),
            torch.nn.Linear(64, 32), torch.nn.ReLU(), torch.nn.Linear(32, 1),
        )
    raise ValueError(name)


def train_predict(name: str, train: pd.DataFrame, test: pd.DataFrame, seed: int) -> np.ndarray:
    seed_everything(seed)
    device = torch_device()
    model = make_model(name).to(device)
    if name == "mlp":
        x_train = onehot_flat(train["trigger"])
        x_test = onehot_flat(test["trigger"])
    else:
        x_train = onehot_channels(train["trigger"])
        x_test = onehot_channels(test["trigger"])
    x_train_t = torch.tensor(x_train, dtype=torch.float32, device=device)
    y_train_t = torch.tensor(train["ON_OFF"].values, dtype=torch.float32, device=device).unsqueeze(1)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    model.train()
    for _ in range(15):
        optimizer.zero_grad()
        loss = torch.nn.functional.mse_loss(model(x_train_t), y_train_t)
        loss.backward()
        optimizer.step()
    model.eval()
    with torch.no_grad():
        return model(torch.tensor(x_test, dtype=torch.float32, device=device)).squeeze(1).cpu().numpy()


def mean_target_spearman(frame: pd.DataFrame, score_col: str) -> float:
    values = []
    for _, group in frame.groupby("target_id"):
        if len(group) < 3 or group[score_col].nunique() < 2 or group["ON_OFF"].nunique() < 2:
            continue
        rho = stats.spearmanr(group[score_col], group["ON_OFF"]).correlation
        if np.isfinite(rho):
            values.append(float(rho))
    return float(np.mean(values)) if values else float("nan")


def split_diagnostic(canonical: pd.DataFrame) -> dict:
    source_train = canonical[canonical["split"] == "train"].reset_index(drop=True)
    source_test = canonical[canonical["split"] == "test"].reset_index(drop=True)
    permutation = np.random.default_rng(SEED).permutation(len(canonical))
    # Match the source-disjoint train and test row counts so a change cannot be
    # attributed simply to a larger random-split training set.
    n_train = len(source_train)
    n_test = len(source_test)
    row_train = canonical.iloc[permutation[:n_train]].reset_index(drop=True)
    row_test = canonical.iloc[permutation[n_train:n_train + n_test]].reset_index(drop=True)
    result = {
        "source_disjoint_target_overlap_fraction": float(
            source_test["target_id"].isin(set(source_train["target_id"])).mean()
        ),
        "row_random_target_overlap_fraction": float(
            row_test["target_id"].isin(set(row_train["target_id"])).mean()
        ),
        "models": {},
    }
    for model_name in ("mlp", "cnn"):
        per_seed = []
        for seed in DIAGNOSTIC_SEEDS:
            source_scores = train_predict(model_name, source_train, source_test, seed)
            row_scores = train_predict(model_name, row_train, row_test, seed)
            source_eval = source_test.copy()
            row_eval = row_test.copy()
            source_eval["score"] = source_scores
            row_eval["score"] = row_scores
            source_rho = float(stats.spearmanr(source_scores, source_test["ON_OFF"]).correlation)
            row_rho = float(stats.spearmanr(row_scores, row_test["ON_OFF"]).correlation)
            per_seed.append({
                "seed": seed,
                "source_disjoint_pooled_spearman": round(source_rho, 5),
                "row_random_pooled_spearman": round(row_rho, 5),
                "row_minus_source_spearman": round(row_rho - source_rho, 5),
                "source_disjoint_mean_target_spearman": round(
                    mean_target_spearman(source_eval, "score"), 5
                ),
                "row_random_mean_target_spearman": round(
                    mean_target_spearman(row_eval, "score"), 5
                ),
            })
        numeric_keys = [key for key in per_seed[0] if key != "seed"]
        result["models"][model_name] = {
            "per_seed": per_seed,
            "mean_across_seeds": {
                key: round(float(np.mean([row[key] for row in per_seed])), 5)
                for key in numeric_keys
            },
        }
    return result


def main():
    scores = pd.read_csv(SCORES)
    target_tables = [expected_random_metric_rows(scores)] + [
        metric_rows(scores, method) for method in METHODS[1:]
    ]
    target_metrics = pd.concat(target_tables, ignore_index=True)
    target_metrics.to_csv(TARGET_OUT, index=False)

    e1 = {"methods": {}, "paired_vs_random": {}}
    prediction_rho = []
    design_s1 = []
    design_ndcg = []
    for method in METHODS:
        method_metrics = target_metrics[target_metrics["method"] == method].sort_values("target_id")
        rho = 0.0 if method == "B0_random" else float(
            stats.spearmanr(scores[method], scores["ON_OFF"]).correlation
        )
        e1["methods"][method] = {
            "pooled_prediction_spearman": round(rho, 5),
            "success_at_1": summary(method_metrics["success_at_1"]),
            "success_at_3": summary(method_metrics["success_at_3"]),
            "success_at_5": summary(method_metrics["success_at_5"]),
            "ndcg_at_10": summary(method_metrics["ndcg_at_10"]),
            "normalized_regret_at_10": summary(method_metrics["normalized_regret_at_10"]),
            "pareto_front_coverage_at_10": summary(
                method_metrics["pareto_front_coverage_at_10"]
            ),
        }
        prediction_rho.append(rho)
        design_s1.append(method_metrics["success_at_1"].mean())
        design_ndcg.append(method_metrics["ndcg_at_10"].mean())

    random_metrics = target_metrics[target_metrics["method"] == "B0_random"].sort_values("target_id")
    for method in METHODS[1:]:
        current = target_metrics[target_metrics["method"] == method].sort_values("target_id")
        e1["paired_vs_random"][method] = {
            "success_at_1": pairwise(current["success_at_1"], random_metrics["success_at_1"]),
            "success_at_3": pairwise(current["success_at_3"], random_metrics["success_at_3"]),
            "ndcg_at_10": pairwise(current["ndcg_at_10"], random_metrics["ndcg_at_10"]),
            "pareto_front_coverage_at_10": pairwise(
                current["pareto_front_coverage_at_10"],
                random_metrics["pareto_front_coverage_at_10"],
            ),
        }
    e1["method_rank_spearman_prediction_vs_success_at_1"] = round(
        float(stats.spearmanr(prediction_rho, design_s1).correlation), 5
    )
    e1["method_rank_spearman_prediction_vs_ndcg_at_10"] = round(
        float(stats.spearmanr(prediction_rho, design_ndcg).correlation), 5
    )

    canonical = pd.read_parquet(CANON)
    canonical = canonical[
        (canonical["admission_status"] == "admitted_paired") & canonical["ON_OFF"].notna()
    ].copy()
    canonical = canonical.merge(pd.read_csv(SPLIT), on="target_id", how="left")
    canonical["success"] = ((canonical["ON"] >= 0.5) & (canonical["OFF"] <= 0.5)).astype(int)
    e2 = split_diagnostic(canonical)

    # E4 is a local sequence/biophysical feature concatenation comparison, not
    # a full-target-context ablation.
    e4 = {"label": "local_biophysical_feature_concatenation", "comparisons": {}}
    base = target_metrics[target_metrics["method"] == "B2_mlp"].sort_values("target_id")
    for method in ("B4_struct", "B5_structrank"):
        other = target_metrics[target_metrics["method"] == method].sort_values("target_id")
        e4["comparisons"][f"{method}_minus_B2_mlp"] = {
            "success_at_1": pairwise(other["success_at_1"], base["success_at_1"]),
            "ndcg_at_10": pairwise(other["ndcg_at_10"], base["ndcg_at_10"]),
        }

    # E5 is explicitly an oracle/metric diagnostic.  Every target remains in the
    # denominator, including targets with no threshold-qualified candidate.
    oracle_rows = []
    for target_id, group in scores.groupby("target_id", sort=True):
        success = dict(zip(group["record_id"], group["success"].astype(bool)))
        on = dict(zip(group["record_id"], group["ON"]))
        off = dict(zip(group["record_id"], group["OFF"]))
        by_difference = group.sort_values(["ON_OFF", "record_id"], ascending=[False, True])["record_id"].tolist()
        by_on = group.sort_values(["ON", "record_id"], ascending=[False, True])["record_id"].tolist()
        by_off = group.sort_values(["OFF", "record_id"], ascending=[True, True])["record_id"].tolist()
        pareto = pareto_front_ids(group["record_id"].tolist(), on, off)
        oracle_rows.append({
            "target_id": target_id,
            "has_feasible_candidate": int(group["success"].any()),
            "on_minus_off_oracle": success_at_k(by_difference, success, 1),
            "on_only_oracle": success_at_k(by_on, success, 1),
            "off_only_oracle": success_at_k(by_off, success, 1),
            "pareto_lexicographic_oracle": success_at_k(pareto, success, 1),
            "pareto_front_size": len(pareto),
        })
    oracle = pd.DataFrame(oracle_rows)
    e5 = {
        "label": "oracle_metric_diagnostic_not_a_submitted_method",
        "n_targets": len(oracle),
        "n_targets_with_feasible_candidate": int(oracle["has_feasible_candidate"].sum()),
        "unconditional_success_at_1": {
            column: round(float(oracle[column].mean()), 5)
            for column in (
                "on_minus_off_oracle", "on_only_oracle", "off_only_oracle",
                "pareto_lexicographic_oracle",
            )
        },
        "mean_pareto_front_size": round(float(oracle["pareto_front_size"].mean()), 5),
    }

    mlp = scores.sort_values(["target_id", "B2_mlp"], ascending=[True, False]).groupby("target_id").first()
    thermo = scores.sort_values(["target_id", "B1_thermo"], ascending=[True, False]).groupby("target_id").first()
    agreement = (mlp["record_id"] == thermo["record_id"]).mean()
    e6 = {
        "label": "evaluator_disagreement_not_proxy_overfitting",
        "top1_agreement_B2_mlp_vs_B1_thermo": round(float(agreement), 5),
        "n_targets": int(len(mlp)),
    }

    result = {"version": "0.2",
              "random_baseline": "exact per-target expectation over all candidate permutations",
              "E1_objective_alignment": e1, "E2_split_diagnostic": e2,
              "E4_local_feature_concat": e4, "E5_oracle_metric_diagnostic": e5,
              "E6_evaluator_disagreement": e6}
    with open(OUT, "w") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
    print(json.dumps(result, indent=2))
    print("wrote", OUT)
    print("wrote", TARGET_OUT)


if __name__ == "__main__":
    main()
