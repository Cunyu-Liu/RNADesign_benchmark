"""P4 E4: target-context ablation (seeded). seq-only vs seq+structure vs target-aware."""
import json
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, "/home/cunyuliu/ToeholdDesignBench/src")
from metrics.metrics import success_at_k  # noqa: E402

CANON = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_records.parquet"
SPLIT = "/mnt/cunyuliu/ToeholdDesignBench/processed/split_manifests.csv"
OUT = "/mnt/cunyuliu/ToeholdDesignBench/processed/p4_e4_ablation.json"
SEED = 0
np.random.seed(SEED)

df = pd.read_parquet(CANON)
df = df[df["admission_status"] == "admitted_paired"].copy()
df = df[df["ON_OFF"].notna()].reset_index(drop=True)
df = df.merge(pd.read_csv(SPLIT), on="target_id", how="left")
df["success"] = ((df["ON"] >= 0.5) & (df["OFF"] <= 0.5)).astype(int)

STRUCT = ["gc_trigger", "salis_onoff", "mfe_switch_off", "mfe_switch_on", "mfe_trigger"]
for c in STRUCT:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

def onehot(seqs):
    m = {"A": 0, "C": 1, "G": 2, "T": 3}
    X = np.zeros((len(seqs), 120), dtype=np.float32)
    for i, s in enumerate(seqs):
        for j, ch in enumerate(str(s)[:30]):
            if ch in m: X[i, j * 4 + m[ch]] = 1.0
    return X

import torch
def fit_eval(Xtr, ytr, Xte, epochs):
    torch.manual_seed(SEED)
    model = torch.nn.Sequential(torch.nn.Linear(Xtr.shape[1], 64), torch.nn.ReLU(),
                                torch.nn.Linear(64, 32), torch.nn.ReLU(), torch.nn.Linear(32, 1)).cuda()
    Xt = torch.tensor(Xtr, device="cuda")
    yt = torch.log1p(torch.tensor(ytr, dtype=torch.float32, device="cuda").clamp(min=0)).unsqueeze(1)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    for _ in range(epochs):
        opt.zero_grad(); loss = torch.nn.functional.mse_loss(model(Xt), yt); loss.backward(); opt.step()
    with torch.no_grad():
        return model(torch.tensor(Xte, device="cuda")).squeeze(1).cpu().numpy()

tr = df[df["split"] == "train"].reset_index(drop=True)
te = df[df["split"] == "test"].reset_index(drop=True)

Xtr_o, Xte_o = onehot(tr["trigger"].tolist()), onehot(te["trigger"].tolist())
Xtr_s = np.hstack([Xtr_o, tr[STRUCT].values.astype(np.float32)])
Xte_s = np.hstack([Xte_o, te[STRUCT].values.astype(np.float32)])
ytr = tr["ON_OFF"].values

variants = {
    "seq_only (B2_mlp)": (Xtr_o, Xte_o, 15),
    "seq+structure (B4)": (Xtr_s, Xte_s, 15),
    "seq+structure+epochs (B5 target-aware)": (Xtr_s, Xte_s, 25),
}
e4 = {}
for name, (Xtr, Xte, ep) in variants.items():
    s = fit_eval(Xtr, ytr, Xte, ep)
    rho = stats.spearmanr(s, te["ON_OFF"].values).correlation
    te2 = te.copy(); te2["score"] = s
    s1 = [success_at_k(g.sort_values("score", ascending=False)["record_id"].tolist(),
                        dict(zip(g["record_id"], g["success"].astype(bool))), 1)
          for _, g in te2.groupby("target_id")]
    e4[name] = {"rho": round(float(rho), 4), "success_at_1": round(float(np.mean(s1)), 4)}
    print(f"  {name:32s} rho={rho:.3f} s@1={np.mean(s1):.3f}")

json.dump(e4, open(OUT, "w"), indent=2)
print("wrote", OUT)