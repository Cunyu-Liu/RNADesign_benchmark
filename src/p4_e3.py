"""Legacy v0.1 transfer analysis retained for audit only.

Use ``vista_paired_context.py`` for the controlling v0.2 paired analysis.

Train a sequence->ON_OFF model on the fused 91k (30-nt), apply to the VISTA mCherry
full-target set (189 x 36-nt tiles, truncate to 30), and measure transfer Spearman rho
against 'ON OFF Full'. Compare to tsgen2 (traditional tool) and random/GC chance.
"""
import json
import sys

import numpy as np
import pandas as pd
from scipy import stats

CANON = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_records.parquet"
VISTA = "/mnt/cunyuliu/ToeholdDesignBench/external/mCH_on_off_rank.xlsx"
OUT = "/mnt/cunyuliu/ToeholdDesignBench/processed/p4_e3_transfer.json"
SEED = 0
np.random.seed(SEED)

# ---- train on fused 91k (all paired) ----
df = pd.read_parquet(CANON)
df = df[df["admission_status"] == "admitted_paired"].copy()
df = df[df["ON_OFF"].notna()].reset_index(drop=True)

def onehot(seqs, L=30):
    m = {"A": 0, "C": 1, "G": 2, "T": 3}
    X = np.zeros((len(seqs), L * 4), dtype=np.float32)
    for i, s in enumerate(seqs):
        for j, ch in enumerate(str(s)[:L]):
            if ch in m:
                X[i, j * 4 + m[ch]] = 1.0
    return X

import torch
torch.manual_seed(SEED)
model = torch.nn.Sequential(torch.nn.Linear(120, 64), torch.nn.ReLU(),
                            torch.nn.Linear(64, 32), torch.nn.ReLU(), torch.nn.Linear(32, 1)).cuda()
Xt = torch.tensor(onehot(df["trigger"].tolist()), device="cuda")
yt = torch.log1p(torch.tensor(df["ON_OFF"].values, dtype=torch.float32, device="cuda").clamp(min=0)).unsqueeze(1)
opt = torch.optim.Adam(model.parameters(), lr=1e-3)
for _ in range(20):
    opt.zero_grad(); loss = torch.nn.functional.mse_loss(model(Xt), yt); loss.backward(); opt.step()
model.eval()

# ---- apply to VISTA full-target ----
v = pd.read_excel(VISTA, sheet_name="Calculated Values")
v = v.dropna(subset=["Trigger Sequence", "ON OFF Full"]).reset_index(drop=True)
trig36 = v["Trigger Sequence"].astype(str).str.upper().tolist()
label = v["ON OFF Full"].values.astype(float)
print("VISTA tiles:", len(v), " trigger len:", len(trig36[0]))

def transfer_rho(seqs):
    X = onehot(seqs, L=30)  # truncate 36 -> first 30
    with torch.no_grad():
        pred = model(torch.tensor(X, device="cuda")).squeeze(1).cpu().numpy()
    return float(stats.spearmanr(pred, label).correlation)

first30 = [s[:30] for s in trig36]
last30 = [s[-30:] for s in trig36]

fused_rho_first = transfer_rho(first30)
fused_rho_last = transfer_rho(last30)

# tsgen2 (traditional tool) transfer: 'tsgen2 rank' (ascending = better); rho vs ON OFF Full
if "tsgen2 rank" in v.columns:
    tsg = v["tsgen2 rank"].values.astype(float)
    tsg_rho = float(stats.spearmanr(-tsg, label).correlation)  # rank ascending => negate
else:
    tsg_rho = None

# GC baseline
gc = [ (s.count("G")+s.count("C"))/30.0 for s in first30 ]
gc_rho = float(stats.spearmanr(gc, label).correlation)

# random baseline (seed)
rng = np.random.default_rng(SEED)
rand_rho = float(stats.spearmanr(rng.random(len(label)), label).correlation)

e3 = {
    "n_vista_tiles": int(len(v)),
    "fused_mlp_transfer_rho_first30": round(fused_rho_first, 4),
    "fused_mlp_transfer_rho_last30": round(fused_rho_last, 4),
    "tsgen2_transfer_rho": round(tsg_rho, 4) if tsg_rho is not None else None,
    "gc_transfer_rho": round(gc_rho, 4),
    "random_transfer_rho": round(rand_rho, 4),
}
print(json.dumps(e3, indent=2))
json.dump(e3, open(OUT, "w"), indent=2)
print("wrote", OUT)
