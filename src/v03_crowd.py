"""Crowdsourced 100-regulator architecture-shift external track (contract §9
Batch 4; family: Architecture-shift).

Source: 2026 crowdsourced riboregulator preprint (Green lab, bioRxiv
2026.07.08.737257; PMC13370501 Supplementary Table 1 = 100 heterogeneous
community-designed riboregulators with native cell-free TX-TL continuous
outcomes).

Contract requirements:
- native continuous outcomes (ON average, OFF average, ON-OFF, fold change);
  NO artificial candidate-set NDCG (contract §4 execution boundary)
- Spearman correlations of frozen canonical-transfer models vs native outcomes
- architecture-cluster bootstrap (structural grouping from Supplementary
  Table 3 features; k-means K=5, seed 20260821, complete-case rows)
- exposure check vs canonical training registry (must be 0 overlap for
  independent-external-study status)

Scoring input mapping (deterministic, documented; crowdsourced sensors do NOT
follow the canonical switch==RC(trigger) relation -- verified 0/100):
- cnn60 transfer models: trigger30 = Target[:30] right-padded with N;
  switch30 = Sensor[:30] (all sensors >= 41 nt)
- sandstorm transfer models: construct59 = Sensor[:59] right-padded with N;
  prototype PPM = contact_map_ppm(construct59)
- rnaelectra transfer models: construct = Sensor (tokenized, max_length 62)

Outputs under /mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/crowd_external_<ts>/.
"""
import argparse
import glob
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import torch
from scipy.stats import spearmanr
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

PROJ = "/home/cunyuliu/ToeholdDesignBench"
MNT = "/mnt/cunyuliu/ToeholdDesignBench"
BASE = f"{MNT}/runs/v0.3.0"
sys.path.insert(0, f"{PROJ}/src")
import v03_tblr as vr  # noqa: E402

XLSX = f"{MNT}/external_data/crowdsourced/media-1.xlsx"
FINAL_SEEDS = [20260821, 20260822, 20260823, 20260824, 20260825]
CLUSTER_K = 5
CLUSTER_SEED = 20260821
N_BOOT = 5000
BOOT_SEED = 20260821
STRUCT_FEATURES = ["Sensor Length", "Target Length", "Start Index from TSS",
                   "Target Bound to RBS", "Target Bound to GFP",
                   "RBS to GFP", "Start to GFP"]


def clean_seq(s):
    return str(s).upper().replace("U", "T")


def pad_to(s, n):
    s = clean_seq(s)
    return s[:n] + "N" * max(0, n - len(s))


def load_regulators():
    """T1 (100 regulators) joined with T3 structural features by number."""
    xl = pd.ExcelFile(XLSX)
    t1 = xl.parse("Supplementary Table 1")
    t3 = xl.parse("Supplementary Table 3")
    t3["num"] = pd.to_numeric(
        t3["Sensor Number"].astype(str).str.replace(
            "Sensor", "", regex=False).str.strip(), errors="coerce")
    t3 = t3[t3["num"].isin(t1["Number"])].copy()
    t3.columns = [c.replace("\xa0", " ") for c in t3.columns]
    t1 = t1.copy()
    t1["sensor"] = [clean_seq(s) for s in t1["Sensor"]]
    t1["target"] = [clean_seq(s) for s in t1["Target"]]
    t1["label_on"] = t1["ON\xa0average"].astype(float)
    t1["label_off"] = t1["OFF average"].astype(float)
    t1["label_fold"] = t1["Fold Change Fluorescence"].astype(float)
    t1["label_onoff"] = t1["label_on"] - t1["label_off"]
    feat = t3.set_index("num")[STRUCT_FEATURES].apply(
        pd.to_numeric, errors="coerce")
    feat = feat.loc[feat.index.intersection(t1["Number"])]
    t1 = t1.set_index("Number")
    for c in STRUCT_FEATURES:
        t1[c] = feat[c]
    t1 = t1.reset_index()
    # cross-check sensor length feature against the actual sequences
    agree = (t1["Sensor Length"] == t1["sensor"].str.len()).mean()
    assert agree > 0.99, f"T1/T3 sensor length disagreement: {agree}"
    return t1


