"""Rebuild BEACON PRS as target-level, source-disjoint ranking tracks.

The published BEACON split is row-level and contains the same virus targets in
train/validation/test.  This script creates two non-overlapping evaluation tracks:

1. stratified source-disjoint TF+virus split;
2. domain OOD, training on TF targets and testing on all 23 virus targets.

BEACON's reported ``ON_OFF`` column is treated as its own normalized label.  It is
not equated with the signed canonical ``ON - OFF`` value and no absolute success
threshold is transferred between tracks.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(__file__))
from metrics.metrics import (  # noqa: E402
    mean_with_ci, ndcg_at_k, normalized_regret, paired_mean_difference_ci,
    expected_random_ranking_metrics,
)
from model_utils import onehot_channels, onehot_flat, seed_everything, torch_device  # noqa: E402


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TD_ROOT = os.environ.get("TD_BENCH_ROOT", os.path.join(PROJECT_ROOT, "data"))
MAPPING = os.path.join(TD_ROOT, "external", "beacon_prs", "beacon_authoritative_mapping.csv")
PROCESSED = os.environ.get("TD_BENCH_PROCESSED", os.path.join(TD_ROOT, "processed"))
MANIFEST = os.path.join(PROCESSED, "beacon_source_split_v02.csv")
TARGET_METRICS = os.path.join(PROCESSED, "beacon_target_metrics_v02.csv")
OUT = os.path.join(PROCESSED, "beacon_target_benchmark_v02.json")
SEEDS = (0, 1, 2)


def build_manifest(data: pd.DataFrame) -> pd.DataFrame:
    targets = data[["source_sequence", "category"]].drop_duplicates().sort_values(
        ["category", "source_sequence"]
    ).reset_index(drop=True)
    pieces = []
    rng = np.random.default_rng(0)
    for category, group in targets.groupby("category", sort=True):
        order = rng.permutation(len(group))
        group = group.iloc[order].copy().reset_index(drop=True)
        n_test = max(1, int(round(0.15 * len(group))))
        n_val = max(1, int(round(0.15 * len(group))))
        n_train = len(group) - n_val - n_test
        group["split"] = ["train"] * n_train + ["validation"] * n_val + ["test"] * n_test
        pieces.append(group)
    manifest = pd.concat(pieces, ignore_index=True)
    manifest["target_id"] = [f"beacon_target_{idx:04d}" for idx in range(len(manifest))]
    return manifest[["target_id", "source_sequence", "category", "split"]]


def attach_source_manifest(data: pd.DataFrame, manifest: pd.DataFrame) -> pd.DataFrame:
    """Attach the target-level split without confusing it with BEACON's row split."""
    data = data.copy()
    if "split" in data.columns:
        data = data.rename(columns={"split": "published_row_split"})
    merged = data.merge(
        manifest,
        on=["source_sequence", "category"],
        how="left",
        validate="many_to_one",
    )
    if merged[["target_id", "split"]].isna().any().any():
        raise ValueError("BEACON source manifest did not cover every retained row")
    return merged


def published_split_audit(data: pd.DataFrame) -> dict:
    """Quantify target leakage in BEACON's published row/QC split."""
    result = {}
    for category in ("TF", "virus"):
        group = data[data["category"] == category]
        train_targets = set(group[group["published_row_split"] == "train"]["source_sequence"])
        test_targets = set(group[group["published_row_split"] == "test"]["source_sequence"])
        overlap = train_targets & test_targets
        result[category] = {
            "n_train_targets": len(train_targets),
            "n_test_targets": len(test_targets),
            "n_overlapping_targets": len(overlap),
            "test_target_overlap_fraction": (
                len(overlap) / len(test_targets) if test_targets else None
            ),
        }
    return result


def make_model(name: str, length: int):
    import torch

    if name.startswith("mlp"):
        return torch.nn.Sequential(
            torch.nn.Linear(length * 4, 128), torch.nn.ReLU(),
            torch.nn.Linear(128, 64), torch.nn.ReLU(), torch.nn.Linear(64, 1),
        )
    if name == "cnn30":
        return torch.nn.Sequential(
            torch.nn.Conv1d(4, 64, 7), torch.nn.ReLU(),
            torch.nn.Conv1d(64, 64, 5), torch.nn.ReLU(),
            torch.nn.AdaptiveAvgPool1d(1), torch.nn.Flatten(),
            torch.nn.Linear(64, 32), torch.nn.ReLU(), torch.nn.Linear(32, 1),
        )
    raise ValueError(name)


