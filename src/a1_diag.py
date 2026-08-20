"""Diagnose BEACON ON/OFF distribution vs canonical to choose a fair success criterion
for the expanded (n=23) virus evaluation.
"""
import pandas as pd, numpy as np, json

MAP = "/mnt/cunyuliu/ToeholdDesignBench/external/beacon_prs/beacon_target_mapping.csv"
b = pd.read_csv(MAP, dtype=str)
for c in ["ON","OFF","ON_OFF"]:
    b[c] = b[c].astype(float)

v = b[b["category"]=="virus"]
print("=== BEACON virus: ON/OFF/ON_OFF quantiles ===")
for c in ["ON","OFF","ON_OFF"]:
    print(f"  {c}: p10={v[c].quantile(.1):.3f} p50={v[c].median():.3f} p90={v[c].quantile(.9):.3f}")

# canonical for reference
canon = pd.read_parquet("/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_records.parquet")
canon = canon[canon["admission_status"]=="admitted_paired"].copy(); canon=canon[canon["ON_OFF"].notna()]
print("\n=== canonical: ON/OFF/ON_OFF quantiles (all paired) ===")
for c in ["ON","OFF","ON_OFF"]:
    print(f"  {c}: p10={canon[c].quantile(.1):.3f} p50={canon[c].median():.3f} p90={canon[c].quantile(.9):.3f}")

# BEACON binary relation: with ON_OFF independent, use ON alone threshold? Test:
# what frac have ON>=0.5, what frac OFF<=0.5
print("\nBEACON virus: ON>=0.5:", (v["ON"]>=0.5).mean(), " OFF<=0.5:", (v["OFF"]<=0.5).mean())
print("canonical: ON>=0.5:", (canon["ON"]>=0.5).mean(), " OFF<=0.5:", (canon["OFF"]<=0.3).mean())

# A1 evaluation should use RELATIVE success (per-target), robust to scale:
# success@1 = target's top-1 ranked by score is actually-successful.
# We need a "true success" label. Use ON_OFF (BEACON pivot) with a relative per-target
# heuristic OR report NDCG with ON_OFF relevance (scale-free).
# NDCG with continuous relevance ON_OFF is scale-invariant under monotone transforms -> SAFE.
# Check correlation structure: is ON_OFF a good relevance?
import scipy.stats as st
# per-target: corr(ON_OFF, rank) - we just need a relevance that sorts well. Use ON_OFF.
print("\nsign(ON-OFF) agreement with sign(ON_OFF):", np.mean(np.sign(v["ON"]-v["OFF"])==np.sign(v["ON_OFF"])))
# Note: if BEACON ON_OFF ~ ON-scaled - OFF-scaled, sign should mostly agree with ON-OFF on same scale
# Let's see rank corr between ON_OFF and (ON-OFF)
mask = v["ON"].notna() & v["OFF"].notna() & v["ON_OFF"].notna()
print("Spearman(ON_OFF, ON-OFF) virus:", st.spearmanr(v.loc[mask,"ON_OFF"], v.loc[mask,"ON"]-v.loc[mask,"OFF"])[0].round(3))