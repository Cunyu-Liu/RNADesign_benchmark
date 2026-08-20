"""A1-3: expanded virus-group robustness on BEACON, n=6->23 targets, using SCALE-FREE
ranking metrics (per-target Spearman of predicted ON_OFF vs ON_OFF). Absolute-hit
threshold is deliberately NOT used because BEACON's OFF is independently normalized
(incompatible with canonical). Bootstrap CI over 23 virus test targets.
"""
import json, sys
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import torch

OUT = "/mnt/cunyuliu/ToeholdDesignBench/processed/a1_virus_robustness_n23.json"
MAP = "/mnt/cunyuliu/ToeholdDesignBench/external/beacon_prs/beacon_target_mapping.csv"
df = pd.read_csv(MAP, dtype=str)
for c in ["ON","OFF","ON_OFF"]:
    df[c] = df[c].astype(float)

virus = df[df["category"] == "virus"].copy()
tr = virus[virus["split"] == "train"].reset_index(drop=True)
te = virus[virus["split"] == "test"].reset_index(drop=True)
print(f"virus train {len(tr)} / test {len(te)} / test targets {te['target_id'].nunique()}")

def onehot(seqs, L=30):
    mp = {"A":0,"C":1,"G":2,"T":3,"U":3,"N":0}
    X = np.zeros((len(seqs), L, 4))
    for i, s in enumerate(seqs):
        for j, ch in enumerate(str(s).upper()[:L]):
            X[i, j, mp.get(ch,0)] = 1
    return X

def make_mlp():
    import torch
    return torch.nn.Sequential(torch.nn.Flatten(), torch.nn.Linear(120,64), torch.nn.ReLU(),
                               torch.nn.Linear(64,32), torch.nn.ReLU(), torch.nn.Linear(32,1))

def train(Xtr, ytr, Xte, seed=0):
    torch.manual_seed(seed); torch.cuda.manual_seed_all(seed); np.random.seed(seed)
    m = make_mlp(); dev="cuda" if torch.cuda.is_available() else "cpu"; m=m.to(dev)
    opt = torch.optim.Adam(m.parameters(), lr=1e-3)
    Xt=torch.tensor(Xtr,dtype=torch.float32).to(dev); yt=torch.tensor(ytr,dtype=torch.float32).to(dev)
    for _ in range(20):
        m.train(); opt.zero_grad()
        loss=torch.mean((m(Xt).squeeze(-1)-yt)**2); loss.backward(); opt.step()
    m.eval()
    with torch.no_grad():
        return m(torch.tensor(Xte,dtype=torch.float32).to(dev)).squeeze(-1).cpu().numpy()

Xtr_o=onehot(tr["sequence"]).reshape(len(tr),-1); Xte_o=onehot(te["sequence"]).reshape(len(te),-1)
ytr = tr["ON_OFF"].values
mlp0 = train(Xtr_o, ytr, Xte_o, seed=0)
mlp1 = train(Xtr_o, ytr, Xte_o, seed=1)
mlp2 = train(Xtr_o, ytr, Xte_o, seed=2)
mlp_seeds = [mlp0, mlp1, mlp2]

# scores (aligned to te row order)
scores = {
    "random": np.random.RandomState(0).random(len(te)),
    "gc": te["sequence"].map(lambda s: (str(s).count("G")+str(s).count("C"))/len(str(s))).values,
}
for i, s in enumerate(mlp_seeds):
    scores[f"mlp_seed{i}"] = s
scores["mlp_avg"] = np.mean(mlp_seeds, axis=0)

y_te = te["ON_OFF"].values

# per-target Spearman (ranking utility; scale-free)
def per_target_rho(scores_arr):
    out = {}
    te2 = te.copy(); te2["score"] = scores_arr
    for tid, g in te2.groupby("target_id"):
        if len(g) < 3 or np.unique(g["ON_OFF"]).size < 2:
            continue
        # any two designs to rank; ON_OFF is the relevance
        out[tid] = spearmanr(g["score"], g["ON_OFF"])[0]
    return out

res = {}
for name, sc in scores.items():
    rho = np.array(list(per_target_rho(sc).values()))
    # bootstrap CI over targets
    rng = np.random.default_rng(0)
    boots = [rho[rng.integers(0, len(rho), len(rho))].mean() for _ in range(1000)]
    res[name] = {"n_targets": int(len(rho)),
                 "mean_rho": round(float(rho.mean()), 4),
                 "ci95": [round(float(np.percentile(boots,2.5)),4), round(float(np.percentile(boots,97.5)),4)],
                 "pct_positive": round(float((rho>0).mean()),4)}
    print(f"{name:10s} n_tgt={len(rho):2d} mean_rho={rho.mean():+.4f} CI={res[name]['ci95']} pct_pos={res[name]['pct_positive']}")

json.dump(res, open(OUT,"w"), indent=2)
print("wrote", OUT)