def encode(name: str, sequences, length: int):
    if name == "cnn30":
        return onehot_channels(sequences, length=length)
    return onehot_flat(sequences, length=length)


def fit_score(name: str, train: pd.DataFrame, test: pd.DataFrame, length: int, seed: int) -> np.ndarray:
    import torch

    seed_everything(seed)
    device = torch_device()
    model = make_model(name, length).to(device)
    x_train = torch.tensor(encode(name, train["sequence"], length), dtype=torch.float32, device=device)
    y_train = torch.tensor(train["ON_OFF"].values, dtype=torch.float32, device=device).unsqueeze(1)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    model.train()
    for _ in range(12):
        optimizer.zero_grad()
        loss = torch.nn.functional.mse_loss(model(x_train), y_train)
        loss.backward()
        optimizer.step()
    model.eval()
    x_test = torch.tensor(encode(name, test["sequence"], length), dtype=torch.float32, device=device)
    with torch.no_grad():
        return model(x_test).squeeze(1).cpu().numpy()


def target_metrics(frame: pd.DataFrame, score_col: str, track: str) -> pd.DataFrame:
    rows = []
    for target_id, group in frame.groupby("target_id", sort=True):
        ranked_group = group.sort_values([score_col, "sequence_id"], ascending=[False, True])
        ranked = ranked_group["sequence_id"].tolist()
        relevance = dict(zip(group["sequence_id"], group["ON_OFF"]))
        rho = stats.spearmanr(group[score_col], group["ON_OFF"]).correlation
        rows.append({
            "track": track,
            "target_id": target_id,
            "category": group["category"].iloc[0],
            "method": score_col,
            "n_candidates": len(group),
            "target_spearman": float(rho) if np.isfinite(rho) else np.nan,
            "ndcg_at_10": ndcg_at_k(ranked, relevance, 10),
            "normalized_regret_at_10": normalized_regret(ranked, relevance, 10),
            "normalized_regret_at_1": normalized_regret(ranked, relevance, 1),
        })
    return pd.DataFrame(rows)


def expected_random_target_metrics(frame: pd.DataFrame, track: str) -> pd.DataFrame:
    rows = []
    for target_id, group in frame.groupby("target_id", sort=True):
        ids = group["sequence_id"].tolist()
        metrics = expected_random_ranking_metrics(
            ids,
            {cid: False for cid in ids},
            dict(zip(ids, group["ON_OFF"])),
            dict(zip(ids, group["ON"])),
            dict(zip(ids, group["OFF"])),
        )
        rows.append({
            "track": track,
            "target_id": target_id,
            "category": group["category"].iloc[0],
            "method": "random",
            "n_candidates": len(group),
            "target_spearman": 0.0 if group["ON_OFF"].nunique() > 1 else np.nan,
            "ndcg_at_10": metrics["ndcg_at_10"],
            "normalized_regret_at_10": metrics["normalized_regret_at_10"],
            "normalized_regret_at_1": metrics["normalized_regret_at_1"],
        })
    return pd.DataFrame(rows)


def summarize(values) -> dict:
    clean = pd.Series(values).dropna().astype(float).tolist()
    if not clean:
        return {"mean": None, "ci95": [None, None], "n_targets": 0}
    mean, lo, hi = mean_with_ci(clean, rng=np.random.default_rng(0))
    return {"mean": round(mean, 5), "ci95": [round(lo, 5), round(hi, 5)], "n_targets": len(clean)}


def paired(a, b) -> dict:
    delta, lo, hi, p = paired_mean_difference_ci(
        list(a), list(b), rng=np.random.default_rng(0)
    )
    return {"mean_difference": round(delta, 5), "ci95": [round(lo, 5), round(hi, 5)],
            "two_sided_bootstrap_p": round(p, 5), "n_targets": len(a)}


