"""VISTA mCherry external track: native site ranking analysis (contract §9
Batch 4, §5 statistics).

Native endpoint: site-level NDCG@10 on the measured ON-OFF labels of the 189
mCherry sites (single target -- intervals are SITE-level uncertainty only and
are never extrapolated to multi-target claims, contract §5).

Methods scored on the native track:
- vista-tsgen2: official tsgen2 ranking (column 'tsgen2 rank'; score = -rank)
- vista-plsda-full / vista-plsda-trunc: official PLS-DA model rankings
  ('FULL Rank ONOFF' / 'TRUNC Rank ONOFF'; score = -rank)
- transfer models (e.g. cnn60/full_tblr): frozen canonical-trained models
  scoring (trigger30, switch30) reconstructed deterministically from each
  36-nt site: trigger30 = site[6:36] (the segment the toehold binds),
  switch30 = sensor[0:30] = RC(site[6:36]) -- the canonical relation
  switch == RC(trigger) verified on the canonical manifest
- exact-random: analytic per-target expectation (the 189 sites are ONE
  target; this is the analytic random NDCG of that single candidate set)

Statistics: site-level bootstrap (resampling the 189 sites with replacement,
5000 reps) for 95% CIs; single-target boundary recorded in every artifact.

Outputs under /mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/vista_external_<ts>/.
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

PROJ = "/home/cunyuliu/ToeholdDesignBench"
MNT = "/mnt/cunyuliu/ToeholdDesignBench"
sys.path.insert(0, f"{PROJ}/src")
import v03_tblr as vr  # noqa: E402
from toeholdbench.evaluator import expected_ndcg, random_ndcg  # noqa: E402

XLSX = f"{MNT}/external/mCH_on_off_rank.xlsx"

# VISTA official scaffold constants (Toehold_VISTA.ipynb __init__ /
# return_design_object)
HAIRPIN_TOP = "GUUAUAGUUAUGAACAGAGGAGACAUAACAUGAAC"
HAIRPIN_SUFFIX = "AACCUGGCGGCAGCGCAAAAG"
D_DOM = "AAC"

_COMP = {"A": "T", "T": "A", "C": "G", "G": "C"}


def rc_dna(s):
    return "".join(_COMP[b] for b in s[::-1])


def build_sensor(target36, output_seq30):
    """Deterministic VISTA sensor from a 36-nt target window (official
    return_design_object construction)."""
    t = target36.upper().replace("U", "T")
    toehold = rc_dna(t)[:30]
    a_dom, b_dom = t[:3], t[3:6]
    a_star, b_star = rc_dna(a_dom), rc_dna(b_dom)
    hairpin = (toehold + b_star + a_star + HAIRPIN_TOP.replace("U", "T")
               + a_dom + b_dom + D_DOM + a_star
               + rc_dna(HAIRPIN_TOP[-3:].replace("U", "T"))
               + HAIRPIN_SUFFIX.replace("U", "T") + output_seq30[:30])
    return hairpin.replace("T", "U")


def load_vista_sites():
    xl = pd.ExcelFile(XLSX)
    df = xl.parse("Calculated Values")
    df = df.dropna(subset=["Trigger Sequence"]).reset_index(drop=True)
    # output sequence: the reporter downstream of the switch (source_seq_list)
    src = pd.read_csv(
        f"{MNT}/external_src/vista/toehold-VISTA/source_seq_list.csv")
    out30 = str(src["Output Sequence"].iloc[0])[:30]
    sites = []
    for _, r in df.iterrows():
        t36 = str(r["Trigger Sequence"]).upper().replace("T", "U")
        sensor = build_sensor(t36, out30)
        # input pair for canonical-trained models
        trig30 = t36[6:36]
        switch30 = rc_dna(trig30.replace("U", "T")).replace("T", "U")
        assert switch30 == sensor[:30].replace("T", "U")[:30]
        sites.append({
            "site_id": f"vista_mch_{int(r['Index'])}",
            "index": int(r["Index"]),
            "target36": t36,
            "sensor": sensor,
            "trigger30": trig30,
            "switch30": switch30,
            "label_on_full": float(r["ON AVG Full"]),
            "label_off": float(r["OFF AVG"]),
            "label_onoff_full": float(r["ON OFF Full"]),
            "label_onoff_trunc": float(r["ON OFF Truncated"]),
            "tsgen2_rank": float(r["tsgen2 rank"]),
            "plsda_full_rank": float(r["FULL Rank ONOFF"]),
            "plsda_trunc_rank": float(r["TRUNC Rank ONOFF"]),
        })
    return pd.DataFrame(sites)


def score_transfer(models, sites_df, device, backbone):
    """Score all sites with each frozen model; returns per-seed score arrays."""
    tok = None
    if backbone == "rnaelectra":
        tok = vr._rnaelectra_tokenizer()
        enc = tok(sites_df["trigger30"].tolist(), padding=True,
                  truncation=True, max_length=62, return_tensors="np")
        enc_sw = tok(sites_df["switch30"].tolist(), padding=True,
                     truncation=True, max_length=62, return_tensors="np")
        # cnn60-style input needs one-hot; rnaelectra uses token ids of
        # trigger+switch concatenated
        ids = np.concatenate([enc["input_ids"], enc_sw["input_ids"]], axis=1)
        mask = np.concatenate([enc["attention_mask"],
                               enc_sw["attention_mask"]], axis=1)
    else:
        trig = np.stack([vr.onehot(s, 30) for s in sites_df["trigger30"]])
        sw = np.stack([vr.onehot(s, 30) for s in sites_df["switch30"]])
        x = np.concatenate([trig, sw], axis=1).transpose(0, 2, 1)

    all_scores = []
    with torch.no_grad():
        for m in models:
            m.eval()
            outs = []
            for s in range(0, len(sites_df), 256):
                e = min(s + 256, len(sites_df))
                if backbone == "rnaelectra":
                    h = m(torch.from_numpy(ids[s:e]).to(device),
                          torch.from_numpy(mask[s:e]).to(device))
                elif backbone == "sandstorm":
                    ppm = np.stack([vr.contact_map_ppm(t)
                                    for t in sites_df["trigger30"][s:e]])
                    h = m(torch.from_numpy(x[s:e][:, None, :, :]).to(device),
                          torch.from_numpy(ppm[s:e][:, None, :, :]).to(device))
                else:
                    h = m(torch.from_numpy(x[s:e]).to(device))
                outs.append(h["score"].cpu().numpy())
            all_scores.append(np.concatenate(outs))
    # seed-average BEFORE metrics (contract §5)
    return np.mean(all_scores, axis=0)


def site_bootstrap_ndcg(scores, onoff, n_rep=5000, seed=20260821, k=10):
    """Site-level bootstrap of the single-target NDCG@10."""
    rng = np.random.default_rng(seed)
    n = len(onoff)
    base = expected_ndcg(scores, onoff, k)
    stats = np.empty(n_rep)
    for r in range(n_rep):
        idx = rng.integers(0, n, size=n)
        stats[r] = expected_ndcg(np.asarray(scores)[idx],
                                 np.asarray(onoff)[idx], k)
    return base, float(np.percentile(stats, 2.5)), \
        float(np.percentile(stats, 97.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transfer-run", default=None,
                    help="transfer run id (e.g. transfer_cnn60)")
    ap.add_argument("--device", default="cuda:0")
    args = ap.parse_args()

    ts = time.strftime("%Y%m%dT%H%M%S")
    out_dir = f"{MNT}/runs/v0.3.0/vista_external_{ts}"
    os.makedirs(out_dir)

    sites = load_vista_sites()
    print(f"VISTA mCherry sites: {len(sites)} (SINGLE TARGET -- site-level "
          f"uncertainty only)")
    sites.to_parquet(f"{out_dir}/vista_sites.parquet", index=False)

    methods = {}
    # Official rankings: score = -rank (rank 1 = model's best design). The
    # 1=best convention is documented by the VISTA paper (Fig. 5D compares
    # "switches ranked highest by tsgen2" with the PLS-DA top set) and by the
    # notebook's rank_new_designs (argsort of descending score). tsgen2's
    # below-random NDCG is therefore an honest negative result, consistent
    # with the paper's motivation. A direction-reversed sensitivity row is
    # reported for transparency (no label-based direction selection: the
    # primary direction comes from the paper's documented convention).
    methods["vista-tsgen2"] = -sites["tsgen2_rank"].values
    methods["vista-tsgen2-reversed-sensitivity"] = sites["tsgen2_rank"].values
    methods["vista-plsda-full"] = -sites["plsda_full_rank"].values
    methods["vista-plsda-trunc"] = -sites["plsda_trunc_rank"].values

    # transfer models
    if args.transfer_run:
        tdir = f"{MNT}/runs/v0.3.0/{args.transfer_run}"
        with open(f"{tdir}/run_manifest.json") as fh:
            tm = json.load(fh)
        backbone = tm["backbone"]
        device = torch.device(
            args.device if torch.cuda.is_available() else "cpu")
        if not torch.cuda.is_available():
            print("FATAL: CUDA unavailable for transfer scoring")
            sys.exit(3)
        models = []
        for seed in vr.FINAL_SEEDS:
            ck = torch.load(f"{tdir}/transfer_s{seed}.pt",
                            map_location=device, weights_only=False)
            m = vr.build_model(backbone, 0.0)
            m.load_state_dict(ck["state_dict"])
            m.to(device)
            models.append(m)
        sc = score_transfer(models, sites, device, backbone)
        methods[f"transfer-{backbone}/full_tblr"] = sc
        print(f"transfer-{backbone} scored ({len(models)} seeds averaged)")

    # endpoints
    results = {"single_target_boundary": (
                   "VISTA mCherry is ONE target; CIs are site-level "
                   "uncertainty only and must not be extrapolated to "
                   "multi-target claims"),
               "n_sites": int(len(sites))}
    for label_name, label_col in (("onoff_full", "label_onoff_full"),
                                  ("onoff_trunc", "label_onoff_trunc")):
        onoff = sites[label_col].values
        rnd = random_ndcg(onoff, 10)
        rows = []
        preds = []
        for name, sc in methods.items():
            base, lo, hi = site_bootstrap_ndcg(np.asarray(sc), onoff)
            rows.append({"method": name, "endpoint": label_name,
                         "ndcg@10": base, "ci_low": lo, "ci_high": hi,
                         "random_ndcg@10": rnd,
                         "gain_over_random": base - rnd})
            for i in range(len(sites)):
                preds.append({
                    "run_id": f"vista_external_{ts}",
                    "track_id": f"vista_mcherry_{label_name}",
                    "fold": None, "target_id": "mCherry",
                    "target_cluster_id": "vista_mcherry",
                    "record_id": sites.iloc[i]["site_id"],
                    "method_id": name, "seed": 20260821,
                    "score": float(np.asarray(sc)[i])})
        results[label_name] = rows
        pd.DataFrame(preds).to_parquet(
            f"{out_dir}/predictions_{label_name}.parquet", index=False)
        print(f"--- endpoint {label_name} (random NDCG@10 = {rnd:.4f}) ---")
        for r in sorted(rows, key=lambda x: -x["ndcg@10"]):
            print(f"  {r['method']}: {r['ndcg@10']:.4f} "
                  f"CI[{r['ci_low']:.4f}, {r['ci_high']:.4f}] "
                  f"(+{r['gain_over_random']:.4f} vs random)")

    with open(f"{out_dir}/vista_external_results.json", "w") as fh:
        json.dump(results, fh, indent=2)
    print(f"written to {out_dir}")


if __name__ == "__main__":
    main()
