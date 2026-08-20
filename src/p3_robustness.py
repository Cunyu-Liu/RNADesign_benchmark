"""P3 robustness: multi-seed (5 seeds) + virus/TF group-stratified design utility.
Per-target metrics averaged over deep seeds, then mean +/- 95% CI across targets.
"""
import json, sys
import numpy as np
import pandas as pd
import torch

sys.path.insert(0, "/home/cunyuliu/ToeholdDesignBench/src")
from metrics.metrics import success_at_k, ndcg_at_k, normalized_regret

CANON = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_records.parquet"
SPLIT = "/mnt/cunyuliu/ToeholdDesignBench/processed/split_manifests.csv"
OUT = "/mnt/cunyuliu/ToeholdDesignBench/processed/p3_robustness_multiseed.json"
SEEDS = [0, 1, 2, 3, 4]

df = pd.read_parquet(CANON)
df = df[df["admission_status"] == "admitted_paired"].copy()
df = df[df["ON_OFF"].notna()].reset_index(drop=True)
sp = pd.read_csv(SPLIT)
df = df.merge(sp, on="target_id", how="left")
df["success"] = ((df["ON"] >= 0.5) & (df["OFF"] <= 0.5)).astype(int)
df["group"] = np.where(df["target_id"].astype(str).str.startswith("human_"), "TF", "virus")

tr = df[df["split"] == "train"].reset_index(drop=True)
te = df[df["split"] == "test"].reset_index(drop=True)
te = te.reset_index(drop=True)
print("test targets:", len(te["target_id"].unique()), "records:", len(te))


def onehot(seqs, max_len=30):
    mp = {"A": 0, "C": 1, "G": 2, "T": 3, "U": 3, "N": 0}
    X = np.zeros((len(seqs), max_len, 4))
    for i, s in enumerate(seqs):
        for j, ch in enumerate(str(s).upper()[:max_len]):
            X[i, j, mp.get(ch, 0)] = 1
    return X


def make_mlp():
    import torch
    return torch.nn.Sequential(torch.nn.Flatten(), torch.nn.Linear(120, 64), torch.nn.ReLU(),
                               torch.nn.Linear(64, 32), torch.nn.ReLU(), torch.nn.Linear(32, 1))

def make_cnn():
    import torch
    return torch.nn.Sequential(torch.nn.Conv1d(4, 32, 5), torch.nn.ReLU(), torch.nn.AdaptiveAvgPool1d(1),
                               torch.nn.Flatten(), torch.nn.Linear(32, 16), torch.nn.ReLU(), torch.nn.Linear(16, 1))

def make_deep1d():
    import torch
    return torch.nn.Sequential(torch.nn.Conv1d(4, 64, 5), torch.nn.ReLU(), torch.nn.Conv1d(64, 128, 3), torch.nn.ReLU(),
                               torch.nn.AdaptiveAvgPool1d(1), torch.nn.Flatten(), torch.nn.Linear(128, 64), torch.nn.ReLU(),
                               torch.nn.Linear(64, 1))


def train_deep(model_fn, Xtr, ytr, Xte, seed):
    torch.manual_seed(seed); torch.cuda.manual_seed_all(seed); np.random.seed(seed)
    m = model_fn()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    m = m.to(dev); opt = torch.optim.Adam(m.parameters(), lr=1e-3)
    Xt = torch.tensor(Xtr, dtype=torch.float32).to(dev); yt = torch.tensor(ytr, dtype=torch.float32).to(dev)
    for _ in range(15):
        m.train(); opt.zero_grad()
        loss = torch.mean((m(Xt).squeeze(-1) - yt) ** 2); loss.backward(); opt.step()
    m.eval()
    with torch.no_grad():
        return m(torch.tensor(Xte, dtype=torch.float32).to(dev)).squeeze(-1).cpu().numpy()


Xtr_o = onehot(tr["trigger"]); Xte_o = onehot(te["trigger"])
ytr = tr["ON_OFF"].values

Xtr_mlp = Xtr_o.reshape(len(Xtr_o), -1); Xte_mlp = Xte_o.reshape(len(Xte_o), -1)
Xtr_c = Xtr_o.reshape(len(Xtr_o), 4, 30); Xte_c = Xte_o.reshape(len(Xte_o), 4, 30)

# deep seed scores for full test (aligned to te row order 0..N-1)
deep_seed = {}
for name, (fn, Xa, Xc) in {"B2_mlp": (make_mlp, Xtr_mlp, Xte_mlp),
                            "B2_cnn": (make_cnn, Xtr_c, Xte_c),
                            "B3_deep": (make_deep1d, Xtr_c, Xte_c)}.items():
    deep_seed[name] = [train_deep(fn, Xa, ytr, Xc, sd) for sd in SEEDS]


def eval_sub(g, scores):
    s1, s3, nd_, rg = [], [], [], []
    g = g.copy(); g["score"] = scores
    for _, gg in g.groupby("target_id"):
        s = gg.sort_values("score", ascending=False)["record_id"].tolist()
        succ = dict(zip(gg["record_id"], gg["success"].astype(bool)))
        rel = dict(zip(gg["record_id"], gg["ON_OFF"]))
        s1.append(success_at_k(s, succ, 1)); s3.append(success_at_k(s, succ, 3))
        nd_.append(ndcg_at_k(s, rel, 10))
        rg.append(normalized_regret(s, rel, 10))
    return {k: np.array(v) for k, v in {"s1": s1, "s3": s3, "ndcg": nd_, "regret": rg}.items()}


def summarize(sig):
    def ci(a):
        a = np.asarray(a, float)
        m = float(a.mean())
        lo, hi = (float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))) if len(a) > 1 else (m, m)
        return {"mean": round(m, 4), "ci95": [round(lo, 4), round(hi, 4)], "n": int(len(a))}
    return {k: ci(v) for k, v in sig.items()}


det_scores = {
    "B0_random": np.random.RandomState(0).random(len(te)),
    "B0_gc": te["gc_trigger"].values.astype(float),
    "B1_thermo": te["salis_onoff"].replace(0.0, np.nan).fillna(te["mfe_switch_off"]).fillna(0).values.astype(float),
}

res = {"by_group": {}}
for gname in ["all", "virus", "TF"]:
    mask = (te["group"] == gname) if gname != "all" else np.ones(len(te), bool)
    g = te[mask].reset_index(drop=True)
    pos = g.index.values  # positions into g (g reindexed). Map g[position] -> te[boolmask original]
    # We need scores aligned to g. det_scores are aligned to te. g row i corresponds to original te row = np.where(mask)[0][i]
    orig_pos = np.where(mask)[0]
    out = {}
    for name, sc in det_scores.items():
        out[name] = summarize(eval_sub(g, sc[orig_pos]))
    for name, seeds in deep_seed.items():
        tgt = {}
        for s in seeds:
            e = eval_sub(g, s[orig_pos])
            for k, v in e.items():
                tgt.setdefault(k, []).append(v)
        avg_per_target = {k: np.mean(np.vstack(v), axis=0) for k, v in tgt.items()}
        out[name] = summarize(avg_per_target)
    res["by_group"][gname] = out

json.dump(res, open(OUT, "w"), indent=2)
print("wrote", OUT)
for g in res["by_group"]:
    print("\n== group:", g)
    for name, m in res["by_group"][g].items():
        print(f"  {name:11s} s1={m['s1']['mean']}({m['s1']['ci95']}) s3={m['s3']['mean']} ndcg={m['ndcg']['mean']} regret={m['regret']['mean']}")