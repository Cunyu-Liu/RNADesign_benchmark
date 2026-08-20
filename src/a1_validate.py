"""A1-2: validate BEACON virus rows — label ranges, success under absolute threshold,
per-target sizes, and whether a source-disjoint split is possible for virus targets.
"""
import pandas as pd
import numpy as np
import json

MAP = "/mnt/cunyuliu/ToeholdDesignBench/external/beacon_prs/beacon_target_mapping.csv"
df = pd.read_csv(MAP, dtype=str)
df["ON"] = df["ON"].astype(float); df["OFF"] = df["OFF"].astype(float); df["ON_OFF"] = df["ON_OFF"].astype(float)

virus = df[df["category"] == "virus"].copy()
print("virus rows:", len(virus))
print("ON min/max:", virus["ON"].min(), virus["ON"].max(), "| OFF min/max:", virus["OFF"].min(), virus["OFF"].max())
print("ON_OFF min/max:", virus["ON_OFF"].min(), virus["ON_OFF"].max())

# Does ON_OFF == ON - OFF? (BEACON independent normalization)
viol = (virus["ON"] - virus["OFF"] - virus["ON_OFF"]).abs()
print("ON-OFF vs ON_OFF: median |diff| =", viol.median(), " max =", viol.max())

# success under absolute threshold (on BEACON's ON/OFF)
virus["success"] = ((virus["ON"] >= 0.5) & (virus["OFF"] <= 0.5)).astype(int)
print("\nsuccess rate (abs):", virus["success"].mean(), " n successful:", int(virus["success"].sum()))

# per-target sizes & success
pt = virus.groupby("target_id").agg(n=("sequence","count"), succ=("success","mean")).reset_index()
print("\nper-target sizes:")
for _, r in pt.sort_values("n", ascending=False).iterrows():
    print(f"  {r['target_id']:24s} n={int(r['n']):4d} succ={r['succ']:.2f}")

print("\nviruses with n>=10:", int((pt["n"]>=10).sum()))
print("viruses with n>=30:", int((pt["n"]>=30).sum()))
print("total virus targets:", len(pt))
print("median per-target n:", int(pt["n"].median()))

# split sizes
print("\nsplit virus rows:", virus["split"].value_counts().to_dict())
vt = virus.groupby(["split","target_id"]).size()
print("test virus targets:", int(vt.loc["test"].shape[0]))
print("test virus records:", int(vt.loc["test"].sum()))

json.dump({"n_virus_targets": len(pt),
           "virus_targets": sorted(pt["target_id"].tolist()),
           "per_target": pt.to_dict("records"),
           "success_rate": round(float(virus["success"].mean()),4),
           "n_success": int(virus["success"].sum())},
          open("/mnt/cunyuliu/ToeholdDesignBench/processed/a1_virus_label_stats.json","w"), indent=2)
print("\nwrote a1_virus_label_stats.json")