def evaluate_track(name: str, train: pd.DataFrame, test: pd.DataFrame):
    test = test.copy().reset_index(drop=True)
    rng = np.random.default_rng(0)
    test["random"] = rng.random(len(test))
    sequence = test["sequence"].astype(str).str.upper().str.replace("U", "T")
    test["gc_full"] = sequence.map(lambda s: (s.count("G") + s.count("C")) / max(1, len(s)))
    model_specs = {"mlp30": 30, "cnn30": 30, "mlp148": 148}
    for model_name, length in model_specs.items():
        seed_scores = [fit_score(model_name, train, test, length, seed) for seed in SEEDS]
        test[model_name] = np.mean(np.vstack(seed_scores), axis=0)

    methods = ["random", "gc_full", "mlp30", "cnn30", "mlp148"]
    metric_tables = [expected_random_target_metrics(test, name)] + [
        target_metrics(test, method, name) for method in methods[1:]
    ]
    metrics = pd.concat(metric_tables, ignore_index=True)
    result = {
        "n_train_rows": int(len(train)),
        "n_test_rows": int(len(test)),
        "n_train_targets": int(train["target_id"].nunique()),
        "n_test_targets": int(test["target_id"].nunique()),
        "target_overlap": int(len(set(train["target_id"]) & set(test["target_id"]))),
        "methods": {},
        "paired_vs_random": {},
    }
    random_metrics = metrics[metrics["method"] == "random"].sort_values("target_id")
    for method in methods:
        current = metrics[metrics["method"] == method].sort_values("target_id")
        result["methods"][method] = {
            "pooled_spearman": 0.0 if method == "random" else round(
                float(stats.spearmanr(test[method], test["ON_OFF"]).correlation), 5
            ),
            "target_spearman": summarize(current["target_spearman"]),
            "ndcg_at_10": summarize(current["ndcg_at_10"]),
            "normalized_regret_at_10": summarize(current["normalized_regret_at_10"]),
            "normalized_regret_at_1": summarize(current["normalized_regret_at_1"]),
        }
        if method != "random":
            result["paired_vs_random"][method] = {
                "ndcg_at_10": paired(current["ndcg_at_10"], random_metrics["ndcg_at_10"]),
                "normalized_regret_at_10": paired(
                    random_metrics["normalized_regret_at_10"], current["normalized_regret_at_10"]
                ),
            }
    return result, metrics


def main():
    data = pd.read_csv(MAPPING)
    data = data[data["category"].isin(["TF", "virus"])].copy().reset_index(drop=True)
    manifest = build_manifest(data)
    manifest.to_csv(MANIFEST, index=False)
    data = attach_source_manifest(data, manifest)
    row_split_audit = published_split_audit(data)

    mixed_train = data[data["split"] == "train"].reset_index(drop=True)
    mixed_test = data[data["split"] == "test"].reset_index(drop=True)
    mixed_result, mixed_metrics = evaluate_track("source_disjoint_mixed", mixed_train, mixed_test)

    domain_train = data[data["category"] == "TF"].reset_index(drop=True)
    domain_test = data[data["category"] == "virus"].reset_index(drop=True)
    domain_result, domain_metrics = evaluate_track("TF_to_virus_domain_OOD", domain_train, domain_test)

    all_metrics = pd.concat([mixed_metrics, domain_metrics], ignore_index=True)
    all_metrics.to_csv(TARGET_METRICS, index=False)
    result = {
        "version": "0.2",
        "label_semantics": "BEACON-reported normalized ON_OFF; not canonical ON-minus-OFF",
        "random_baseline": "exact per-target expectation over all candidate permutations",
        "published_row_split_audit": row_split_audit,
        "excluded_from_target_ranking": {"category": "random", "reason": "one pooled source group"},
        "manifest_counts": manifest.groupby(["category", "split"]).size().unstack(fill_value=0).to_dict(),
        "tracks": {
            "source_disjoint_mixed": mixed_result,
            "TF_to_virus_domain_OOD": domain_result,
        },
    }
    with open(OUT, "w") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
    print(json.dumps(result, indent=2))
    print("wrote", MANIFEST)
    print("wrote", TARGET_METRICS)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
