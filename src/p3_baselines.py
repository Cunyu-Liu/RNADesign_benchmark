"""P3: reproduce 6 core baseline families under a unified interface (R1 ranking).

Baselines (contract 8.1): B0 random/rule, B1 traditional thermo, B2 Angenent-Mari
MLP/CNN, B3 STORM/NuSpeak-like deep predictor, B4 SANDSTORM-like seq+structure,
B5 VISTA-like target-aware (structure-rich). Fixed seeds; source-disjoint split;
design-utility metrics (success@K/NDCG/regret) with target bootstrap.
"""
import json
import sys

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, "/home/cunyuliu/ToeholdDesignBench/src")
from metrics.metrics import success_at_k, ndcg_at_k, normalized_regret, mean_with_ci  # noqa: E402

CANON = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_records.parquet"
SPLIT = "/mnt/cunyuliu/ToeholdDesignBench/processed/split_manifests.csv"
OUT = "/mnt/cunyuliu/ToeholdDesignBench/processed/p3_baselines.json"

SEED = 0
np.random.seed(SEED)
# FIX-1: seed torch BEFORE any model construction (reproducibility)
torch.manual_seed(SEED)
torch.cuda.manual_seed_all(SEED)

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

def onehot(seqs, L=30, n=4):
    m = {"A": 0, "C": 1, "G": 2, "T": 3}
    X = np.zeros((len(seqs), L * n), dtype=np.float32)
    for i, s in enumerate(seqs):
        for j, ch in enumerate(str(s)[:L]):
            if ch in m:
                X[i, j * n + m[ch]] = 1.0
    return X

def struct_mat(d):
    return d[STRUCT_COLS].values.astype(np.float32)


# ---------------- deep models (torch, GPU) ----------------
def _train(model, Xtr, ytr, epochs, lr=1e-3):
    import torch
    torch.manual_seed(SEED)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    Xt = torch.tensor(Xtr, device=device)
    yt = torch.log1p(torch.tensor(ytr, dtype=torch.float32, device=device).clamp(min=0)).unsqueeze(1)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    lossf = torch.nn.MSELoss()
    model.train()
    for _ in range(epochs):
        opt.zero_grad(); loss = lossf(model(Xt), yt); loss.backward(); opt.step()
    model.eval()
    return model, device

def _predict(model, device, Xte):
    import torch
    with torch.no_grad():
        return model(torch.tensor(Xte, device=device)).squeeze(1).cpu().numpy()


def make_mlp(in_dim):
    import torch
    return torch.nn.Sequential(torch.nn.Linear(in_dim, 64), torch.nn.ReLU(),
                               torch.nn.Linear(64, 32), torch.nn.ReLU(), torch.nn.Linear(32, 1))

def make_cnn():
    import torch
    return torch.nn.Sequential(
        torch.nn.Conv1d(4, 64, 5), torch.nn.ReLU(), torch.nn.AdaptiveAvgPool1d(1),
        torch.nn.Flatten(), torch.nn.Linear(64, 32), torch.nn.ReLU(), torch.nn.Linear(32, 1))

def make_storm():
    import torch
    return torch.nn.Sequential(
        torch.nn.Conv1d(4, 64, 5), torch.nn.ReLU(), torch.nn.Conv1d(64, 128, 3), torch.nn.ReLU(),
        torch.nn.AdaptiveAvgPool1d(1), torch.nn.Flatten(), torch.nn.Linear(128, 64), torch.nn.ReLU(),
        torch.nn.Linear(64, 1))


# ---------------- baseline scorer (fit on train, score test) ----------------
def scorer(name, tr, te):
    if name == "B0_random":
        rng = np.random.default_rng(SEED)
        return rng.random(len(te))
    if name == "B0_gc":
        return te["gc_trigger"].values
    if name == "B1_thermo":
        s = te["salis_onoff"].copy()
        s = s.replace(0.0, np.nan).fillna(te["mfe_switch_off"])
        return s.fillna(0).values
    # deep baselines (fit on train)
    Xtr_o, Xte_o = onehot(tr["trigger"].tolist()), onehot(te["trigger"].tolist())
    ytr = tr["ON_OFF"].values
    if name == "B2_mlp":
        m, dev = _train(make_mlp(120), Xtr_o, ytr, epochs=15)
        return _predict(m, dev, Xte_o)
    if name == "B2_cnn":
        Xtr_c = Xtr_o.reshape(len(Xtr_o), 4, 30); Xte_c = Xte_o.reshape(len(Xte_o), 4, 30)
        m, dev = _train(make_cnn(), Xtr_c, ytr, epochs=15)
        return _predict(m, dev, Xte_c)
    if name == "B3_storm":
        Xtr_c = Xtr_o.reshape(len(Xtr_o), 4, 30); Xte_c = Xte_o.reshape(len(Xte_o), 4, 30)
        m, dev = _train(make_storm(), Xtr_c, ytr, epochs=15)
        return _predict(m, dev, Xte_c)
    if name == "B4_struct":
        Xtr = np.hstack([Xtr_o, struct_mat(tr)]); Xte = np.hstack([Xte_o, struct_mat(te)])
        m, dev = _train(make_mlp(125), Xtr, ytr, epochs=15)
        return _predict(m, dev, Xte)
    if name == "B5_targetaware":
        Xtr = np.hstack([Xtr_o, struct_mat(tr)]); Xte = np.hstack([Xte_o, struct_mat(te)])
        m, dev = _train(make_mlp(125), Xtr, ytr, epochs=20)
        return _predict(m, dev, Xte)
    raise ValueError(name)


BASELINES = ["B0_random", "B0_gc", "B1_thermo", "B2_mlp", "B2_cnn", "B3_storm", "B4_struct", "B5_targetaware"]

tr = df[df["split"] == "train"].reset_index(drop=True)
te = df[df["split"] == "test"].reset_index(drop=True)
print(f"train records {len(tr)}, test records {len(te)}, test targets {te.target_id.nunique()}")

report = {}
for name in BASELINES:
    try:
        scores = scorer(name, tr, te)
    except Exception as e:
        report[name] = {"error": str(e)}
        print(f"{name}: ERROR {e}")
        continue
    te2 = te.copy()
    te2["score"] = np.asarray(scores, dtype=float)
    s1, s3, ndcg, regret = [], [], [], []
    for tid, g in te2.groupby("target_id"):
        g = g.sort_values("score", ascending=False)
        ranked = g["record_id"].tolist()
        succ = dict(zip(g["record_id"], g["success"].astype(bool)))
        rel = dict(zip(g["record_id"], g["ON_OFF"]))
        s1.append(success_at_k(ranked, succ, 1))
        s3.append(success_at_k(ranked, succ, 3))
        ndcg.append(ndcg_at_k(ranked, rel, 10))
        regret.append(normalized_regret(ranked, rel, 10))
    r = {}
    for k, vals in [("s1", s1), ("s3", s3), ("ndcg", ndcg), ("regret", regret)]:
        m, lo, hi = mean_with_ci(vals, rng=np.random.default_rng(SEED))
        r[k] = {"mean": round(m, 4), "ci": [round(lo, 4), round(hi, 4)]}
    report[name] = r
    print(f"{name:16s} s@1={r['s1']['mean']:.3f} s@3={r['s3']['mean']:.3f} ndcg@10={r['ndcg']['mean']:.3f} regret={r['regret']['mean']:.3f}")

json.dump(report, open(OUT, "w"), indent=2)
print("wrote", OUT)