"""A1 cross-validation: authoritative (GSE149225) vs earlier trigger-based attribution.
For rows the trigger method attributed, do categories/targets agree? (independent check)
And re-run the scale-free virus-group robustness on the FULL authoritative virus set.
"""
import numpy as np, pandas as pd
from scipy.stats import spearmanr
import torch

AUTH = "/mnt/cunyuliu/ToeholdDesignBench/external/beacon_prs/beacon_authoritative_mapping.csv"
TRIG = pd.read_csv("/mnt/cunyuliu/ToeholdDesignBench/external/beacon_prs/beacon_target_mapping.csv", dtype=str)
au = pd.read_csv(AUTH, dtype=str)

# --- 1) consistency: join by sequence, compare category where trigger method had one
tr = TRIG[TRIG["category"].isin(["virus","TF"])].copy()
au2 = au[["sequence","source_sequence","category"]].rename(columns={"category":"au_cat","source_sequence":"au_src"})
m = tr.merge(au2, on="sequence", how="left", suffixes=("","_au"))
m = m.dropna(subset=["au_cat"])
agree = (m["category"] == m["au_cat"]).mean()
print(f"[consistency] trigger-attributed rows={len(m)}; category agreement={100*agree:.1f}%")
# for virus, check target-level
v = m[m["category"]=="virus"].dropna(subset=["au_src"])
print(f"  virus trigger rows w/ auth target: {len(v)}; exact target match={(v['target_id']==v['au_src']).mean()*100:.1f}%")

# --- 2) authoritative category counts
print("\n[authoritative] category counts:")
print(au["category"].value_counts().to_dict())
print("virus test targets:", au[(au.category=='virus')&(au.split=='test')]['source_sequence'].nunique(),
      "rows:", (au[(au.category=='virus')&(au.split=='test')].shape[0]))
print("attribution total:", (au['category']!='NA').sum(), "/", len(au))

# --- 3) virus robustness on authoritative full set, scale-free per-target spearman
vios = au[au.category=="virus"].copy()
for c in ["ON","OFF","ON_OFF"]:
    vios[c] = vios[c].astype(float)
tr_data = vios[vios.split=="train"].reset_index(drop=True)
te_data = vios[vios.split=="test"].reset_index(drop=True)

def onehot(seqs, L=30):
    mp={"A":0,"C":1,"G":2,"T":3,"U":3,"N":0}
    X=np.zeros((len(seqs),L,4))
    for i,s in enumerate(seqs):
        for j,ch in enumerate(str(s).upper()[:L]): X[i,j,mp.get(ch,0)]=1
    return X
def train(Xtr,ytr,Xte,seed):
    torch.manual_seed(seed); torch.cuda.manual_seed_all(seed); np.random.seed(seed)
    m=torch.nn.Sequential(torch.nn.Flatten(),torch.nn.Linear(120,64),torch.nn.ReLU(),
                          torch.nn.Linear(64,32),torch.nn.ReLU(),torch.nn.Linear(32,1))
    dev="cuda" if torch.cuda.is_available() else "cpu"; m=m.to(dev)
    opt=torch.optim.Adam(m.parameters(),lr=1e-3)
    Xt=torch.tensor(Xtr,dtype=torch.float32).to(dev); yt=torch.tensor(ytr,dtype=torch.float32).to(dev)
    for _ in range(20):
        m.train(); opt.zero_grad(); loss=torch.mean((m(Xt).squeeze(-1)-yt)**2); loss.backward(); opt.step()
    m.eval()
    with torch.no_grad(): return m(torch.tensor(Xte,dtype=torch.float32).to(dev)).squeeze(-1).cpu().numpy()

Xtr=onehot(tr_data["sequence"]).reshape(len(tr_data),-1)
Xte=onehot(te_data["sequence"]).reshape(len(te_data),-1)
ytr=tr_data["ON_OFF"].values
m0=train(Xtr,ytr,Xte,0); m1=train(Xtr,ytr,Xte,1); m2=train(Xtr,ytr,Xte,2)
scores={"random":np.random.RandomState(0).random(len(te_data)),
        "mlp_avg":np.mean([m0,m1,m2],axis=0)}
def per_target_rho(sc):
    out={}
    d=te_data.copy(); d["sc"]=sc
    for tid,g in d.groupby("source_sequence"):
        if len(g)<3 or np.unique(g["ON_OFF"]).size<2: continue
        out[tid]=spearmanr(g["sc"],g["ON_OFF"])[0]
    return out
for name,sc in scores.items():
    rho=np.array(list(per_target_rho(sc).values()))
    rng=np.random.default_rng(0); boots=[rho[rng.integers(0,len(rho),len(rho))].mean() for _ in range(1000)]
    print(f"[robust] {name}: n_targets={len(rho)} mean_rho={rho.mean():+.4f} CI=[{np.percentile(boots,2.5):+.4f},{np.percentile(boots,97.5):+.4f}] pct_pos={(rho>0).mean():.2f}")