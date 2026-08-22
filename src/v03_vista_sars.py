"""VISTA SARS-CoV groups: selection-conditioned analysis (contract §9
Batch 4).

Source: Toehold-VISTA (Robson & Green, NAR 2026, gkag097; PMC12907555)
Supplementary Table 9 -- 72 switches in 6 selection groups (12 each):
- VISTA_GFP_low_onoff / high_onoff: mCherry-screen switches selected by
  VISTA's own predicted ON/OFF (low vs high)
- VISTA_GFP_low_off / high_on: selected by predicted OFF / ON
- tsgen2_GFP_SARSCoV2_11_N: tsgen2-designed SARS-CoV-2 N-gene switches
- VISTA_LacZ_SARS_COV_2_N: VISTA-designed SARS-CoV-2 N-gene switches

Boundary (contract): these switches were SELECTED by design-model scores,
so any performance readout is selection-conditioned description -- never
independent validation. The analysis: (a) paper-native group separation of
measured ON/OFF; (b) frozen canonical-transfer model scores per group
(descriptive; input mapping identical to the mCherry track: trigger30 =
target[6:36], switch30 = switch[25:55], alignment verified 72/72).

Outputs under /mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/vista_sars_<ts>/.
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import torch
from scipy.stats import spearmanr

PROJ = "/home/cunyuliu/ToeholdDesignBench"
MNT = "/mnt/cunyuliu/ToeholdDesignBench"
BASE = f"{MNT}/runs/v0.3.0"
sys.path.insert(0, f"{PROJ}/src")
import v03_tblr as vr  # noqa: E402

XLSX = (f"{MNT}/external_data/vista_nar/supplemental/"
        "Robson_Green_Toehold_VISTA_Supp_Data_updated2.xlsx")
FINAL_SEEDS = [20260821, 20260822, 20260823, 20260824, 20260825]
T7_PREFIX = 25  # switch[25:55] == RC(target[-30:]) verified 72/72


def parse_group(name):
    return str(name).rsplit("_", 1)[0]


def load_groups():
    t9 = pd.read_excel(XLSX, sheet_name="Supplementary_Table9")
    t9 = t9.rename(columns={"Unnamed: 0": "design_id"})
    t9["group"] = t9["design_id"].map(parse_group)
    t9["trigger30"] = t9["Target Sequence"].astype(
        str).str.upper().str[6:36]
    t9["switch30"] = t9["Switch Sequence"].astype(
        str).str.upper().str[T7_PREFIX:T7_PREFIX + 30]
    # alignment invariant: switch30 == RC(trigger30)
    comp = {"A": "T", "T": "A", "C": "G", "G": "C"}
    for _, r in t9.iterrows():
        rc = "".join(comp.get(b, "N")
                     for b in r["trigger30"][::-1])
        assert r["switch30"] == rc, f"alignment failed: {r['design_id']}"
    return t9


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


def score_cnn60(models, df, device):
    trig = np.stack([vr.onehot(s, 30) for s in df["trigger30"]])
    sw = np.stack([vr.onehot(s, 30) for s in df["switch30"]])
    x = np.concatenate([trig, sw], axis=1).transpose(0, 2, 1)
    return _forward(models, x, device)


def construct59_of(df):
    """SANDSTORM construct window: switch[25:84] (sensor starts after the
    25-nt T7 promoter; same position convention as the switch30 toehold)."""
    return [s[T7_PREFIX:T7_PREFIX + 59]
            for s in df["Switch Sequence"].astype(str).str.upper()]


def score_sandstorm(models, df, device):
    cons = construct59_of(df)
    xs = np.stack([vr.onehot(c, 59) for c in cons])
    xs = np.pad(xs, ((0, 0), (1, 0), (0, 0)))
    x = xs.transpose(0, 2, 1)[:, None, :, :]
    ppm = np.stack([vr.contact_map_ppm(c) for c in cons])[:, None, :, :]
    return _forward(models, (x, ppm), device)


def _forward(models, inputs, device):
    scores, ons, offs = [], [], []
    with torch.no_grad():
        for m in models:
            outs = {"score": [], "on": [], "off": []}
            for s in range(0, len(inputs if isinstance(inputs, np.ndarray)
                                      else inputs[0]), 64):
                if isinstance(inputs, np.ndarray):
                    args = (torch.from_numpy(inputs[s:s + 64]).to(device),)
                else:
                    x, ppm = inputs
                    args = (torch.from_numpy(x[s:s + 64]).to(device),
                            torch.from_numpy(ppm[s:s + 64]).to(device))
                h = m(*args)
                for k in outs:
                    outs[k].append(h[k].cpu().numpy())
            scores.append(np.concatenate(outs["score"]))
            ons.append(np.concatenate(outs["on"]))
            offs.append(np.concatenate(outs["off"]))
    return (np.mean(scores, axis=0), np.mean(ons, axis=0),
            np.mean(offs, axis=0))


def group_summary(df, score_col):
    rows = []
    for g, sub in df.groupby("group"):
        rows.append({
            "group": g, "n": len(sub),
            "measured_onoff_full_mean": float(sub["ON/OFF Full RNA "].mean()),
            "measured_onoff_trunc_mean":
                float(sub["ON/OFF Truncated"].mean()),
            "measured_on_full_mean": float(sub["Full RNA ON Avg"].mean()),
            "measured_off_mean": float(sub["OFF AVG"].mean()),
            f"{score_col}_mean": float(sub[score_col].mean()),
            f"{score_col}_sem": float(sub[score_col].sem()),
        })
    return pd.DataFrame(rows).sort_values("group")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda:0")
    args = ap.parse_args()
    if not torch.cuda.is_available():
        print("FATAL: CUDA unavailable (contract: no silent CPU fallback)")
        sys.exit(3)
    device = torch.device(args.device)

    ts = time.strftime("%Y%m%dT%H%M%S")
    out_dir = f"{BASE}/vista_sars_{ts}"
    os.makedirs(out_dir)

    df = load_groups()
    print(f"VISTA SARS-CoV selection groups: {len(df)} switches, "
          f"{df['group'].nunique()} groups (SELECTION-CONDITIONED -- "
          f"description only, never independent validation)")
    df.to_parquet(f"{out_dir}/groups.parquet", index=False)

    # (a) paper-native group separation (measured outcomes only)
    native = group_summary(df, "ON/OFF Full RNA ")
    native.to_csv(f"{out_dir}/group_measured_summary.csv", index=False)
    print(native.to_string(index=False))

    # (b) frozen transfer model scores per group (descriptive)
    for backbone in ("cnn60", "sandstorm"):
        models = load_transfer_models(backbone, device)
        if models is None:
            print(f"transfer_{backbone} not frozen yet; skipped")
            continue
        if backbone == "sandstorm":
            sc, on, off = score_sandstorm(models, df, device)
        else:
            sc, on, off = score_cnn60(models, df, device)
        df[f"transfer_{backbone}_score"] = sc
        df[f"transfer_{backbone}_on"] = on
        df[f"transfer_{backbone}_off"] = off
        ms = group_summary(df, f"transfer_{backbone}_score")
        ms.to_csv(f"{out_dir}/group_transfer_scores_{backbone}.csv",
                  index=False)
        print(ms.to_string(index=False))
        # pooled Spearman (selection-conditioned; descriptive only)
        rho_full = float(spearmanr(sc, df["ON/OFF Full RNA "]).statistic)
        rho_trunc = float(spearmanr(sc, df["ON/OFF Truncated"]).statistic)
        print(f"pooled Spearman transfer-{backbone} score vs measured "
              f"ON/OFF: full={rho_full:.4f} truncated={rho_trunc:.4f} "
              f"(SELECTION-CONDITIONED, no CI claim)")
    df.to_parquet(f"{out_dir}/predictions.parquet", index=False)

    with open(f"{out_dir}/execution_manifest.json", "w") as fh:
        json.dump({
            "track": "VISTA SARS-CoV selection groups "
                     "(selection-conditioned)",
            "source": "Toehold-VISTA NAR 2026 gkag097 (PMC12907555) "
                      "Supplementary Table 9",
            "n_switches": len(df), "n_groups": int(df["group"].nunique()),
            "groups": sorted(df["group"].unique().tolist()),
            "input_mapping": "trigger30 = target[6:36]; switch30 = "
                             "switch[25:55] (alignment verified 72/72)",
            "boundaries": [
                "switches SELECTED by design-model scores; descriptive "
                "analysis only, never independent validation",
                "single study; paper's own selection groups",
                "no CI / hypothesis test on pooled Spearman "
                "(selection-conditioned data)",
            ],
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }, fh, indent=2)
    print("ARTIFACTS:", out_dir)


if __name__ == "__main__":
    main()
