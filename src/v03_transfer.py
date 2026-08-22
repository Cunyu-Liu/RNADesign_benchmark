"""External-transfer training: freeze canonical models for external scoring.

Contract §7: "外部迁移模型在不查看外部 labels 的前提下，以全 canonical
5-fold inner-CV 选择配置，随后在全 canonical 上训练五个 seeds 并冻结，
再评分外部研究。"

- Config selection: aggregate the existing per-fold tuning manifests (12
  configs x 3 inner folds x 5 outer folds); the full-canonical selection is
  the config with the best mean inner-validation NDCG@10 across all folds.
- Training: all canonical eligible targets; early-stop validation = inner
  fold 0 (train on inner folds 1+2) -- frozen convention, identical to the
  final runs; seeds 20260821..20260825.
- The five frozen models are saved per backbone for external scoring; no
  external label is read by this script.

Outputs: /mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/transfer_<backbone>/
  transfer_s<seed>.pt + selection.json + run_manifest.json
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
import pandas as pd
import torch

PROJ = "/home/cunyuliu/ToeholdDesignBench"
MNT = "/mnt/cunyuliu/ToeholdDesignBench"
sys.path.insert(0, f"{PROJ}/src")
import v03_tblr as vr  # noqa: E402


def select_config(backbone):
    """Aggregate inner-CV tuning results across all outer folds."""
    scores = {}
    for fold in range(5):
        for ci in range(12):
            vals = []
            ok = True
            for inner in range(3):
                p = (f"{MNT}/runs/v0.3.0/"
                     f"tune_{backbone}_f{fold}_c{ci:02d}_i{inner}"
                     f"/run_manifest.json")
                if not os.path.exists(p):
                    ok = False
                    break
                with open(p) as fh:
                    vals.append(json.load(fh)["best_val_ndcg10"])
            if ok:
                scores.setdefault(ci, []).extend(vals)
    if not scores:
        raise SystemExit(f"no completed tuning runs for {backbone}")
    best_ci, best_vals = max(scores.items(), key=lambda kv: float(np.mean(kv[1])))
    cfgs = [
        {"lr_mult": lm, "weight_decay": wd, "aux": aux}
        for lm in (0.5, 1.0, 2.0) for wd in ("0", "default")
        for aux in (0.1, 0.5)
    ]
    return best_ci, cfgs[best_ci], scores


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backbone", choices=["cnn60", "sandstorm", "rnaelectra"],
                    required=True)
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()

    out_dir = f"{MNT}/runs/v0.3.0/{args.run_id}"
    if os.path.exists(out_dir):
        print(f"REFUSING to overwrite {out_dir}")
        sys.exit(2)
    os.makedirs(out_dir)
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("FATAL: CUDA unavailable (contract: no silent CPU fallback)")
        sys.exit(3)

    # ---- config selection from full-canonical inner CV ----
    best_ci, cfg, all_scores = select_config(args.backbone)
    sel = {
        "backbone": args.backbone,
        "selected_config_index": best_ci,
        "config": cfg,
        "mean_inner_val_ndcg10": float(np.mean(all_scores[best_ci])),
        "n_aggregated_runs": len(all_scores[best_ci]),
        "selection_rule": ("mean inner-validation NDCG@10 aggregated over "
                           "all 5 outer folds x 3 inner folds (full-canonical "
                           "inner-CV; no external labels read)"),
    }
    with open(f"{out_dir}/selection.json", "w") as fh:
        json.dump(sel, fh, indent=2)
    print("selected:", json.dumps(sel, indent=2))

    # ---- data: ALL canonical eligible targets ----
    data, df = vr.load_data(args.backbone)
    all_targets = sorted(data.cands.keys())
    # frozen convention: early-stop validation = inner fold 0
    val_targets = [t for t in all_targets if data.inner.get(t) == 0]
    train_targets = [t for t in all_targets if data.inner.get(t) != 0]
    print(f"transfer training: {len(train_targets)} train / "
          f"{len(val_targets)} early-stop targets of {len(all_targets)}")

    full_cfg = {
        "lr": vr.LR[args.backbone] * cfg["lr_mult"],
        "weight_decay": (vr.WD_DEFAULT[args.backbone]
                         if cfg["weight_decay"] == "default"
                         else float(cfg["weight_decay"])),
        "aux_weight": cfg["aux"], "dropout": 0.0,
    }
    manifests = []
    for seed in vr.FINAL_SEEDS:
        model = vr.build_model(args.backbone, 0.0)
        info = vr.train_one(model, data, train_targets, val_targets,
                            full_cfg, device, seed, "full_tblr", args.backbone)
        path = f"{out_dir}/transfer_s{seed}.pt"
        torch.save({"state_dict": model.state_dict(), "config": full_cfg,
                    "backbone": args.backbone, "seed": seed}, path)
        info.update({"seed": seed, "model_path": path, "config": full_cfg,
                     "n_params": sum(p.numel() for p in model.parameters())})
        manifests.append(info)
        print(f"seed {seed}: val NDCG@10 {info['best_val_ndcg10']:.4f} "
              f"({info['epochs_run']} epochs)")

    with open(f"{out_dir}/run_manifest.json", "w") as fh:
        json.dump({"backbone": args.backbone,
                   "seeds": vr.FINAL_SEEDS, "folds": manifests,
                   "selection": sel}, fh, indent=2)
    print("TRANSFER MODELS FROZEN")


if __name__ == "__main__":
    main()
