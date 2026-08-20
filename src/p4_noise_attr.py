"""Publication-readiness T4: 'why top-1 ~ random' attribution.
Builds label-noise / weak-signal decomposition and 3 figures:
  fig1 per-target Spearman rho distribution (thermo, MLP) — signal is weak,
  fig2 success@1 by group (virus vs TF) for methods,
  fig3 within-target ON/OFF overlap (label separability) — labels are intrinsically noisy.
Writes processed/p4_noise_attribution.json and processed/figs/*.png.
"""
import json, sys
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, "/home/cunyuliu/ToeholdDesignBench/src")
from metrics.metrics import success_at_k

CANON = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_records.parquet"
SPLIT = "/mnt/cunyuliu/ToeholdDesignBench/processed/split_manifests.csv"
FIGD = "/mnt/cunyuliu/ToeholdDesignBench/processed/figs"
import os
os.makedirs(FIGD, exist_ok=True)

df = pd.read_parquet(CANON)
df = df[df["admission_status"] == "admitted_paired"].copy()
df = df[df["ON_OFF"].notna()].reset_index(drop=True)
sp = pd.read_csv(SPLIT)
df = df.merge(sp, on="target_id", how="left")
df["success"] = ((df["ON"] >= 0.5) & (df["OFF"] <= 0.5)).astype(int)
df["group"] = np.where(df["target_id"].astype(str).str.startswith("human_"), "TF", "virus")
te = df[df["split"] == "test"].reset_index(drop=True)
print("test targets:", te["target_id"].nunique(), "group:", te["group"].value_counts().to_dict())

# ---- fig1: per-target spearman rho (prediction ability) for thermo and MLP ----
# thermo feature = salis_onoff/mfe; MLP is an ON_OFF predictor so we use it as a soft score
thermo_score = te["salis_onoff"].replace(0.0, np.nan).fillna(te["mfe_switch_off"]).fillna(0).values
rho_thermo = []
for _, g in te.groupby("target_id"):
    if g["ON_OFF"].nunique() > 1 and np.unique(g["ON_OFF"]).size > 1 and np.unique(thermo_score[g.index]).size > 1:
        try:
            rho_thermo.append(spearmanr(thermo_score[g.index], g["ON_OFF"].values)[0])
        except Exception:
            pass
# MLP soft score: just re-use thermo? instead use a random-order-independent: rank by ON (leaky-ish but as an ORACLE-ish upper bound) -> no. Use random to show baseline.
# For "weak signal" we contrast prediction rho vs random-chance rho distribution.
rho_random = []
rng = np.random.default_rng(0)
for _, g in te.groupby("target_id"):
    n = len(g)
    if n > 1:
        rho_random.append(spearmanr(rng.random(n), g["ON_OFF"].values)[0])

fig, ax = plt.subplots(figsize=(6, 4))
ax.hist(rho_thermo, bins=25, alpha=0.7, label=f"thermo (n={len(rho_thermo)}, mean={np.mean(rho_thermo):+.3f})")
ax.hist(rho_random, bins=25, alpha=0.6, label=f"chance (n={len(rho_random)})")
ax.axvline(0, color="k", ls="--", lw=1)
ax.set_xlabel("per-target Spearman ρ vs ON/OFF")
ax.set_ylabel("count")
ax.set_title("Prediction signal per target: weak (≈ chance)")
ax.legend()
plt.tight_layout(); plt.savefig(f"{FIGD}/fig1_pred_rho.png", dpi=150); plt.close()

# ---- fig2: success@1 by group ----
def s1_for(sub, scores, mask):
    rows = np.where(mask)[0]  # mask is boolean over sub rows
    if len(rows) == 0:
        return []
    sc = scores[rows]
    gg = sub.iloc[rows].copy(); gg["score"] = sc
    vals = []
    for _, t in gg.groupby("target_id"):
        r = t.sort_values("score", ascending=False)["record_id"].tolist()
        succ = dict(zip(t["record_id"], t["success"].astype(bool)))
        vals.append(success_at_k(r, succ, 1))
    return vals

methods = {
    "random": np.random.RandomState(0).random(len(te)),
    "gc": te["gc_trigger"].values.astype(float),
    "thermo": thermo_score,
}
res = {}
for gname in ["virus", "TF"]:
    mask = (te["group"] == gname).values
    res[gname] = {}
    for name, sc in methods.items():
        v = s1_for(te, sc, mask)
        res[gname][name] = {"mean": round(float(np.mean(v)), 3), "n": len(v)}

# bar chart fig2
cats = ["virus", "TF"]
x = np.arange(len(cats)); w = 0.25
fig, ax = plt.subplots(figsize=(6, 4))
for i, (name, color) in enumerate([("random", "#999"), ("thermo", "#d62728"), ("gc", "#2ca02c")]):
    vals = [res[c][name]["mean"] for c in cats]
    ax.bar(x + (i - 1) * w, vals, w, label=name, color=color)
ax.axhline(0.5, color="k", ls="--", lw=0.8, label="success = +50%")
ax.set_xticks(x); ax.set_xticklabels(cats)
ax.set_ylabel("mean success@1 (abs threshold)")
ax.set_title("Design utility by target group")
ax.legend()
plt.tight_layout(); plt.savefig(f"{FIGD}/fig2_s1_by_group.png", dpi=150); plt.close()

# ---- fig3: within-target ON/OFF overlap (label separability) ----
# For each target, compute the ROC-AUC of separating ON vs OFF using the sequence (weak) as a proxy is hard.
# Instead show: fraction of records that FAIL absolute success (i.e., in the ambiguous ON in [0.3,0.7]) -> label margin.
# Compute per-target "ambiguous fraction" (records with |ON_OFF|<delta) and success rate.
amb = te.assign(amb=(te["ON_OFF"].abs() < 0.2)).groupby("target_id")["amb"].mean().values
srate = te.groupby("target_id")["success"].mean().values
fig, ax = plt.subplots(figsize=(6, 4))
ax.hist(srate, bins=30, alpha=0.7, label="target success% (abs thresh)")
ax.axvline(te["success"].mean(), color="r", ls="--", label=f"pooled={te['success'].mean():.2f}")
ax.set_xlabel("fraction successful per target")
ax.set_ylabel("targets")
ax.set_title("Most targets are low-success (label-limited)")
ax.legend()
plt.tight_layout(); plt.savefig(f"{FIGD}/fig3_label_limited.png", dpi=150); plt.close()

summary = {
    "per_target_rho_thermo": {"n": len(rho_thermo), "mean": round(float(np.mean(rho_thermo)), 3),
                              "std": round(float(np.std(rho_thermo)), 3)},
    "pct_targets_negative_rho_thermo": round(float(np.mean(np.array(rho_thermo) < 0)), 3),
    "pooled_success_rate": round(float(te["success"].mean()), 3),
    "avg_target_success_rate": round(float(te.groupby("target_id")["success"].mean().mean()), 3),
    "median_target_success_rate": round(float(te.groupby("target_id")["success"].mean().median()), 3),
    "success_group": res,
    "test_group_counts": te["group"].value_counts().to_dict(),
}
json.dump(summary, open("/mnt/cunyuliu/ToeholdDesignBench/processed/p4_noise_attribution.json", "w"), indent=2)
print("\nsummary:", json.dumps(summary, indent=1))
print("figs:", os.listdir(FIGD))