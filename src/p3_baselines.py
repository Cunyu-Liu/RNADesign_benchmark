"""P3: reproduce 6 core baseline families under a unified interface (R1 ranking).

Baselines (contract 8.1) — honest local names, NOT bound to third-party tools:
  B0 random/rule, B1 traditional thermodynamic proxy (RBS/MFE),
  B2 plain MLP and 1-D CNN (k-mer input; design pattern of Angenent-Mari nets),
  B3 deep encoder+head (1-D conv), B4 seq+structure concat, B5 structure-rich ranker.
These are representative families to probe the prediction->design axis; they do NOT
re-implement or endorse STORM/NuSpeak, SANDSTORM, or Toehold-VISTA.
Five seeds for learned models; source-disjoint split; design-utility metrics
(success@K/NDCG/regret/Pareto-front coverage).
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from metrics.metrics import (  # noqa: E402
    success_at_k, ndcg_at_k, normalized_regret, pareto_front_coverage, mean_with_ci,
    expected_random_ranking_metrics,
)
from model_utils import onehot_flat, onehot_channels, seed_everything, torch_device  # noqa: E402

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TD_ROOT = os.environ.get("TD_BENCH_ROOT", os.path.join(PROJECT_ROOT, "data"))
TD_PROC = os.environ.get("TD_BENCH_PROCESSED", os.path.join(TD_ROOT, "processed"))
CANON = os.path.join(TD_PROC, "canonical_records.parquet")
SPLIT = os.path.join(TD_PROC, "split_manifests.csv")
OUT = os.path.join(TD_PROC, "p3_baselines_v02.json")
SCORES_OUT = os.path.join(TD_PROC, "p3_test_scores_v02.csv")

SEED = 0
SEEDS = (0, 1, 2, 3, 4)

df = pd.read_parquet(CANON)
df = df[df["admission_status"] == "admitted_paired"].copy()
df = df[df["ON_OFF"].notna()].reset_index(drop=True)
sp = pd.read_csv(SPLIT)
df = df.merge(sp, on="target_id", how="left")

# FIX-2: pre-registered ABSOLUTE success (test-independent): ON>=0.5 AND OFF<=0.5
df["success"] = ((df["ON"] >= 0.5) & (df["OFF"] <= 0.5)).astype(int)

STRUCT_COLS = ["gc_trigger", "salis_onoff", "mfe_switch_off", "mfe_switch_on", "mfe_trigger"]
for c in STRUCT_COLS:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

def struct_mat(d):
    return d[STRUCT_COLS].values.astype(np.float32)


# ---------------- deep models (torch, GPU) ----------------
def _fit_predict(model_fn, Xtr, ytr, Xte, epochs, seed, lr=1e-3):
    import torch

    # Seed before model construction so initial weights differ only by the
    # declared replicate seed.
    seed_everything(seed)
    device = torch_device()
    model = model_fn().to(device)
    Xt = torch.tensor(Xtr, dtype=torch.float32, device=device)
    # ON_OFF is a signed difference in the canonical track.  Preserve all values.
    yt = torch.tensor(ytr, dtype=torch.float32, device=device).unsqueeze(1)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    lossf = torch.nn.MSELoss()
    model.train()
    for _ in range(epochs):
        opt.zero_grad(); loss = lossf(model(Xt), yt); loss.backward(); opt.step()
    model.eval()
    with torch.no_grad():
        return model(torch.tensor(Xte, dtype=torch.float32, device=device)).squeeze(1).cpu().numpy()


def make_mlp(in_dim):
    import torch
    return torch.nn.Sequential(torch.nn.Linear(in_dim, 64), torch.nn.ReLU(),
                               torch.nn.Linear(64, 32), torch.nn.ReLU(), torch.nn.Linear(32, 1))

def make_cnn():
    import torch
    return torch.nn.Sequential(
        torch.nn.Conv1d(4, 64, 5), torch.nn.ReLU(), torch.nn.AdaptiveAvgPool1d(1),
        torch.nn.Flatten(), torch.nn.Linear(64, 32), torch.nn.ReLU(), torch.nn.Linear(32, 1))

def make_deep1d():
    import torch
    return torch.nn.Sequential(
        torch.nn.Conv1d(4, 64, 5), torch.nn.ReLU(), torch.nn.Conv1d(64, 128, 3), torch.nn.ReLU(),
        torch.nn.AdaptiveAvgPool1d(1), torch.nn.Flatten(), torch.nn.Linear(128, 64), torch.nn.ReLU(),
        torch.nn.Linear(64, 1))


# ---------------- baseline scorer (fit on train, score test) ----------------
def scorer(name, tr, te, seed=SEED):
    if name == "B0_random":
        rng = np.random.default_rng(seed)
        return rng.random(len(te))
    if name == "B0_gc":
        return te["gc_trigger"].values
    if name == "B1_thermo":
        s = te["salis_onoff"].copy()
        s = s.replace(0.0, np.nan).fillna(te["mfe_switch_off"])
        return s.fillna(0).values
    # deep baselines (fit on train)
    Xtr_o, Xte_o = onehot_flat(tr["trigger"].tolist()), onehot_flat(te["trigger"].tolist())
    ytr = tr["ON_OFF"].values
    if name == "B2_mlp":
        return _fit_predict(lambda: make_mlp(120), Xtr_o, ytr, Xte_o, epochs=15, seed=seed)
    if name == "B2_cnn":
        Xtr_c = onehot_channels(tr["trigger"].tolist()); Xte_c = onehot_channels(te["trigger"].tolist())
        return _fit_predict(make_cnn, Xtr_c, ytr, Xte_c, epochs=15, seed=seed)
    if name == "B3_deep":
        Xtr_c = onehot_channels(tr["trigger"].tolist()); Xte_c = onehot_channels(te["trigger"].tolist())
        return _fit_predict(make_deep1d, Xtr_c, ytr, Xte_c, epochs=15, seed=seed)
    if name == "B4_struct":
        Xtr = np.hstack([Xtr_o, struct_mat(tr)]); Xte = np.hstack([Xte_o, struct_mat(te)])
        return _fit_predict(lambda: make_mlp(125), Xtr, ytr, Xte, epochs=15, seed=seed)
    if name == "B5_structrank":
        Xtr = np.hstack([Xtr_o, struct_mat(tr)]); Xte = np.hstack([Xte_o, struct_mat(te)])
        return _fit_predict(lambda: make_mlp(125), Xtr, ytr, Xte, epochs=20, seed=seed)
    raise ValueError(name)


BASELINES = ["B0_random", "B0_gc", "B1_thermo", "B2_mlp", "B2_cnn", "B3_deep", "B4_struct", "B5_structrank"]
LEARNED = {"B2_mlp", "B2_cnn", "B3_deep", "B4_struct", "B5_structrank"}


def evaluate_scores(test, scores):
    s1, s3, s5, ndcg, regret, pareto = [], [], [], [], [], []
    evaluated = test.copy()
    evaluated["score"] = np.asarray(scores, dtype=float)
    for _, group in evaluated.groupby("target_id", sort=True):
        group = group.sort_values(["score", "record_id"], ascending=[False, True])
        ranked = group["record_id"].tolist()
        success = dict(zip(group["record_id"], group["success"].astype(bool)))
        relevance = dict(zip(group["record_id"], group["ON_OFF"]))
        on = dict(zip(group["record_id"], group["ON"]))
        off = dict(zip(group["record_id"], group["OFF"]))
        s1.append(success_at_k(ranked, success, 1))
        s3.append(success_at_k(ranked, success, 3))
        s5.append(success_at_k(ranked, success, 5))
        ndcg.append(ndcg_at_k(ranked, relevance, 10))
        regret.append(normalized_regret(ranked, relevance, 10))
        pareto.append(pareto_front_coverage(ranked, on, off, 10))
    result = {}
    for metric, values in {
        "success_at_1": s1,
        "success_at_3": s3,
        "success_at_5": s5,
        "ndcg_at_10": ndcg,
        "normalized_regret_at_10": regret,
        "pareto_front_coverage_at_10": pareto,
    }.items():
        mean, lo, hi = mean_with_ci(values, rng=np.random.default_rng(SEED))
        result[metric] = {
            "mean": round(mean, 5),
            "ci95": [round(lo, 5), round(hi, 5)],
            "n_targets": len(values),
        }
    return result


def evaluate_expected_random(test):
    values = {
        "success_at_1": [], "success_at_3": [], "success_at_5": [],
        "ndcg_at_10": [], "normalized_regret_at_10": [],
        "pareto_front_coverage_at_10": [],
    }
    for _, group in test.groupby("target_id", sort=True):
        ids = group["record_id"].tolist()
        metrics = expected_random_ranking_metrics(
            ids,
            dict(zip(ids, group["success"].astype(bool))),
            dict(zip(ids, group["ON_OFF"])),
            dict(zip(ids, group["ON"])),
            dict(zip(ids, group["OFF"])),
        )
        for metric in values:
            values[metric].append(metrics[metric])
    result = {}
    for metric, target_values in values.items():
        mean, lo, hi = mean_with_ci(target_values, rng=np.random.default_rng(SEED))
        result[metric] = {
            "mean": round(mean, 5),
            "ci95": [round(lo, 5), round(hi, 5)],
            "n_targets": len(target_values),
        }
    return result

tr = df[df["split"] == "train"].reset_index(drop=True)
te = df[df["split"] == "test"].reset_index(drop=True)
print(f"train records {len(tr)}, test records {len(te)}, test targets {te.target_id.nunique()}")

report = {
    "version": "0.2",
    "label_semantics": "signed canonical ON minus OFF",
    "seed_policy": {
        "learned_models": list(SEEDS),
        "reported_score": "mean prediction across seeds",
        "random_baseline": "exact per-target expectation over all candidate permutations",
    },
    "target_accounting": {
        "n_test_targets": int(te["target_id"].nunique()),
        "n_targets_with_feasible_candidate": int(te.groupby("target_id")["success"].any().sum()),
        "n_targets_without_feasible_candidate": int((~te.groupby("target_id")["success"].any()).sum()),
    },
    "methods": {},
}
score_table = te[["target_id", "record_id", "ON", "OFF", "ON_OFF", "success"]].copy()
for name in BASELINES:
    try:
        seeds = SEEDS if name in LEARNED else (SEED,)
        seed_scores = [scorer(name, tr, te, seed) for seed in seeds]
    except Exception as e:
        report["methods"][name] = {"error": str(e)}
        print(f"{name}: ERROR {e}")
        continue
    ensemble_scores = np.mean(np.vstack(seed_scores), axis=0)
    score_table[name] = ensemble_scores
    if name == "B0_random":
        method_report = {
            "ensemble": evaluate_expected_random(te),
            "score_column_note": "seed-0 draw retained for row-level audit; not used for paper metrics",
        }
    else:
        method_report = {"ensemble": evaluate_scores(te, ensemble_scores)}
    if name in LEARNED:
        method_report["per_seed"] = {}
        for seed, scores in zip(seeds, seed_scores):
            score_table[f"{name}_seed_{seed}"] = scores
            method_report["per_seed"][str(seed)] = evaluate_scores(te, scores)
    report["methods"][name] = method_report
    r = method_report["ensemble"]
    print(
        f"{name:16s} s@1={r['success_at_1']['mean']:.3f} "
        f"s@3={r['success_at_3']['mean']:.3f} "
        f"ndcg@10={r['ndcg_at_10']['mean']:.3f} "
        f"regret={r['normalized_regret_at_10']['mean']:.3f}"
    )

score_table.to_csv(SCORES_OUT, index=False)
json.dump(report, open(OUT, "w"), indent=2, allow_nan=False)
print("wrote", OUT)
print("wrote", SCORES_OUT)
