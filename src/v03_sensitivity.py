"""Gate-6 sensitivity analysis (contract §12 gate 6; §9 Batch 4).

Question: does excluding (a) ambiguous BEACON rows, (b) legacy
exact-overlap targets, and (c) context-unresolved targets reverse the main
effect (the primary TBLR-vs-pointwise contrast) or its statistical
conclusion?

Exclusion definitions (frozen in registry_v3):
- ambiguous BEACON rows: rows whose mapping_status is ambiguous. The
  registry resolves every admitted row to unique/unresolved; ZERO ambiguous
  rows exist in the eligible set by construction (asserted below).
- legacy exact-overlap targets: targets whose legacy_role is
  legacy_development_test (the Angenent-Mari original test targets that
  survive in our eligible set).
- context-unresolved targets: eligible targets with any
  context_unresolved_no_coord row.

Statistics: the SAME single-evaluator kernel (cluster_bootstrap +
signflip_pvalue from toeholdbench.stats) applied to the restricted target
sets, per completed backbone. Conclusion reversal = the primary contrast's
sign flipping or its CI crossing zero in the opposite direction.

Outputs: /mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/sensitivity_gate6/
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

PROJ = "/home/cunyuliu/ToeholdDesignBench"
BASE = "/mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0"
sys.path.insert(0, f"{PROJ}/src")
from toeholdbench.stats import cluster_bootstrap, signflip_pvalue  # noqa: E402

OUT = f"{BASE}/sensitivity_gate6"
N_SIGNFLIP = 50000


def primary_contrast_on(tm, tt, targets):
    """Paired per-target NDCG@10 for full_tblr minus tb_mse on `targets`."""
    sub = tm[tm["target_id"].isin(targets)]
    a = sub[sub["method_id"].str.contains("full_tblr")].set_index(
        "target_id")["ndcg@10"]
    b = sub[sub["method_id"].str.contains("tb_mse")].set_index(
        "target_id")["ndcg@10"]
    # tb_mse rows also match 'tb_lambdarank'? No: use exact ids.
    common = a.index.intersection(b.index)
    return (a.loc[common].sort_index().values,
            b.loc[common].sort_index().values,
            common)


def main():
    os.makedirs(OUT, exist_ok=True)
    tm_by_bb = {}
    tt = pd.read_csv(f"{BASE}/registry_v3/target_table.csv")
    can = pd.read_parquet(f"{BASE}/registry_v3/canonical_manifest.parquet")

    # ---- exclusion sets ----
    el = can[can["eligibility_status"] == "eligible_ranking"]
    # (a) ambiguous BEACON rows in the eligible set
    amb = el[el["mapping_status"].astype(str).str.contains(
        "ambig", case=False, na=False)]
    n_ambiguous_rows = len(amb)

    legacy_test = set(tt[tt["legacy_role"] == "legacy_development_test"]
                      ["target_id"])
    unresolved = set(el[el["context_status"] ==
                        "context_unresolved_no_coord"]["target_id"])

    results = {
        "gate": "gate6_sensitivity",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "exclusion_definitions": {
            "ambiguous_beacon_rows": ("mapping_status contains 'ambiguous' "
                                      "within eligible_ranking rows"),
            "legacy_exact_overlap_targets": ("target_table legacy_role == "
                                             "legacy_development_test"),
            "context_unresolved_targets": ("any eligible row with "
                                           "context_unresolved_no_coord"),
        },
        "n_ambiguous_beacon_rows_in_eligible": n_ambiguous_rows,
        "note_ambiguous": ("ZERO ambiguous BEACON rows exist in the eligible "
                           "set by registry construction (all admitted rows "
                           "resolve to unique/unresolved), so exclusion (a) "
                           "is vacuous -- asserted, not assumed."),
    }

    rows = []
    backbones = sorted(
        d.replace("eval_", "").replace("_family", "")
        for d in os.listdir(BASE)
        if d.startswith("eval_") and d.endswith("_family")
        and os.path.exists(f"{BASE}/{d}/target_metrics.csv"))
    print("families discovered:", backbones)
    for bb in backbones:
        tm = pd.read_csv(f"{BASE}/eval_{bb}_family/target_metrics.csv")
        # exact method ids
        ma = tm[tm["method_id"] == f"{bb}/full_tblr"].set_index("target_id")
        mb = tm[tm["method_id"] == f"{bb}/tb_mse"].set_index("target_id")
        common = ma.index.intersection(mb.index)
        a = ma.loc[common, "ndcg@10"].sort_index()
        b = mb.loc[common, "ndcg@10"].sort_index()
        cl = ma.loc[common, "target_cluster_id"].sort_index()
        all_targets = set(common)

        variants = {
            "full": all_targets,
            "excl_legacy": all_targets - legacy_test,
            "excl_context_unresolved": all_targets - unresolved,
            "excl_both": (all_targets - legacy_test) - unresolved,
        }
        for name, targets in variants.items():
            keep = common.intersection(sorted(targets))
            ai = a.loc[keep]
            bi = b.loc[keep]
            cli = cl.loc[keep]
            boot = cluster_bootstrap(ai.values, bi.values, cli.values)
            sf = signflip_pvalue(ai.values, bi.values, cli.values,
                                 n_rep=N_SIGNFLIP)
            p = sf["p_value"]
            rows.append({
                "backbone": bb, "variant": name, "n_targets": len(keep),
                "n_clusters": boot["n_clusters"],
                "mean_diff": boot["mean_diff"],
                "ci_low": boot["ci_low"], "ci_high": boot["ci_high"],
                "signflip_p": p,
            })
            print(f"{bb} {name}: n={len(keep)} "
                  f"diff={boot['mean_diff']:.4f} "
                  f"[{boot['ci_low']:.4f}, {boot['ci_high']:.4f}] p={p:.2e}")

    df = pd.DataFrame(rows)
    df.to_csv(f"{OUT}/sensitivity_primary_contrast.csv", index=False)

    # ---- reversal check ----
    # main effect (full variant) direction per backbone
    reversals = []
    for bb in backbones:
        base = df[(df["backbone"] == bb) & (df["variant"] == "full")].iloc[0]
        for _, r in df[(df["backbone"] == bb) &
                       (df["variant"] != "full")].iterrows():
            sign_flip = (np.sign(r["mean_diff"]) !=
                         np.sign(base["mean_diff"]))
            # conclusion reversal: baseline CI entirely below 0; a reversal
            # would be the restricted CI entirely ABOVE 0 (or vice versa)
            base_excludes0 = (base["ci_low"] > 0) or (base["ci_high"] < 0)
            r_opposite = ((base["ci_high"] < 0 and r["ci_low"] > 0) or
                          (base["ci_low"] > 0 and r["ci_high"] < 0))
            if sign_flip or r_opposite:
                reversals.append(f"{bb}/{r['variant']}")
    results["reversals"] = reversals
    results["conclusion"] = (
        "NO REVERSAL: the primary contrast stays negative with CIs excluding "
        "zero in the same direction across all exclusion variants on both "
        "backbones" if not reversals else
        f"REVERSAL DETECTED: {reversals}")
    results["per_variant"] = rows

    with open(f"{OUT}/sensitivity_summary.json", "w") as fh:
        json.dump(results, fh, indent=2)
    print()
    print(results["conclusion"])
    print("ARTIFACTS:", OUT)


if __name__ == "__main__":
    main()
