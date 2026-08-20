"""Emit authoritative A1 virus robustness json (n=23 virus targets, full GE0 map)."""
import numpy as np, pandas as pd, json
from scipy.stats import spearmanr
import torch

AUTH = "/mnt/cunyuliu/ToeholdDesignBench/external/beacon_prs/beacon_authoritative_mapping.csv"
OUT = "/mnt/cunyuliu/ToeholdDesignBench/processed/a1_virus_robustness_authoritative_n23.json"
au = pd.read_csv(AUTH, dtype=str)
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
mlp=[train(Xtr,ytr,Xte,s) for s in (0,1,2)]
scores={"random":np.random.RandomState(0).random(len(te_data)),
        "gc":te_data["sequence"].map(lambda s:(str(s).count("G")+str(s).count("C"))/len(str(s))).values,
        "mlp_avg":np.mean(mlp,axis=0)}
def per_target_rho(sc):
    out={}; d=te_data.copy(); d["sc"]=sc
    for tid,g in d.groupby("source_sequence"):
        if len(g)<3 or np.unique(g["ON_OFF"]).size<2: continue
        out[tid]=spearmanr(g["sc"],g["ON_OFF"])[0]
    return out
res={}
for name,sc in scores.items():
    rho=np.array(list(per_target_rho(sc).values()))
    rng=np.random.default_rng(0); boots=[rho[rng.integers(0,len(rho),len(rho))].mean() for _ in range(1000)]
    res[name]={"n_targets":int(len(rho)),"mean_rho":round(float(rho.mean()),4),
               "ci95":[round(float(np.percentile(boots,2.5)),4),round(float(np.percentile(boots,97.5)),4)],
               "pct_positive":round(float((rho>0).mean()),4)}
json.dump(res,open(OUT,"w"),indent=2)
print(OUT); print(json.dumps(res,indent=2))