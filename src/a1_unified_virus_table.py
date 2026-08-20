"""A1 unified virus-group comparison: n=6 (canonical, trigger-attributed) vs n=23
(authoritative GSE149225). Both evaluated on the SAME scale-free per-target Spearman
rho of predicted vs actual ON_OFF, so n=6 vs n=23 is an apples-to-apples ranking
comparison. Also reports design-utility (success@1/NDCG) for the n=6 canonical side.
Emits processed/a1_unified_virus_comparison.json + a figure (if matplotlib present).
"""
import json
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import torch

CANON = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_records.parquet"
SPLIT = "/mnt/cunyuliu/ToeholdDesignBench/processed/split_manifests.csv"
AUTH = "/mnt/cunyuliu/ToeholdDesignBench/external/beacon_prs/beacon_authoritative_mapping.csv"
N23 = "/mnt/cunyuliu/ToeholdDesignBench/processed/a1_virus_robustness_authoritative_n23.json"
OUT = "/mnt/cunyuliu/ToeholdDesignBench/processed/a1_unified_virus_comparison.json"
OUTFIG = "/mnt/cunyuliu/ToeholdDesignBench/processed/figs/fig_virus_n6_vs_n23_rho.png"

np.random.seed(0)
torch.manual_seed(0); torch.cuda.manual_seed_all(0)


def onehot(seqs, L=30):
    mp = {"A":0,"C":1,"G":2,"T":3,"U":3,"N":0}
    X = np.zeros((len(seqs), L, 4))
    for i, s in enumerate(seqs):
        for j, ch in enumerate(str(s).upper()[:L]):
            X[i, j, mp.get(ch,0)] = 1
    return X


def make_mlp():
    return torch.nn.Sequential(torch.nn.Flatten(), torch.nn.Linear(120,64), torch.nn.ReLU(),
                               torch.nn.Linear(64,32), torch.nn.ReLU(), torch.nn.Linear(32,1))


def train_mlp(Xtr, ytr, Xte, seed):
    torch.manual_seed(seed); torch.cuda.manual_seed_all(seed); np.random.seed(seed)
    m = make_mlp(); dev = "cuda" if torch.cuda.is_available() else "cpu"; m = m.to(dev)
    opt = torch.optim.Adam(m.parameters(), lr=1e-3)
    Xt = torch.tensor(Xtr, dtype=torch.float32).to(dev)
    yt = torch.tensor(ytr, dtype=torch.float32).to(dev)
    for _ in range(20):
        m.train(); opt.zero_grad()
        loss = torch.mean((m(Xt).squeeze(-1)-yt)**2); loss.backward(); opt.step()
    m.eval()
    with torch.no_grad():
        return m(torch.tensor(Xte, dtype=torch.float32).to(dev)).squeeze(-1).cpu().numpy()


def per_target_rho(df, score_col):
    out = {}
    for tid, g in df.groupby("target"):
        if len(g) < 3 or np.unique(g["ON_OFF"]).size < 2:
            continue
        out[tid] = spearmanr(g[score_col], g["ON_OFF"])[0]
    return out


def summarize(rhos):
    arr = np.array(list(rhos.values()))
    rng = np.random.default_rng(0)
    boots = [arr[rng.integers(0, len(arr), len(arr))].mean() for _ in range(1000)]
    return {"n_targets": int(len(arr)),
            "mean_rho": round(float(arr.mean()), 4),
            "ci95": [round(float(np.percentile(boots,2.5)),4), round(float(np.percentile(boots,97.5)),4)],
            "pct_positive": round(float((arr>0).mean()),4)}


# ---------------- n=6 canonical virus test ----------------
canon = pd.read_parquet(CANON)
canon = canon[canon["admission_status"]=="admitted_paired"].copy()
canon = canon[canon["ON_OFF"].notna()]
sp = pd.read_csv(SPLIT)
canon = canon.merge(sp, on="target_id", how="left")
te = canon[canon["split"]=="test"].copy()
te_v = te[~te["target_id"].astype(str).str.startswith("human_")].copy()
tr = canon[canon["split"]=="train"].copy()
te_v["target"] = te_v["target_id"]
te_v["ON_OFF"] = pd.to_numeric(te_v["ON_OFF"], errors="coerce")
te_v = te_v.dropna(subset=["ON_OFF"]).reset_index(drop=True)

# predictors on n=6
te_v["random_sc"] = np.random.RandomState(0).random(len(te_v))
te_v["gc_sc"] = te_v["gc_trigger"].astype(float)
te_v["thermo_sc"] = pd.to_numeric(te_v["salis_onoff"], errors="coerce").fillna(0.0)
Xtr = onehot(tr["trigger"].astype(str)).reshape(len(tr),-1)
Xte = onehot(te_v["trigger"].astype(str)).reshape(len(te_v),-1)
ytr = pd.to_numeric(tr["ON_OFF"], errors="coerce").values
mlps = [train_mlp(Xtr, ytr, Xte, s) for s in (0,1,2)]
te_v["mlp_sc"] = np.mean(mlps, axis=0)

