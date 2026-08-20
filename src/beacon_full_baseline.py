"""BEACON full-set (91,534 sequence-mapped) sequence-level prediction baseline.
Demonstrates a REPRODUCIBLE >=70k sequence-mapped experiment on the PRS task.
Predicts ON from the 148-nt switch sequence (features: mononuc + GC + simple dinuc).
Train 73,227 / val 9,153 / test 9,154 (BEACON official split).
"""
import csv
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import r2_score, mean_absolute_error
from scipy.stats import spearmanr

BASE = "/mnt/cunyuliu/ToeholdDesignBench/external/beacon_prs"

def load(split):
    X, y = [], []
    with open(f"{BASE}/{split}.csv") as fh:
        r = csv.reader(fh); next(r)
        for row in r:
            if len(row) < 4:
                continue
            s = row[0].upper().replace("U", "T")
            y.append(float(row[1]))  # ON
            X.append(feats(s))
    return np.array(X), np.array(y)

def feats(s):
    # 4 mononuc counts + GC + 4 dinuc pair counts (compressed to 9 dims)
    n = len(s)
    mon = [s.count(b) / n for b in "ACGT"]
    gc = (s.count("G") + s.count("C")) / n
    dc = [s.count(p) / (n - 1) for p in ["GC", "CG", "AU", "UA"].replace("U", "T")]  # careful
    return mon + [gc] + dc

# fix dinuc (s is DNA T)
def feats2(s):
    n = len(s)
    mon = [s.count(b) / n for b in "ACGT"]
    gc = (s.count("G") + s.count("C")) / n
    dc = [s.count(p) / (n - 1) for p in ["GC", "CG", "TA", "AT"]]
    return mon + [gc] + dc

def load2(split):
    X, y = [], []
    with open(f"{BASE}/{split}.csv") as fh:
        r = csv.reader(fh); next(r)
        for row in r:
            if len(row) < 4:
                continue
            s = row[0].upper().replace("U", "T")
            y.append(float(row[1]))
            X.append(feats2(s))
    return np.array(X), np.array(y)

Xtr, ytr = load2("train")
Xva, yva = load2("val")
Xte, yte = load2("test")
print(f"train {len(ytr)} / val {len(yva)} / test {len(yte)}  total {len(ytr)+len(yva)+len(yte)}")

md = GradientBoostingRegressor(n_estimators=300, max_depth=4, random_state=0)
md.fit(Xtr, ytr)
for name, X, y in [("train", Xtr, ytr), ("val", Xva, yva), ("test", Xte, yte)]:
    p = md.predict(X)
    print(f"{name:6s}: R2={r2_score(y, p):.4f} MAE={mean_absolute_error(y, p):.4f} spearman={spearmanr(y, p)[0]:.4f}")

# also always-on baseline: predict global mean
glob = np.full(len(yte), ytr.mean())
print(f"baseline(mean): test R2={r2_score(yte, glob):.4f}")

import json
res = {
    "dataset": "BEACON ProgrammableRNASwitches (91,534 sequence-mapped, HF mirror)",
    "features": "4 mononuc + GC + 4 dinuc",
    "model": "GBDT(300, depth4, seed0)",
    "train": len(ytr), "val": len(yva), "test": len(yte), "total": len(ytr)+len(yva)+len(yte),
    "test_R2": r2_score(yte, md.predict(Xte)),
    "test_MAE": mean_absolute_error(yte, md.predict(Xte)),
    "test_spearman": spearmanr(yte, md.predict(Xte))[0],
    "mean_baseline_test_R2": r2_score(yte, glob),
}
json.dump(res, open("/mnt/cunyuliu/ToeholdDesignBench/processed/p1_fullset_beacon91k.json", "w"), indent=2)
print("\nsaved p1_fullset_beacon91k.json")
print(json.dumps(res, indent=1))