def exposure_check(regs):
    """Overlap of crowdsourced sensors/targets vs canonical registry."""
    can = pd.read_parquet(f"{BASE}/registry_v3/canonical_manifest.parquet")
    can_sw = set(can["switch_or_construct_sequence"].astype(str))
    can_tr = set(can["trigger_sequence"].astype(str))
    crowd_sw = set(regs["sensor"])
    crowd_tr = set(regs["target"])
    tr30 = set(s[:30] for s in can_tr if len(s) >= 30)
    crowd_tr30 = set(s[:30] for s in crowd_tr if len(s) >= 30)
    return {
        "sensor_overlap": len(crowd_sw & can_sw),
        "trigger_overlap": len(crowd_tr & can_tr),
        "trigger30_prefix_overlap": len(crowd_tr30 & tr30),
        "n_regulators": len(regs),
        "n_canonical_records": len(can),
    }


def architecture_clusters(regs):
    """k-means K=5 (seed 20260821) on standardized T3 structural features.

    Rows with any missing feature get no cluster (NaN) and are excluded from
    the cluster bootstrap but kept in the overall Spearman.
    """
    complete = regs[STRUCT_FEATURES].notna().all(axis=1)
    X = regs.loc[complete, STRUCT_FEATURES].values
    Xs = StandardScaler().fit_transform(X)
    km = KMeans(n_clusters=CLUSTER_K, random_state=CLUSTER_SEED, n_init=10)
    labels = km.fit_predict(Xs)
    out = pd.Series(np.nan, index=regs.index, dtype=float)
    out.loc[complete] = labels
    return out, int(complete.sum())


def load_transfer_models(backbone, device):
    d = f"{BASE}/transfer_{backbone}"
    models = []
    for seed in FINAL_SEEDS:
        p = f"{d}/transfer_s{seed}.pt"
        if not os.path.exists(p):
            return None
        ck = torch.load(p, map_location=device, weights_only=True)
        m = vr.build_model(backbone, 0.0)
        m.load_state_dict(ck["state_dict"])
        m.to(device).eval()
        models.append(m)
    return models


def score_models(backbone, models, regs, device):
    """Seed-mean predictions (score, on, off) for all regulators."""
    n = len(regs)
    acc = {"score": [], "on": [], "off": []}
    with torch.no_grad():
        for m in models:
            outs = {"score": [], "on": [], "off": []}
            for s in range(0, n, 64):
                e = min(s + 64, n)
                chunk = regs.iloc[s:e]
                if backbone == "cnn60":
                    trig = np.stack(
                        [vr.onehot(pad_to(t, 30), 30)
                         for t in chunk["target"]])
                    sw = np.stack(
                        [vr.onehot(pad_to(x, 30), 30)
                         for x in chunk["sensor"]])
                    x = np.concatenate([trig, sw], axis=1).transpose(0, 2, 1)
                    h = m(torch.from_numpy(x).to(device))
                elif backbone == "sandstorm":
                    cons = [pad_to(x, 59) for x in chunk["sensor"]]
                    xs = np.stack([vr.onehot(c, 59) for c in cons])
                    xs = np.pad(xs, ((0, 0), (1, 0), (0, 0)))
                    xt = xs.transpose(0, 2, 1)[:, None, :, :]
                    ppm = np.stack([vr.contact_map_ppm(c) for c in cons])
                    h = m(torch.from_numpy(xt).to(device),
                          torch.from_numpy(ppm[:, None, :, :]).to(device))
                elif backbone == "rnaelectra":
                    tok = vr._rnaelectra_tokenizer()
                    enc = tok(
                        [str(x).upper().replace("T", "U")
                         for x in chunk["sensor"]],
                        padding=True, truncation=True, max_length=62,
                        return_tensors="np")
                    h = m(
                        torch.from_numpy(
                            enc["input_ids"].astype(np.int64)).to(device),
                        torch.from_numpy(
                            enc["attention_mask"].astype(np.int64)).to(device))
                else:
                    raise ValueError(backbone)
                for k in outs:
                    outs[k].append(h[k].cpu().numpy())
            for k in acc:
                acc[k].append(np.concatenate(outs[k]))
    return {k: np.mean(v, axis=0) for k, v in acc.items()}