n6 = {name: summarize(per_target_rho(te_v, sc))
      for name, sc in [("random","random_sc"),("gc","gc_sc"),("thermo","thermo_sc"),("mlp_avg","mlp_sc")]}
n6["n_test_rows"] = int(len(te_v))
n6["targets"] = sorted(te_v["target"].unique())
n6["design_success1"] = {name: None for name in []}

# design-utility success@1 on n=6 canonical (absolute threshold, as in P3)
te_v["success"] = ((pd.to_numeric(te_v["ON"], errors="coerce")>=0.5)&(pd.to_numeric(te_v["OFF"], errors="coerce")<=0.5)).astype(int)
def s1(df, score_col, K=1):
    hits=[]
    for tid,g in df.groupby("target"):
        if len(g)<K: continue
        g=g.sort_values(score_col,ascending=False)
        hits.append(g["success"].iloc[:K].max())
    return round(float(np.mean(hits)),3) if hits else None
n6["design_success1"] = {"random": s1(te_v,"random_sc"), "gc": s1(te_v,"gc_sc"),
                         "thermo": s1(te_v,"thermo_sc"), "mlp_avg": s1(te_v,"mlp_sc")}
print("=== n=6 canonical virus ===")
print(json.dumps(n6, indent=2, default=str))

# ---------------- n=23 authoritative virus ----------------
au = pd.read_csv(AUTH, dtype=str)
vios = au[au["category"]=="virus"].copy()
for c in ["ON","OFF","ON_OFF"]:
    vios[c] = pd.to_numeric(vios[c], errors="coerce")
vios["target"] = vios["source_sequence"]
trb = vios[vios["split"]=="train"].reset_index(drop=True)
teb = vios[vios["split"]=="test"].reset_index(drop=True)
teb["ON_OFF"] = teb["ON_OFF"].astype(float)
teb["random_sc"] = np.random.RandomState(0).random(len(teb))
teb["gc_sc"] = teb["sequence"].map(lambda s: (str(s).count("G")+str(s).count("C"))/len(str(s))).values
Xtrb = onehot(trb["sequence"]).reshape(len(trb),-1)
Xteb = onehot(teb["sequence"]).reshape(len(teb),-1)
mlps_b = [train_mlp(Xtrb, trb["ON_OFF"].values.astype(float), Xteb, s) for s in (0,1,2)]
teb["mlp_sc"] = np.mean(mlps_b, axis=0)
n23 = {name: summarize(per_target_rho(teb, sc))
       for name, sc in [("random","random_sc"),("gc","gc_sc"),("mlp_avg","mlp_sc")]}
n23["n_test_rows"] = int(len(teb))
n23["targets"] = sorted(teb["target"].unique())
print("=== n=23 authoritative virus ===")
print(json.dumps(n23, indent=2, default=str))

out = {"n6_canonical": n6, "n23_authoritative": n23,
       "method_note": "scale-free per-target Spearman rho(pred, ON_OFF); CI=95% bootstrap over targets"}
json.dump(out, open(OUT,"w"), indent=2, default=str)
print("wrote", OUT)

# ---------------- figure ----------------
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7,4))
    methods = ["random","gc","mlp_avg"]
    labels = {"random":"Random","gc":"GC content","mlp_avg":"MLP (3-seed avg)"}
    x = np.arange(len(methods)); w=0.35
    for j,(src, off) in enumerate([(n6, -w/2), (n23, w/2)]):
        means=[src[m]["mean_rho"] for m in methods]
        lo=[src[m]["ci95"][0] for m in methods]
        hi=[src[m]["ci95"][1] for m in methods]
        ax.errorbar(x+off, means, yerr=[np.array(means)-np.array(lo), np.array(hi)-np.array(means)],
                    fmt="o", capsize=4, label=("n=6 canonical" if j==0 else "n=23 authoritative"))
    ax.axhline(0, color="grey", ls="--", lw=0.8)
    ax.set_xticks(x); ax.set_xticklabels([labels[m] for m in methods])
    ax.set_ylabel("per-target Spearman rho (95% CI)")
    ax.set_title("Virus-group ranking signal: n=6 (canonical) vs n=23 (authoritative)")
    ax.legend(); ax.grid(alpha=0.3)
    import os
    os.makedirs(os.path.dirname(OUTFIG), exist_ok=True)
    fig.tight_layout(); fig.savefig(OUTFIG, dpi=150)
    print("wrote", OUTFIG)
except Exception as e:
    print("figure skipped:", e)