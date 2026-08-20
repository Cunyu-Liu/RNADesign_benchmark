"""R5 final: complete honest diagnosis of MLP vs thermo prediction.
Adds per-feature rho (salis_onoff, mfe_off, mfe_on, gc, mlp single vs 5-seed) so we can
state precisely WHICH protocol makes thermo look better, and what the MLP actually learns.
"""
import numpy as np, pandas as pd, json
from scipy.stats import spearmanr
import torch

CANON = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_records.parquet"
SPLIT = "/mnt/cunyuliu/ToeholdDesignBench/processed/split_manifests.csv"
OUT = "/mnt/cunyuliu/ToeholdDesignBench/processed/a1_dl_vs_thermo_diag.json"

df = pd.read_parquet(CANON)
df = df[df["admission_status"]=="admitted_paired"].copy()
df = df[df["ON_OFF"].notna()].reset_index(drop=True)
df = df.merge(pd.read_csv(SPLIT), on="target_id", how="left")
tr = df[df["split"]=="train"].reset_index(drop=True)
te = df[df["split"]=="test"].reset_index(drop=True)
for c in ["salis_onoff","mfe_switch_off","mfe_switch_on","mfe_trigger","gc_trigger"]:
    te[c] = pd.to_numeric(te[c], errors="coerce").fillna(0.0)
y = te["ON_OFF"].values

def rho(a,b):
    a=np.asarray(a,float); b=np.asarray(b,float); ok=np.isfinite(a)&np.isfinite(b)
    if ok.sum()<3 or np.all(a[ok]==a[ok][0]) or np.all(b[ok]==b[ok][0]): return float("nan")
    return float(spearmanr(a[ok],b[ok])[0])

def onehot(seqs,L=30):
    mp={"A":0,"C":1,"G":2,"T":3,"U":3,"N":0}
    X=np.zeros((len(seqs),L,4))
    for i,s in enumerate(seqs):
        for j,ch in enumerate(str(s).upper()[:L]): X[i,j,mp.get(ch,0)]=1
    return X

def train_mlp(Xtr,ytr,Xte,seed=0,epochs=15):
    torch.manual_seed(seed); torch.cuda.manual_seed_all(seed); np.random.seed(seed)
    m=torch.nn.Sequential(torch.nn.Flatten(),torch.nn.Linear(120,64),torch.nn.ReLU(),
                          torch.nn.Linear(64,32),torch.nn.ReLU(),torch.nn.Linear(32,1))
    dev="cuda" if torch.cuda.is_available() else "cpu"; m=m.to(dev)
    opt=torch.optim.Adam(m.parameters(),lr=1e-3)
    Xt=torch.tensor(Xtr,dtype=torch.float32).to(dev); yt=torch.tensor(ytr,dtype=torch.float32).to(dev)
    for _ in range(epochs):
        m.train(); opt.zero_grad(); loss=torch.mean((m(Xt).squeeze(-1)-yt)**2); loss.backward(); opt.step()
    m.eval()
    with torch.no_grad(): return m(torch.tensor(Xte,dtype=torch.float32).to(dev)).squeeze(-1).cpu().numpy()

Xo=onehot(tr["trigger"]); ytr=tr["ON_OFF"].values; Xte_o=onehot(te["trigger"]).reshape(len(te),-1)
Xr=Xo.reshape(len(Xo),-1)
mlp15=train_mlp(Xr,ytr,Xte_o,0,15)
mlp20=[train_mlp(Xr,ytr,Xte_o,s,20) for s in range(5)]
mlp20_avg=np.mean(mlp20,axis=0)

feats = {
    "salis_onoff (RBS-calc)": pd.to_numeric(te["salis_onoff"],errors="coerce").fillna(0.0).values,
    "mfe_switch_off": te["mfe_switch_off"].values,
    "mfe_switch_on": te["mfe_switch_on"].values,
    "gc_trigger": te["gc_trigger"].values,
}
res = {"test_rows": int(len(te)), "test_targets": int(te["target_id"].nunique())}
res["pooled_pred_rho"] = {k: round(rho(v,y),4) for k,v in feats.items()}
res["pooled_pred_rho"].update({
    "thermo_composite (salis|mfe)": round(rho(np.where(te["salis_onoff"].values!=0, te["salis_onoff"].values,
        np.where(te["mfe_switch_off"].values!=0, te["mfe_switch_off"].values, 0.0)), y),4),
    "mlp 15ep seed0 (paper protocol)": round(rho(mlp15,y),4),
    "mlp 20ep 5seed avg": round(rho(mlp20_avg,y),4),
})
# MLP learns what? corr with features
res["mlp20avg_corr_with"] = {k: round(float(np.corrcoef(mlp20_avg, v)[0,1]),4) for k,v in feats.items()}
# overfit check: train rho for mlp20 avg
pred_tr = np.mean([train_mlp(Xr,ytr,Xr,s,20) for s in range(5)],axis=0)
res["mlp20avg_train_rho"] = round(rho(pred_tr, ytr),4)
res["mlp20avg_test_rho"] = round(rho(mlp20_avg,y),4)

json.dump(res, open(OUT,"w"), indent=2)
print(json.dumps(res, indent=2))
print("wrote", OUT)