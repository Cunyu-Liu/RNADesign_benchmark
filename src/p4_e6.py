"""P4 E6 (R1-appropriate): cross-evaluator / proxy-overfitting audit.

For ranking, 'reward/evaluator circularity' reduces to: does a model's top-K, judged by
itself, survive judgment by an independent evaluator (a different model, or the real label)?
We quantify (a) cross-evaluator rank agreement, (b) how a model's #1 pick scores under an
independent ranking / the true ON_OFF.
"""
import json
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, "/home/cunyuliu/ToeholdDesignBench/src")
CANON = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_records.parquet"
SPLIT = "/mnt/cunyuliu/ToeholdDesignBench/processed/split_manifests.csv"
OUT = "/mnt/cunyuliu/ToeholdDesignBench/processed/p4_e6_audit.json"
SEED = 0
np.random.seed(SEED)

df = pd.read_parquet(CANON)
df = df[df["admission_status"] == "admitted_paired"].copy()
df = df[df["ON_OFF"].notna()].reset_index(drop=True)
df = df.merge(pd.read_csv(SPLIT), on="target_id", how="left")
tr = df[df["split"] == "train"].reset_index(drop=True)
te = df[df["split"] == "test"].reset_index(drop=True)

def onehot(seqs):
    m = {"A": 0, "C": 1, "G": 2, "T": 3}
    X = np.zeros((len(seqs), 120), dtype=np.float32)
    for i, s in enumerate(seqs):
        for j, ch in enumerate(str(s)[:30]):
            if ch in m: X[i, j*4 + m[ch]] = 1.0
    return X

import torch
torch.manual_seed(SEED)
model = torch.nn.Sequential(torch.nn.Linear(120, 64), torch.nn.ReLU(),
                            torch.nn.Linear(64, 32), torch.nn.ReLU(), torch.nn.Linear(32, 1)).cuda()
Xt = torch.tensor(onehot(tr["trigger"].tolist()), device="cuda")
yt = torch.log1p(torch.tensor(tr["ON_OFF"].values, dtype=torch.float32, device="cuda").clamp(min=0)).unsqueeze(1)
opt = torch.optim.Adam(model.parameters(), lr=1e-3)
for _ in range(15):
    opt.zero_grad(); loss = torch.nn.functional.mse_loss(model(Xt), yt); loss.backward(); opt.step()
with torch.no_grad():
    A = model(torch.tensor(onehot(te["trigger"].tolist()), device="cuda")).squeeze(1).cpu().numpy()

B = te["salis_onoff"].replace(0.0, np.nan).fillna(te["mfe_switch_off"]).fillna(0).values

# cross-evaluator agreement of #1 picks
te2 = te.copy(); te2["A"] = A; te2["B"] = B
agree = 0; n = 0
for tid, g in te2.groupby("target_id"):
    gA = g.sort_values("A", ascending=False); gB = g.sort_values("B", ascending=False)
    if gA.iloc[0]["record_id"] == gB.iloc[0]["record_id"]:
        agree += 1
    n += 1
agreement = agree / max(1, n)

# proxy overfitting: A's #1 pick, ranked by reality (ON_OFF percentile within target)
median_real_pct = []
for tid, g in te2.groupby("target_id"):
    gA = g.sort_values("A", ascending=False)
    top1 = gA.iloc[0]
    pct = (g["ON_OFF"] < top1["ON_OFF"]).mean()  # fraction of target candidates beaten
    median_real_pct.append(pct)

e6 = {
    "cross_evaluator_top1_agreement": round(float(agreement), 4),
    "A_model": "MLP (sequence)", "B_model": "thermo (RBS/MFE)",
    "A_top1_median_real_ONOFF_percentile": round(float(np.mean(median_real_pct)), 4),
    "interpretation": ("top-1 agreement < 1 => evaluator choice changes the answer; "
                       "A_top1 median real percentile < 1 => self-ranking over-rates picks vs truth (proxy overfitting)"),
}
print(json.dumps(e6, indent=2))
json.dump(e6, open(OUT, "w"), indent=2)
print("wrote", OUT)