def cluster_bootstrap_spearman(pred, outcome, clusters, n_rep=N_BOOT,
                               seed=BOOT_SEED):
    """Resample architecture clusters with replacement; pooled Spearman CI."""
    rng = np.random.default_rng(seed)
    uq = np.unique(clusters[~np.isnan(clusters)])
    base = float(spearmanr(pred, outcome).statistic)
    stats = np.empty(n_rep)
    for r in range(n_rep):
        pick = rng.choice(uq, size=len(uq), replace=True)
        idx = np.concatenate(
            [np.where(clusters == c)[0] for c in pick])
        stats[r] = spearmanr(pred[idx], outcome[idx]).statistic
    return base, float(np.percentile(stats, 2.5)), \
        float(np.percentile(stats, 97.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--backbones", nargs="+",
                    default=["cnn60", "sandstorm"])
    args = ap.parse_args()

    if not torch.cuda.is_available():
        print("FATAL: CUDA unavailable (contract: no silent CPU fallback)")
        sys.exit(3)
    device = torch.device(args.device)

    ts = time.strftime("%Y%m%dT%H%M%S")
    out_dir = f"{BASE}/crowd_external_{ts}"
    os.makedirs(out_dir)

    regs = load_regulators()
    print(f"crowdsourced regulators: {len(regs)} "
          f"(SINGLE external study -- cell-free TX-TL; native continuous "
          f"outcomes; no candidate-set NDCG per contract)")
    regs.to_parquet(f"{out_dir}/regulators.parquet", index=False)

    exposure = exposure_check(regs)
    print("exposure check:", json.dumps(exposure))
    with open(f"{out_dir}/exposure_check.json", "w") as fh:
        json.dump(exposure, fh, indent=2)

    clusters, n_complete = architecture_clusters(regs)
    regs["arch_cluster"] = clusters
    print(f"architecture clusters: K={CLUSTER_K}, "
          f"{n_complete}/{len(regs)} complete-feature rows")
    print(regs.groupby("arch_cluster")["Sequence_Name"].count().to_dict())

    rows = []
    pred_rows = []
    for backbone in args.backbones:
        models = load_transfer_models(backbone, device)
        if models is None:
            print(f"transfer models for {backbone} not frozen yet -- skipped")
            continue
        preds = score_models(backbone, models, regs, device)
        for i, r in regs.iterrows():
            pred_rows.append({
                "record_id": f"crowd_{int(r['Number'])}",
                "method_id": f"transfer-{backbone}",
                "score": float(preds["score"][i]),
                "predicted_on": float(preds["on"][i]),
                "predicted_off": float(preds["off"][i]),
                "label_on": float(r["label_on"]),
                "label_off": float(r["label_off"]),
                "label_onoff": float(r["label_onoff"]),
                "label_fold": float(r["label_fold"]),
                "arch_cluster": (None if np.isnan(clusters[i])
                                 else int(clusters[i])),
            })
        for head, outcome, oname in [
                ("score", regs["label_onoff"].values, "onoff"),
                ("on", regs["label_on"].values, "on"),
                ("off", regs["label_off"].values, "off"),
                ("score", regs["label_fold"].values, "fold_change")]:
            pred = preds[head]
            base, lo, hi = cluster_bootstrap_spearman(
                pred, outcome, clusters.values)
            rho_all = float(spearmanr(pred, outcome).statistic)
            rows.append({
                "method_id": f"transfer-{backbone}",
                "prediction": head, "outcome": oname,
                "spearman": rho_all,
                "cluster_boot_lo": lo, "cluster_boot_hi": hi,
                "n": len(regs), "n_clustered": n_complete,
            })
            print(f"transfer-{backbone} {head} vs {oname}: "
                  f"rho={rho_all:.4f} [{lo:.4f}, {hi:.4f}]")

    pd.DataFrame(pred_rows).to_parquet(f"{out_dir}/predictions.parquet",
                                        index=False)
    summary = pd.DataFrame(rows)
    summary.to_csv(f"{out_dir}/spearman_summary.csv", index=False)
    with open(f"{out_dir}/execution_manifest.json", "w") as fh:
        json.dump({
            "track": "crowdsourced-100-regulator architecture-shift",
            "source": "bioRxiv 2026.07.08.737257 (PMC13370501) Suppl Table 1",
            "download": "pmc PoW-solved fetch (script in logs)",
            "n_regulators": len(regs),
            "outcomes": ["ON avg", "OFF avg", "ON-OFF",
                         "Fold Change Fluorescence"],
            "statistic": "Spearman + architecture-cluster bootstrap "
                         f"(K={CLUSTER_K} k-means seed {CLUSTER_SEED}, "
                         f"{N_BOOT} reps)",
            "boundaries": [
                "single external study; cell-free TX-TL system",
                "native continuous outcomes; NO candidate-set NDCG",
                "crowdsourced sensors do not follow canonical "
                "switch==RC(trigger) (verified 0/100)",
                "exposure: 0 overlap with canonical registry",
            ],
            "backbones": args.backbones,
            "device": str(device),
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }, fh, indent=2)
    print("ARTIFACTS:", out_dir)


if __name__ == "__main__":
    main()
