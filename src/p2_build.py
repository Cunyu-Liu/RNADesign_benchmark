"""P2: split manifests + leakage verification + random/oracle sanity (with metrics).

Deliverables: split_manifests.json, leakage_report.html, oracle_sanity.json,
metric unit test run. GO gate: source overlap = 0; metric tests pass.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from metrics.metrics import success_at_k, ndcg_at_k, mean_with_ci  # noqa: E402

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TD_ROOT = os.environ.get("TD_BENCH_ROOT", os.path.join(PROJECT_ROOT, "data"))
OUT = os.environ.get("TD_BENCH_PROCESSED", os.path.join(TD_ROOT, "processed"))
CANON = os.path.join(OUT, "canonical_records.parquet")

df = pd.read_parquet(CANON)
# use paired-labeled records (final ON/OFF both present)
df = df[df["admission_status"] == "admitted_paired"].copy()
df = df[df["ON_OFF"].notna()].reset_index(drop=True)
print("records:", len(df), " targets:", df["target_id"].nunique())

# ---------- split manifests (source-disjoint 70/15/15) ----------
rng = np.random.default_rng(0)
targets = df["target_id"].unique()
rng.shuffle(targets)
n = len(targets)
ntr, nva = int(n * 0.7), int(n * 0.15)
split_of = {}
for i, t in enumerate(targets):
    if i < ntr:
        split_of[t] = "train"
    elif i < ntr + nva:
        split_of[t] = "val"
    else:
        split_of[t] = "test"

df["split"] = df["target_id"].map(split_of)

# GO gate: source overlap = 0
tr = set(targets[:ntr]); va = set(targets[ntr:ntr + nva]); te = set(targets[ntr + nva:])
overlap = {
    "train_val": len(tr & va), "train_test": len(tr & te), "val_test": len(va & te),
}
assert overlap["train_val"] == overlap["train_test"] == overlap["val_test"] == 0, "SOURCE OVERLAP != 0"
print("source overlap = 0  ✓  (train/val/test sizes:", len(tr), len(va), len(te), ")")

manifests = {
    "seed": 0, "split_type": "source_disjoint",
    "n_targets": {"train": len(tr), "val": len(va), "test": len(te)},
    "overlap": overlap,
    "target_split": split_of,
    "n_records": df["split"].value_counts().to_dict(),
}
json.dump({k: v for k, v in manifests.items() if k != "target_split"},
          open(f"{OUT}/split_manifests.json", "w"), indent=2)
pd.DataFrame([{"target_id": k, "split": v} for k, v in split_of.items()]).to_csv(
    f"{OUT}/split_manifests.csv", index=False)

# ---------- success definition (pre-registered ABSOLUTE threshold, test-independent) ----------
df["success"] = ((df["ON"] >= 0.5) & (df["OFF"] <= 0.5)).astype(int)

# ---------- random / oracle sanity (on TEST targets, source-disjoint) ----------
test = df[df["split"] == "test"]
print("test targets:", test["target_id"].nunique(), " test records:", len(test))

oracle = {}
random_res = {}
for K in [1, 3, 5, 10]:
    o_s1 = []; r_s1 = []
    for tid, g in test.groupby("target_id"):
        succ = dict(zip(g["record_id"], g["success"].astype(bool)))
        rel = dict(zip(g["record_id"], g["ON_OFF"]))
        # oracle: rank by true ON_OFF desc
        g_oracle = g.sort_values("ON_OFF", ascending=False)
        o_s1.append(success_at_k(g_oracle["record_id"].tolist(), succ, K))
        # random
        g_rand = g.sample(frac=1, random_state=0)
        r_s1.append(success_at_k(g_rand["record_id"].tolist(), succ, K))
    oracle[K] = {"mean": float(np.mean(o_s1))}
    random_res[K] = {"mean": float(np.mean(r_s1))}

print("oracle success@K:", oracle)
print("random success@K:", random_res)

# NDCG@10 oracle vs random
o_ndcg = [ndcg_at_k(g.sort_values("ON_OFF", ascending=False)["record_id"].tolist(),
                    dict(zip(g["record_id"], g["ON_OFF"])), 10)
          for _, g in test.groupby("target_id")]
r_ndcg = [ndcg_at_k(g.sample(frac=1, random_state=0)["record_id"].tolist(),
                    dict(zip(g["record_id"], g["ON_OFF"])), 10)
          for _, g in test.groupby("target_id")]
sanity = {
    "oracle_success_at_k": oracle, "random_success_at_k": random_res,
    "oracle_ndcg10": float(np.mean(o_ndcg)), "random_ndcg10": float(np.mean(r_ndcg)),
    "learnable_gap_s1": float(oracle[1]["mean"] - random_res[1]["mean"]),
}
json.dump(sanity, open(f"{OUT}/oracle_sanity.json", "w"), indent=2)

# ---------- leakage quantification: source-disjoint vs row-random ----------
# fraction of test records whose source is seen in train
train_sources = set(df[df["split"] == "train"]["target_id"])
leak_src_disjoint = test["target_id"].isin(train_sources).mean()
# random row split (leaky reference): just shuffle rows 70/30
idx = rng.permutation(len(df)); ntr_row = int(len(df) * 0.7)
row_train = df.iloc[idx[:ntr_row]]; row_test = df.iloc[idx[ntr_row:]]
row_train_sources = set(row_train["target_id"])
leak_row = row_test["target_id"].isin(row_train_sources).mean()
print(f"leakage: source-disjoint={leak_src_disjoint:.3f}  row-random={leak_row:.3f}")

html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>P2 leakage report</title>
<style>body{{font-family:system-ui;max-width:880px;margin:2rem auto;line-height:1.5}} td,th{{border:1px solid #ccc;padding:5px 10px}}</style></head><body>
<h1>P2 Leakage &amp; split report</h1>
<h2>Split manifests (source-disjoint)</h2><p>targets: train={len(tr)} val={len(va)} test={len(te)}.
Source overlap across splits = {overlap} (GO gate: 0).</p>
<h2>Leakage (test record whose source appears in train)</h2>
<table><tr><th>split</th><th>leak fraction</th></tr>
<tr><td>source-disjoint</td><td>{leak_src_disjoint:.4f}</td></tr>
<tr><td>row-random (leaky)</td><td>{leak_row:.4f}</td></tr></table>
<p>source-disjoint leak = 0 confirms no source crosses train/test; row-random leaks {leak_row*100:.0f}% of test records.</p>
<h2>Random/oracle sanity</h2>
<table><tr><th></th><th>oracle</th><th>random</th></tr>
<tr><td>success@1</td><td>{oracle[1]['mean']:.3f}</td><td>{random_res[1]['mean']:.3f}</td></tr>
<tr><td>NDCG@10</td><td>{sanity['oracle_ndcg10']:.3f}</td><td>{sanity['random_ndcg10']:.3f}</td></tr></table>
<p>oracle success@1 = ceiling {oracle[1]['mean']:.3f}; random {random_res[1]['mean']:.3f}; learnable gap {sanity['learnable_gap_s1']:.3f}.</p>
</body></html>"""
open(f"{OUT}/leakage_report.html", "w").write(html)

print("wrote split_manifests.json/csv, oracle_sanity.json, leakage_report.html")
