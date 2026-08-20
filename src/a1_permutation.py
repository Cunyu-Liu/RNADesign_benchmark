"""R2 (reviewer): permutation test to strengthen the n=23 virus-group ranking signal.

Null hypothesis: within a target, the predictor's score is UNRELATED to ON_OFF. We destroy
only the score<->label pairing by independently permuting ON_OFF within each target
(preserves target sizes + label distributions), recompute per-target Spearman rho and the
mean, and compare the observed mean to the null distribution.

Reported for: n=23 authoritative virus (primary) and n=6 canonical virus (control), for
mlp_avg (main), plus random and gc as sanity controls. One-sided p = (#null >= obs + 1)/(B+1).
"""
import numpy as np
import pandas as pd
import json
from scipy.stats import spearmanr
import torch

AUTH = "/mnt/cunyuliu/ToeholdDesignBench/external/beacon_prs/beacon_authoritative_mapping.csv"
CANON = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_records.parquet"
SPLIT = "/mnt/cunyuliu/ToeholdDesignBench/processed/split_manifests.csv"
OUT = "/mnt/cunyuliu/ToeholdDesignBench/processed/a1_permutation_n23_n6.json"
B = 5000
SEED = 0


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


def per_target_rho(grouped, score_col, label_col="ON_OFF"):
    out = {}
    for tid, g in grouped:
        if len(g) < 3 or np.unique(g[label_col]).size < 2:
            continue
        out[tid] = spearmanr(g[score_col], g[label_col])[0]
    return np.array(list(out.values()))


def permutation_test(grouped, score_col, label_col="ON_OFF", B=5000, seed=0):
    """Observed mean per-target rho + one-sided permutation p-value."""
    rng = np.random.default_rng(seed)
    obs = per_target_rho(grouped, score_col, label_col)
    obs_mean = obs.mean()
    # null: permute labels within each target
    ge = [(tid, g[score_col].to_numpy(), g[label_col].to_numpy()) for tid, g in grouped
          if len(g) >= 3 and np.unique(g[label_col]).size >= 2]
    cnt = 0
    for _ in range(B):
        mean = 0.0
        for tid, sc, lab in ge:
            mean += spearmanr(sc, rng.permutation(lab))[0]
        mean /= len(ge)
        if mean >= obs_mean:
            cnt += 1
    p = (cnt + 1) / (B + 1)
    return {"n_targets": int(len(obs)),
            "mean_rho": round(float(obs_mean), 4),
            "p_perm_one_sided": round(float(p), 6),
            "n_permutations": int(B)}


# ============ n=23 authoritative virus ============
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
ytrb = trb["ON_OFF"].values.astype(float)
mlps_b = [train_mlp(Xtrb, ytrb, Xteb, s) for s in (0,1,2)]
teb["mlp_sc"] = np.mean(mlps_b, axis=0)
grp_b = list(teb.groupby("target"))

n23 = {"n_test_rows": int(len(teb)), "targets": sorted(teb["target"].unique())}
for name, sc in [("random","random_sc"),("gc","gc_sc"),("mlp_avg","mlp_sc")]:
    n23[name] = permutation_test(grp_b, sc, B=B, seed=SEED)

# ============ n=6 canonical virus (control) ============
canon = pd.read_parquet(CANON)
canon = canon[canon["admission_status"]=="admitted_paired"].copy()
canon = canon[canon["ON_OFF"].notna()]
spm = pd.read_csv(SPLIT)
canon = canon.merge(spm, on="target_id", how="left")
trc = canon[canon["split"]=="train"].copy()
tec = canon[canon["split"]=="test"].copy()
tec = tec[~tec["target_id"].astype(str).str.startswith("human_")].copy()
tec["target"] = tec["target_id"]
tec["ON_OFF"] = pd.to_numeric(tec["ON_OFF"], errors="coerce")
tec = tec.dropna(subset=["ON_OFF"]).reset_index(drop=True)
tec["random_sc"] = np.random.RandomState(0).random(len(tec))
tec["gc_sc"] = pd.to_numeric(tec["gc_trigger"], errors="coerce").fillna(0.0)
Xtrc = onehot(trc["trigger"].astype(str)).reshape(len(trc),-1)
Xtec = onehot(tec["trigger"].astype(str)).reshape(len(tec),-1)
ytrc = pd.to_numeric(trc["ON_OFF"], errors="coerce").values
mlps_c = [train_mlp(Xtrc, ytrc, Xtec, s) for s in (0,1,2)]
tec["mlp_sc"] = np.mean(mlps_c, axis=0)
grp_c = list(tec.groupby("target"))

n6 = {"n_test_rows": int(len(tec)), "targets": sorted(tec["target"].unique())}
for name, sc in [("random","random_sc"),("gc","gc_sc"),("mlp_avg","mlp_sc")]:
    n6[name] = permutation_test(grp_c, sc, B=B, seed=SEED)

out = {"n23_authoritative": n23, "n6_canonical": n6,
       "method": "within-target ON_OFF permutation, one-sided p = (#null>=obs +1)/(B+1)",
       "permutations": B}
json.dump(out, open(OUT, "w"), indent=2)
print(json.dumps(out, indent=2))
print("wrote", OUT)