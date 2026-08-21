"""Tuning orchestrator for one backbone x one outer fold (contract §7).

Phase 1 (tune): 12 pre-declared configs x 3 inner folds of the full TBLR
objective; each run = `v03_tblr.py --mode tune-inner`; config score = mean
inner-validation NDCG@10 over the 3 inner folds; tuning seed 20260821.

Phase 2 (final): the selected config is applied to all five objective
ablations x 5 final seeds (20260821..20260825) as `--mode final` runs on the
same outer fold. The config's third dimension (aux weight for auxiliary
models) maps to dropout {0.0 -> aux 0.1, 0.25 -> aux 0.5} for the two
non-auxiliary ablations, per the contract's dropout-substitution rule.

Existing run directories are skipped (resume-safe); the tuning record and
config selection are written under runs/v0.3.0/tune_<backbone>_f<fold>/.
"""
import argparse
import json
import os
import subprocess
import sys

PROJ = "/home/cunyuliu/ToeholdDesignBench"
MNT = "/mnt/cunyuliu/ToeholdDesignBench"
PY = "/home/cunyuliu/miniconda3/envs/toeholdbench/bin/python"
LR_MULTS = [0.5, 1.0, 2.0]
WDS = ["0", "default"]
AUXS = [0.1, 0.5]
AUX_TO_DROPOUT = {0.1: 0.0, 0.5: 0.25}
FINAL_SEEDS = [20260821, 20260822, 20260823, 20260824, 20260825]
ABLATIONS = ["rowwise_mse", "tb_mse", "tb_dual", "tb_lambdarank", "full_tblr"]


def configs():
    out = []
    for lr in LR_MULTS:
        for wd in WDS:
            for aux in AUXS:
                out.append({"lr_mult": lr, "weight_decay": wd, "aux": aux})
    assert len(out) == 12
    return out


def run_id_for(cfg_idx, inner, backbone, fold):
    return f"tune_{backbone}_f{fold}_c{cfg_idx:02d}_i{inner}"


def final_run_id(backbone, fold, ablation, seed):
    return f"final_{backbone}_f{fold}_{ablation}_s{seed}"


def call(args, log_path, env=None):
    with open(log_path, "a") as log:
        log.write(f"\n=== {args} ===\n")
        log.flush()
        r = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT,
                           env=env, cwd=PROJ)
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backbone", choices=["cnn60", "sandstorm"], required=True)
    ap.add_argument("--outer-fold", type=int, required=True)
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--cuda-device", default="6")
    ap.add_argument("--phase", choices=["tune", "final", "all"], default="all")
    args = ap.parse_args()

    backbone, fold = args.backbone, args.outer_fold
    tune_dir = f"{MNT}/runs/v0.3.0/tune_{backbone}_f{fold}"
    if not os.path.exists(tune_dir):
        os.makedirs(tune_dir)
    log = f"{PROJ}/logs/v03_tune_{backbone}_f{fold}.log"
    env = dict(os.environ)
    env["CUDA_VISIBLE_DEVICES"] = args.cuda_device

    # ---- phase 1: tuning ----
    if args.phase in ("tune", "all"):
        for ci, cfg in enumerate(configs()):
            scores = []
            for inner in (0, 1, 2):
                rid = run_id_for(ci, inner, backbone, fold)
                manifest = f"{MNT}/runs/v0.3.0/{rid}/run_manifest.json"
                if not os.path.exists(manifest):
                    rc = call(
                        [PY, "-u", "src/v03_tblr.py", "--backbone", backbone,
                         "--ablation", "full_tblr", "--outer-fold", str(fold),
                         "--seed", "20260821", "--lr-mult", str(cfg["lr_mult"]),
                         "--weight-decay", cfg["weight_decay"],
                         "--aux-weight", str(cfg["aux"]),
                         "--mode", "tune-inner", "--inner-fold", str(inner),
                         "--device", args.device, "--run-id", rid],
                        log, env)
                    if rc != 0:
                        print(f"TUNING RUN FAILED: {rid} rc={rc}")
                        sys.exit(1)
                with open(manifest) as fh:
                    scores.append(json.load(fh)["best_val_ndcg10"])
            print(f"config {ci} {cfg}: mean inner-val NDCG@10 = "
                  f"{sum(scores)/3:.4f} {scores}")
        # select best config
        best_ci, best_score, best_scores = None, -1, None
        for ci, cfg in enumerate(configs()):
            scores = []
            ok = True
            for inner in (0, 1, 2):
                p = (f"{MNT}/runs/v0.3.0/"
                     f"{run_id_for(ci, inner, backbone, fold)}/run_manifest.json")
                if not os.path.exists(p):
                    ok = False
                    break
                with open(p) as fh:
                    scores.append(json.load(fh)["best_val_ndcg10"])
            if ok and sum(scores) / 3 > best_score:
                best_ci, best_score, best_scores = ci, sum(scores) / 3, scores
        cfg = configs()[best_ci]
        selection = {
            "backbone": backbone, "outer_fold": fold,
            "selected_config_index": best_ci, "config": cfg,
            "mean_inner_val_ndcg10": best_score,
            "per_inner_fold": best_scores,
            "dropout_mapping_for_non_aux": AUX_TO_DROPOUT,
            "grid": {"lr_mults": LR_MULTS, "wds": WDS, "auxs": AUXS},
        }
        with open(f"{tune_dir}/selection.json", "w") as fh:
            json.dump(selection, fh, indent=2)
        print("SELECTED:", json.dumps(selection, indent=2))

    # ---- phase 2: final runs ----
    if args.phase in ("final", "all"):
        with open(f"{tune_dir}/selection.json") as fh:
            sel = json.load(fh)
        cfg = sel["config"]
        for ablation in ABLATIONS:
            for seed in FINAL_SEEDS:
                rid = final_run_id(backbone, fold, ablation, seed)
                manifest = f"{MNT}/runs/v0.3.0/{rid}/run_manifest.json"
                if os.path.exists(manifest):
                    continue
                cmd = [PY, "-u", "src/v03_tblr.py", "--backbone", backbone,
                       "--ablation", ablation, "--outer-fold", str(fold),
                       "--seed", str(seed),
                       "--lr-mult", str(cfg["lr_mult"]),
                       "--weight-decay", cfg["weight_decay"],
                       "--mode", "final", "--device", args.device,
                       "--run-id", rid]
                if ablation in ("full_tblr", "tb_lambdarank"):
                    cmd += ["--aux-weight",
                            str(cfg["aux"] if ablation == "full_tblr" else 0.0)]
                    cmd += ["--dropout", "0.0"]
                elif ablation in ("tb_mse", "tb_dual", "rowwise_mse"):
                    cmd += ["--aux-weight", "0.0"]
                    cmd += ["--dropout", str(AUX_TO_DROPOUT[cfg["aux"]])]
                rc = call(cmd, log, env)
                if rc != 0:
                    print(f"FINAL RUN FAILED: {rid} rc={rc}")
                    sys.exit(1)
                print(f"final done: {rid}")
        print("ALL FINAL RUNS COMPLETE for "
              f"{backbone} fold {fold}")


if __name__ == "__main__":
    main()
