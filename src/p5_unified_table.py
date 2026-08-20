"""T5 (clean): unified table — PREDICTION quality (spearman rho) vs DESIGN utility.
Design values read from authoritative p3_baselines.json. Prediction rho computed
self-contained for the predictors with a valid continuous score (random, gc, thermo,
plus a single k-mer MLP). No import of p3_baselines (avoids side-effects/nan).
"""
import json, sys
import numpy as np
import pandas as pd
import torch
from scipy.stats import spearmanr

CANON = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_records.parquet"
SPLIT = "/mnt/cunyuliu/ToeholdDesignBench/processed/split_manifests.csv"
P3JSON = "/mnt/cunyuliu/ToeholdDesignBench/processed/p3_baselines.json"
OUT = "/mnt/cunyuliu/ToeholdDesignBench/processed/p5_unified_table.json"

df = pd.read_parquet(CANON)
df = df[df["admission_status"] == "admitted_paired"].copy()
df = df[df["ON_OFF"].notna()].reset_index(drop=True)
sp = pd.read_csv(SPLIT)
df = df.merge(sp, on="target_id", how="left")
tr = df[df["split"] == "train"].reset_index(drop=True)
te = df[df["split"] == "test"].reset_index(drop=True)
y = te["ON_OFF"].values
p3 = json.load(open(P3JSON))  # design numbers

def rho_clean(sc, yv=y):
    a = np.asarray(sc, float)
    ok = np.isfinite(a) & np.isfinite(yv)
    if ok.sum() < 3 or np.all(a[ok] == a[ok][0]):
        return float("nan")
    return float(spearmanr(a[ok], yv[ok])[0])

def onehot(seqs, L=30):
    mp = {"A":0,"C":1,"G":2,"T":3,"U":3,"N":0}
    X = np.zeros((len(seqs), L, 4))
    for i, s in enumerate(seqs):
        for j, ch in enumerate(str(s).upper()[:L]):
            X[i, j, mp.get(ch,0)] = 1
    return X

def train_mlp(Xtr, ytr, Xte, seed=0):
    torch.manual_seed(seed); torch.cuda.manual_seed_all(seed); np.random.seed(seed)
    m = torch.nn.Sequential(torch.nn.Flatten(), torch.nn.Linear(120,64), torch.nn.ReLU(),
                            torch.nn.Linear(64,32), torch.nn.ReLU(), torch.nn.Linear(32,1))
    dev = "cuda" if torch.cuda.is_available() else "cpu"; m = m.to(dev)
    opt = torch.optim.Adam(m.parameters(), lr=1e-3)
    Xt = torch.tensor(Xtr, dtype=torch.float32).to(dev); yt = torch.tensor(ytr, dtype=torch.float32).to(dev)
    for _ in range(15):
        m.train(); opt.zero_grad()
        loss = torch.mean((m(Xt).squeeze(-1)-yt)**2); loss.backward(); opt.step()
    m.eval()
    with torch.no_grad():
        return m(torch.tensor(Xte, dtype=torch.float32).to(dev)).squeeze(-1).cpu().numpy()

Xo = onehot(tr["trigger"]); mlp = train_mlp(Xo.reshape(len(Xo),-1), tr["ON_OFF"].values,
                                            onehot(te["trigger"]).reshape(len(te),-1))

pred_rho = {
    "B0_random": rho_clean(np.random.RandomState(0).random(len(te))),
    "B0_gc": rho_clean(te["gc_trigger"].values),
    "B1_thermo": rho_clean(te["salis_onoff"].replace(0.0, np.nan).fillna(te["mfe_switch_off"]).fillna(0).values),
    "B2_mlp": rho_clean(mlp),
    # deep/struct baselines: design-only (no simple closed-form score); rho computed where score exists
}

# Design values from P3 json (same split/metrics)
d = {m: p3[m] for m in p3 if m in ["B0_random","B0_gc","B1_thermo","B2_mlp","B2_cnn","B3_deep","B4_struct","B5_structrank"]}

rows = []
for m in ["B0_random","B0_gc","B1_thermo","B2_mlp","B2_cnn","B3_deep","B4_struct","B5_structrank"]:
    dd = d.get(m, {})
    rows.append({
        "method": m,
        "pred_rho": pred_rho.get(m),
        "pred_R2": float("nan"),  # feature/uncalibrated; regressor MLP R2 is n_m; we emphasize rho
        "s1": dd.get("s1", {}).get("mean"),
        "s3": dd.get("s3", {}).get("mean"),
        "ndcg10": dd.get("ndcg", {}).get("mean"),
        "regret": dd.get("regret", {}).get("mean"),
    })

def is_ok(x):
    return x is not None and (isinstance(x, float) and x == x)

by_rho = sorted([r for r in rows if is_ok(r["pred_rho"])], key=lambda r: r["pred_rho"], reverse=True)
by_s1 = sorted(rows, key=lambda r: r["s1"] if r["s1"]==r["s1"] else -9, reverse=True)

# E1 stat on pairs where BOTH prediction rho and design s1 available
both = [(r["pred_rho"], r["s1"]) for r in rows if is_ok(r["pred_rho"]) and is_ok(r["s1"])]
rankcorr = float(spearmanr([b[0] for b in both], [b[1] for b in both])[0]) if len(both) >= 3 else float("nan")

print(f"{'method':12s} pred_rho |   s@1   s@3  ndcg10 regret")
for r in rows:
    pr = '%.3f' % r["pred_rho"] if (r["pred_rho"] == r["pred_rho"] and r["pred_rho"] is not None) else '   n/a'
    s1 = r["s1"] if r["s1"] is not None else float("nan")
    s3 = r["s3"] if r["s3"] is not None else float("nan")
    nd = r["ndcg10"] if r["ndcg10"] is not None else float("nan")
    rg = r["regret"] if r["regret"] is not None else float("nan")
    print(f"{r['method']:12s} {pr:>9s} | {s1:.3f} {s3:.3f} {nd:.3f} {rg:.3f}")

print("\nBest predictor (rho):", by_rho[0]["method"], by_rho[0]["pred_rho"])
print("Best designer (s@1): ", by_s1[0]["method"], by_s1[0]["s1"])
print("E1: predictor != designer =>", by_rho[0]["method"] != by_s1[0]["method"])
print("rho->s@1 rank corr (methods with both):", round(rankcorr, 3))

json.dump({"table": rows, "best_predictor": by_rho[0]["method"], "best_designer": by_s1[0]["method"],
           "predictor_designer_rank_corr": round(rankcorr, 3), "e1_supported": by_rho[0]["method"] != by_s1[0]["method"]},
          open(OUT, "w"), indent=2)
print("wrote", OUT)