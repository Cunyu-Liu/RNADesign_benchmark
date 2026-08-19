"""Gate 0 To-do D: R1 top-K sanity baselines + metrics (O0-07).

Runs 4 baseline families on the canonical pilot under (a) source-disjoint and
(b) row-random splits, and reports per-target design-utility metrics with
target-level bootstrap CI.
"""
import json
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/cunyuliu/ToeholdDesignBench/src")
from metrics.metrics import success_at_k, ndcg_at_k, normalized_regret, pareto_front_size, mean_with_ci  # noqa: E402

PARQUET = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_pilot.parquet"
OUT = "/mnt/cunyuliu/ToeholdDesignBench/processed/baseline_summary.json"

df = pd.read_parquet(PARQUET)
df = df[df["admission_status"] == "admitted_paired"].copy()
df = df[df["ON_OFF"].notna()].reset_index(drop=True)
print("admitted_paired with ON_OFF:", len(df))

# --- success definition (pre-registered prototype): top-20% ON_OFF within target ---
thr = df.groupby("target_id")["ON_OFF"].transform("quantile", 0.8)
df["success"] = (df["ON_OFF"] >= thr).astype(int)
print("targets:", df["target_id"].nunique(), " success positives:", int(df["success"].sum()))

# --- inputs ---
def onehot(seqs, n=4, L=30):
    m = {"A": 0, "C": 1, "G": 2, "T": 3}
    X = np.zeros((len(seqs), L * n), dtype=np.float32)
    for i, s in enumerate(seqs):
        for j, ch in enumerate(s[:L]):
            if ch in m:
                X[i, j * n + m[ch]] = 1.0
    return X

# --- baseline scorers (take train df, test df -> test scores aligned) ---
class Scorers:
    @staticmethod
    def random(test_df, rng):
        return rng.random(len(test_df))

    @staticmethod
    def gc(test_df, rng):
        return test_df["gc_trigger"].fillna(0.0).values

    @staticmethod
    def thermo(test_df, rng):
        # NUPACK/tsgen-style proxy: RBS-calculator ON:OFF where present, else switch-MFE
        s = test_df["salis_onoff"].copy()
        mfe = test_df["mfe_switch_off"].copy()
        s = s.fillna(mfe)
        return s.fillna(0.0).values

    @staticmethod
    def mlp(train_df, test_df, epochs=8, rng=None):
        import torch
        torch.manual_seed(0)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        Xtr = torch.tensor(onehot(train_df["trigger"].tolist()), device=device)
        Xte = torch.tensor(onehot(test_df["trigger"].tolist()), device=device)
        ytr = torch.tensor(train_df["ON_OFF"].values, dtype=torch.float32, device=device).unsqueeze(1)
        ytr = torch.log1p(ytr.clamp(min=0))
        model = torch.nn.Sequential(
            torch.nn.Linear(120, 64), torch.nn.ReLU(),
            torch.nn.Linear(64, 32), torch.nn.ReLU(),
            torch.nn.Linear(32, 1),
        ).to(device)
        opt = torch.optim.Adam(model.parameters(), lr=1e-3)
        lossf = torch.nn.MSELoss()
        model.train()
        for _ in range(epochs):
            opt.zero_grad()
            loss = lossf(model(Xtr), ytr)
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            pred = model(Xte).squeeze(1).cpu().numpy()
        return pred


SCORERS = {
    "B0_random": lambda tr, te, rng: Scorers.random(te, rng),
    "B0_gc_rule": lambda tr, te, rng: Scorers.gc(te, rng),
    "B1_thermo": lambda tr, te, rng: Scorers.thermo(te, rng),
    "B2_mlp": Scorers.mlp,
}


def evaluate(split_seed=0, split_type="source"):
    rng_np = np.random.default_rng(split_seed)
    if split_type == "source":
        targets = df["target_id"].unique()
        rng_np.shuffle(targets)
        ntr = int(len(targets) * 0.8)
        train_t = set(targets[:ntr])
        te_mask = ~df["target_id"].isin(train_t)
    else:  # row random
        idx = rng_np.permutation(len(df))
        ntr = int(len(df) * 0.8)
        te_mask = np.zeros(len(df), dtype=bool)
        te_mask[idx[ntr:]] = True
    tr_df = df[~te_mask].reset_index(drop=True)
    te_df = df[te_mask].reset_index(drop=True)

    results = {}
    for name, scorer in SCORERS.items():
        rng = np.random.default_rng(split_seed)
        try:
            if name == "B2_mlp":
                scores = Scorers.mlp(tr_df, te_df)
            else:
                scores = scorer(tr_df, te_df, rng)
        except Exception as e:
            print(f"  {name} failed: {e}")
            continue
        te_df = te_df.copy()
        te_df["score"] = np.asarray(scores, dtype=float)

        per_target = {"s1": [], "s3": [], "s5": [], "ndcg": [], "regret": [], "pareto": []}
        for tid, g in te_df.groupby("target_id"):
            g = g.sort_values("score", ascending=False)
            ranked = g["record_id"].tolist()
            succ = dict(zip(g["record_id"], g["success"].astype(bool)))
            rel = dict(zip(g["record_id"], g["ON_OFF"]))
            on_s = dict(zip(g["record_id"], g["ON"]))
            off_s = dict(zip(g["record_id"], g["OFF"]))
            per_target["s1"].append(success_at_k(ranked, succ, 1))
            per_target["s3"].append(success_at_k(ranked, succ, 3))
            per_target["s5"].append(success_at_k(ranked, succ, 5))
            per_target["ndcg"].append(ndcg_at_k(ranked, rel, 10))
            per_target["regret"].append(normalized_regret(ranked, rel, 10))
            per_target["pareto"].append(pareto_front_size(ranked[:10], on_s, off_s))
        out = {}
        for k, vals in per_target.items():
            m, lo, hi = mean_with_ci(vals, rng=np.random.default_rng(split_seed))
            out[k] = {"mean": round(m, 4), "ci": [round(lo, 4), round(hi, 4)]}
        results[name] = out
    return results


report = {}
for st in ["source", "row"]:
    print(f"\n=== split={st} ===")
    report[st] = evaluate(split_seed=0, split_type=st)
    for name, r in report[st].items():
        print(f"  {name}: success@1={r['s1']['mean']} @3={r['s3']['mean']} @5={r['s5']['mean']} ndcg@10={r['ndcg']['mean']} regret={r['regret']['mean']}")

with open(OUT, "w") as fh:
    json.dump(report, fh, indent=2)
print("\nwrote", OUT)