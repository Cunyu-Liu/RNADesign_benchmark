"""P4 v2: E1 prediction!=design, E2 split-stress (rho), E5 ratio pathology (absolute success)."""
import json
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, "/home/cunyuliu/ToeholdDesignBench/src")
from metrics.metrics import success_at_k, mean_with_ci  # noqa: E402

CANON = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_records.parquet"
SPLIT = "/mnt/cunyuliu/ToeholdDesignBench/processed/split_manifests.csv"
OUT = "/mnt/cunyuliu/ToeholdDesignBench/processed/p4_experiments.json"

SEED = 0
np.random.seed(SEED)

df = pd.read_parquet(CANON)
df = df[df["admission_status"] == "admitted_paired"].copy()
df = df[df["ON_OFF"].notna()].reset_index(drop=True)
sp = pd.read_csv(SPLIT)
df = df.merge(sp, on="target_id", how="left")

# two success definitions: relative (LEAKY, kept for comparison) and ABSOLUTE (pre-registered, clean)
df["succ_rel"] = (df.groupby("target_id")["ON_OFF"].transform("quantile", 0.8) <= df["ON_OFF"]).astype(int)
df["succ_abs"] = ((df["ON"] >= 0.5) & (df["OFF"] <= 0.5)).astype(int)
print("abs success positive rate:", round(df["succ_abs"].mean(), 4), " targets with >=1 abs success:",
      (df.groupby("target_id")["succ_abs"].sum() > 0).sum())

STRUCT = ["gc_trigger", "salis_onoff", "mfe_switch_off", "mfe_switch_on", "mfe_trigger"]
for c in STRUCT:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

def onehot(seqs, L=30, n=4):
    m = {"A": 0, "C": 1, "G": 2, "T": 3}
    X = np.zeros((len(seqs), L * n), dtype=np.float32)
    for i, s in enumerate(seqs):
        for j, ch in enumerate(str(s)[:L]):
            if ch in m:
                X[i, j * n + m[ch]] = 1.0
    return X

import torch
def train_mlp(in_dim, Xtr, ytr, epochs=15):
    torch.manual_seed(SEED)
    m = torch.nn.Sequential(torch.nn.Linear(in_dim, 64), torch.nn.ReLU(),
                            torch.nn.Linear(64, 32), torch.nn.ReLU(), torch.nn.Linear(32, 1)).cuda()
    Xt = torch.tensor(Xtr, device="cuda")
    yt = torch.log1p(torch.tensor(ytr, dtype=torch.float32, device="cuda").clamp(min=0)).unsqueeze(1)
    opt = torch.optim.Adam(m.parameters(), lr=1e-3)
    for _ in range(epochs):
        opt.zero_grad(); loss = torch.nn.functional.mse_loss(m(Xt), yt); loss.backward(); opt.step()
    m.eval(); return m

def predict(m, X):
    with torch.no_grad(): return m(torch.tensor(X, device="cuda")).squeeze(1).cpu().numpy()

tr = df[df["split"] == "train"].reset_index(drop=True)
te = df[df["split"] == "test"].reset_index(drop=True)

# ============ E1: rho vs design utility ============
def succ_at_1(te_df, scores):
    te2 = te_df.copy(); te2["score"] = scores
    return [success_at_k(g.sort_values("score", ascending=False)["record_id"].tolist(),
                         dict(zip(g["record_id"], g["succ_abs"].astype(bool))), 1)
            for _, g in te2.groupby("target_id")]

e1 = {}
for name in ["B0_gc", "B1_thermo", "B2_mlp"]:
    if name == "B0_gc":
        s = te["gc_trigger"].values
    elif name == "B1_thermo":
        s = te["salis_onoff"].copy().replace(0.0, np.nan).fillna(te["mfe_switch_off"]).fillna(0).values
    else:
        m = train_mlp(120, onehot(tr["trigger"].tolist()), tr["ON_OFF"].values)
        s = predict(m, onehot(te["trigger"].tolist()))
    rho = stats.spearmanr(s, te["ON_OFF"].values).correlation
    e1[name] = {"rho": round(float(rho), 4), "succ_at_1": round(float(np.mean(succ_at_1(te, s))), 4)}
print("\n=== E1 ===")
for k, v in e1.items(): print(f"  {k} rho={v['rho']:.3f} s@1={v['succ_at_1']:.3f}")

# ============ E2: split stress via test rho + leak fraction ============
def mlp_rho(tr_df, te_df):
    m = train_mlp(120, onehot(tr_df["trigger"].tolist()), tr_df["ON_OFF"].values)
    s = predict(m, onehot(te_df["trigger"].tolist()))
    return float(stats.spearmanr(s, te_df["ON_OFF"].values).correlation)

src_rho = mlp_rho(tr, te)
idx = np.random.default_rng(SEED).permutation(len(df)); ntr = int(len(df) * 0.8)
row_tr = df.iloc[idx[:ntr]].reset_index(drop=True); row_te = df.iloc[idx[ntr:]].reset_index(drop=True)
row_rho = mlp_rho(row_tr, row_te)
leak_src = te["target_id"].isin(set(tr["target_id"])).mean()
leak_row = row_te["target_id"].isin(set(row_tr["target_id"])).mean()
e2 = {"source_disjoint_test_rho": round(src_rho, 4), "row_random_test_rho": round(row_rho, 4),
      "source_disjoint_leak": round(float(leak_src), 4), "row_random_leak": round(float(leak_row), 4)}
print(f"\n=== E2: source rho={src_rho:.3f} (leak {leak_src:.3f}) vs row rho={row_rho:.3f} (leak {leak_row:.3f}) ===")

# ============ E5: ratio pathology (absolute pre-registered success) ============
e5 = {"ratio": [], "on_only": [], "off_only": [], "pareto": []}
for tid, g in te.groupby("target_id"):
    succ = dict(zip(g["record_id"], g["succ_abs"].astype(bool)))
    if g["succ_abs"].sum() == 0: continue
    e5["ratio"].append(success_at_k(g.sort_values("ON_OFF", ascending=False)["record_id"].tolist(), succ, 1))
    e5["on_only"].append(success_at_k(g.sort_values("ON", ascending=False)["record_id"].tolist(), succ, 1))
    e5["off_only"].append(success_at_k(g.sort_values("OFF", ascending=True)["record_id"].tolist(), succ, 1))
    pts = list(zip(g["record_id"], g["ON"], g["OFF"]))
    pareto = [p for p in pts if not any((q[1] >= p[1] and q[2] <= p[2] and (q[1] > p[1] or q[2] < p[2])) for q in pts)]
    e5["pareto"].append(success_at_k([p[0] for p in pareto], succ, 1))
e5 = {k: round(float(np.mean(v)), 4) for k, v in e5.items()}
print(f"\n=== E5 (absolute success ON>=0.5 & OFF<=0.5): {e5} ===")

json.dump({"E1": e1, "E2": e2, "E5": e5}, open(OUT, "w"), indent=2)
print("\nwrote", OUT)