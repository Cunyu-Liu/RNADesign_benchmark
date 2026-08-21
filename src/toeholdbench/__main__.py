"""Unified evaluation entry point (contract §10).

Usage:
  python -m toeholdbench evaluate \
      --track <track_manifest.parquet> \
      --predictions <score_file.(csv|parquet)> \
      --output <run_directory> \
      [--primary-contrast A:B] [--secondary-contrast A:B] ...

Generates target-level metrics, cluster-level contrasts with bootstrap CIs and
sign-flip P values (Holm-corrected over secondaries), coverage/exclusion and
exposure reports, table/figure source data, and a machine-readable execution
manifest. The output directory must not already exist (never overwrite).
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import __version__
from .adapters import check_coverage, load_predictions
from .evaluator import evaluate_target
from .stats import cluster_bootstrap, holm, signflip_pvalue

THRESHOLD_GRID = [(ta, tb) for ta in (0.3, 0.4, 0.5, 0.6, 0.7)
                  for tb in (0.3, 0.4, 0.5, 0.6, 0.7)]
LEGACY_CELL = (0.5, 0.5)


def parse_contrast(spec):
    a, b = spec.split(":")
    if a == b:
        raise ValueError(f"self-contrast: {spec}")
    return a, b


def main(argv=None):
    ap = argparse.ArgumentParser(prog="toeholdbench")
    ap.add_argument("command", choices=["evaluate"])
    ap.add_argument("--track", required=True)
    ap.add_argument("--predictions", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--primary-contrast", default=None)
    ap.add_argument("--secondary-contrast", action="append", default=[])
    ap.add_argument("--bootstrap-reps", type=int, default=5000)
    ap.add_argument("--signflip-reps", type=int, default=50000)
    ap.add_argument("--seed", type=int, default=20260821)
    args = ap.parse_args(argv)

    if os.path.exists(args.output):
        print(f"REFUSING to overwrite existing output: {args.output}", file=sys.stderr)
        return 2
    os.makedirs(args.output)

    track = pd.read_parquet(args.track)
    preds = load_predictions(args.predictions)

    # eligible set: frozen before scoring (contract §10)
    eligible = track[track["eligibility_status"] == "eligible_ranking"].copy()
    check_coverage(preds, eligible)

    # seed-average BEFORE target metrics (contract §5)
    score_cols = ["track_id", "fold", "target_id", "target_cluster_id",
                  "record_id", "method_id"]
    avg = (preds.groupby(score_cols, as_index=False)["score"].mean())

    label_by_rec = track.set_index("record_id")
    on_by_rec = label_by_rec["label_on"].to_dict()
    off_by_rec = label_by_rec["label_off"].to_dict()
    onoff_by_rec = (label_by_rec["label_on"] - label_by_rec["label_off"]).to_dict()
    cl_by_target = track.drop_duplicates("target_id").set_index("target_id")[
        "target_cluster_id"].to_dict()

    target_rows = []
    exposure = []
    for method, sub in avg.groupby("method_id"):
        for tid, tsub in sub.groupby("target_id"):
            onoff = [onoff_by_rec[r] for r in tsub["record_id"]]
            on_l = [on_by_rec[r] for r in tsub["record_id"]]
            off_l = [off_by_rec[r] for r in tsub["record_id"]]
            res = evaluate_target(tsub["score"].values, onoff, on_l, off_l,
                                  THRESHOLD_GRID)
            if res is None:
                continue  # ineligible: not in ranking denominators
            res.update({"method_id": method, "target_id": tid,
                        "target_cluster_id": cl_by_target.get(tid)})
            target_rows.append(res)
        exposure.append({"method_id": method, "n_scored": int(len(sub)),
                         "dataset_exposure": "declared-by-method-registry"})
    tmet = pd.DataFrame(target_rows)
    tmet.to_csv(f"{args.output}/target_metrics.csv", index=False)

    # aggregate: targets equally weighted
    summary_rows = []
    metric_cols = [c for c in tmet.columns
                   if c not in ("method_id", "target_id", "target_cluster_id")]
    for method, sub in tmet.groupby("method_id"):
        row = {"method_id": method, "n_targets": len(sub)}
        for c in metric_cols:
            row[c] = float(sub[c].mean())
        summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(f"{args.output}/method_summary.csv", index=False)

    # contrasts
    contrasts = []
    if args.primary_contrast:
        a, b = parse_contrast(args.primary_contrast)
        contrasts.append({"kind": "primary", "a": a, "b": b})
    for spec in args.secondary_contrast:
        a, b = parse_contrast(spec)
        contrasts.append({"kind": "secondary", "a": a, "b": b})
    contrast_rows = []
    secondary_p = []
    for c in contrasts:
        sa = tmet[tmet["method_id"] == c["a"]].set_index("target_id")["ndcg@10"]
        sb = tmet[tmet["method_id"] == c["b"]].set_index("target_id")["ndcg@10"]
        common = sa.index.intersection(sb.index)
        if len(common) == 0:
            raise ValueError(f"no common targets for contrast {c['a']}:{c['b']}")
        va, vb = sa.loc[common].values, sb.loc[common].values
        cl = tmet[tmet["method_id"] == c["a"]].set_index("target_id")[
            "target_cluster_id"].loc[common].values
        boot = cluster_bootstrap(va, vb, cl, n_rep=args.bootstrap_reps,
                                 seed=args.seed)
        sf = signflip_pvalue(va, vb, cl, n_rep=args.signflip_reps,
                             seed=args.seed)
        row = {"kind": c["kind"], "method_a": c["a"], "method_b": c["b"],
               "n_targets": len(common), **boot, "p_value": sf["p_value"]}
        contrast_rows.append(row)
        if c["kind"] == "secondary":
            secondary_p.append(sf["p_value"])
    if secondary_p:
        adj = holm(secondary_p)
        idx = 0
        for row in contrast_rows:
            if row["kind"] == "secondary":
                row["p_holm"] = adj[idx]
                idx += 1
    pd.DataFrame(contrast_rows).to_csv(f"{args.output}/contrasts.csv", index=False)

    # coverage / exclusion report
    cov = {
        "track_records": int(len(track)),
        "eligible_targets": int(track[track["eligibility_status"] ==
                                      "eligible_ranking"]["target_id"].nunique()),
        "eligibility_counts": track["eligibility_status"].value_counts().to_dict(),
        "mapping_status_counts": track["mapping_status"].value_counts().to_dict(),
        "context_resolved_records": int(track["context_512"].notna().sum()),
        "predictions_rows": int(len(preds)),
        "prediction_methods": sorted(preds["method_id"].unique().tolist()),
        "prediction_seeds": sorted(preds["seed"].unique().tolist()),
    }
    with open(f"{args.output}/coverage_report.json", "w") as fh:
        json.dump(cov, fh, indent=2)

    manifest = {
        "package_version": __version__,
        "command": "evaluate",
        "track": args.track,
        "predictions": args.predictions,
        "output": args.output,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "threshold_grid": [list(t) for t in THRESHOLD_GRID],
        "legacy_cell": list(LEGACY_CELL),
        "bootstrap_reps": args.bootstrap_reps,
        "signflip_reps": args.signflip_reps,
        "seed": args.seed,
        "primary_contrast": args.primary_contrast,
        "secondary_contrasts": args.secondary_contrast,
        "n_target_metric_rows": int(len(tmet)),
    }
    with open(f"{args.output}/execution_manifest.json", "w") as fh:
        json.dump(manifest, fh, indent=2)

    print(json.dumps({"methods": len(summary_rows),
                      "target_metric_rows": len(tmet),
                      "contrasts": len(contrast_rows)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
