"""Paired truncated/full-target stress test on the VISTA mCherry study.

The 189 sites belong to one target and one study.  Site-bootstrap intervals below
quantify uncertainty within that study; they are not target-level generalization
intervals and the output deliberately avoids a cross-target claim.
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
from model_utils import onehot_flat, seed_everything, torch_device  # noqa: E402


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TD_ROOT = os.environ.get("TD_BENCH_ROOT", os.path.join(PROJECT_ROOT, "data"))
TD_PROC = os.environ.get("TD_BENCH_PROCESSED", os.path.join(TD_ROOT, "processed"))
CANON = os.path.join(TD_PROC, "canonical_records.parquet")
SPLIT = os.path.join(TD_PROC, "split_manifests.csv")
VISTA = os.path.join(TD_ROOT, "external", "mCH_on_off_rank.xlsx")
OUT = os.path.join(TD_PROC, "vista_paired_context_v02.json")
SEEDS = (0, 1, 2, 3, 4)


def make_mlp():
    return torch.nn.Sequential(
        torch.nn.Linear(120, 64), torch.nn.ReLU(),
        torch.nn.Linear(64, 32), torch.nn.ReLU(), torch.nn.Linear(32, 1),
    )


def fit_predict(train: pd.DataFrame, sequences, seed: int) -> np.ndarray:
    seed_everything(seed)
    device = torch_device()
    model = make_mlp().to(device)
    x_train = torch.tensor(onehot_flat(train["trigger"]), dtype=torch.float32, device=device)
    y_train = torch.tensor(train["ON_OFF"].values, dtype=torch.float32, device=device).unsqueeze(1)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    for _ in range(20):
        optimizer.zero_grad()
        loss = torch.nn.functional.mse_loss(model(x_train), y_train)
        loss.backward()
        optimizer.step()
    model.eval()
    with torch.no_grad():
        x = torch.tensor(onehot_flat(sequences), dtype=torch.float32, device=device)
        return model(x).squeeze(1).cpu().numpy()


def rho(x, y) -> float:
    value = stats.spearmanr(x, y).correlation
    return float(value) if np.isfinite(value) else float("nan")


def site_bootstrap_difference(score, truncated, full, n_bootstrap=5000) -> dict:
    score = np.asarray(score, float)
    truncated = np.asarray(truncated, float)
    full = np.asarray(full, float)
    rng = np.random.default_rng(0)
    differences = []
    for _ in range(n_bootstrap):
        idx = rng.integers(0, len(score), size=len(score))
        d = rho(score[idx], full[idx]) - rho(score[idx], truncated[idx])
        if np.isfinite(d):
            differences.append(d)
    estimate = rho(score, full) - rho(score, truncated)
    return {
        "full_minus_truncated_spearman": round(estimate, 5),
        "site_bootstrap_ci95": [
            round(float(np.quantile(differences, 0.025)), 5),
            round(float(np.quantile(differences, 0.975)), 5),
        ],
        "n_sites": len(score),
        "uncertainty_unit": "site_within_single_mCherry_target",
    }


def topk_overlap(a, b, k=10) -> float:
    top_a = set(np.argsort(-np.asarray(a))[:k])
    top_b = set(np.argsort(-np.asarray(b))[:k])
    return len(top_a & top_b) / k


def main():
    canonical = pd.read_parquet(CANON)
    canonical = canonical[
        (canonical["admission_status"] == "admitted_paired") & canonical["ON_OFF"].notna()
    ].copy()
    canonical = canonical.merge(pd.read_csv(SPLIT), on="target_id", how="left")
    train = canonical[canonical["split"] == "train"].reset_index(drop=True)

    vista = pd.read_excel(VISTA, sheet_name="Calculated Values").dropna(
        subset=["Trigger Sequence", "ON OFF Truncated", "ON OFF Full"]
    ).reset_index(drop=True)
    sequences = vista["Trigger Sequence"].astype(str).str.upper().tolist()
    first30 = [sequence[:30] for sequence in sequences]
    last30 = [sequence[-30:] for sequence in sequences]
    truncated = vista["ON OFF Truncated"].values.astype(float)
    full = vista["ON OFF Full"].values.astype(float)

    scorers = {
        "fused_mlp_first30": np.mean(
            np.vstack([fit_predict(train, first30, seed) for seed in SEEDS]), axis=0
        ),
        "fused_mlp_last30": np.mean(
            np.vstack([fit_predict(train, last30, seed) for seed in SEEDS]), axis=0
        ),
        "tsgen2": -vista["tsgen2 rank"].values.astype(float),
        "gc_first30": np.array([
            (sequence.count("G") + sequence.count("C")) / 30 for sequence in first30
        ]),
        "random": np.random.default_rng(0).random(len(vista)),
    }

    methods = {}
    for name, score in scorers.items():
        methods[name] = {
            "spearman_with_truncated": round(rho(score, truncated), 5),
            "spearman_with_full": round(rho(score, full), 5),
            "paired_context_difference": site_bootstrap_difference(score, truncated, full),
            "top10_overlap_with_truncated_oracle": round(topk_overlap(score, truncated), 5),
            "top10_overlap_with_full_oracle": round(topk_overlap(score, full), 5),
        }

    result = {
        "version": "0.2",
        "scope": "single_target_single_study_paired_context_stress_test",
        "target": "mCherry",
        "n_sites": int(len(vista)),
        "label_context_agreement": {
            "truncated_vs_full_spearman": round(rho(truncated, full), 5),
            "top10_overlap": round(topk_overlap(truncated, full), 5),
            "median_absolute_rank_shift": round(float(np.median(np.abs(
                stats.rankdata(-truncated) - stats.rankdata(-full)
            ))), 5),
        },
        "methods": methods,
        "allowed_interpretation": (
            "assesses paired context agreement and scorer sensitivity for VISTA mCherry; "
            "does not establish cross-target or cross-study generalization"
        ),
    }
    with open(OUT, "w") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
    print(json.dumps(result, indent=2))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
