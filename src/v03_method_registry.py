"""Method registry builder (contract §10).

Emits /mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/method_registry.csv with
one row per method in the frozen panel, including source commits, checkpoint
locations, official/adapted status, score direction, and dataset exposure.
"""
import json
import os
import subprocess

MNT = "/mnt/cunyuliu/ToeholdDesignBench"
OUT = f"{MNT}/runs/v0.3.0/method_registry.json"


def git_commit(path):
    try:
        return subprocess.run(["git", "-C", path, "rev-parse", "HEAD"],
                              capture_output=True, text=True,
                              timeout=10).stdout.strip()
    except Exception:
        return None


def main():
    ext = f"{MNT}/external_src"
    methods = [
        # ---- analytic / local ----
        {"method_id": "exact-random", "family": "analytic",
         "official_source": "internal (toeholdbench evaluator)",
         "source_commit": git_commit("/home/cunyuliu/ToeholdDesignBench"),
         "checkpoint": None, "official_or_adapted": "internal",
         "information_regime": "analytic", "training_mode": "none",
         "objective": "uniform random ordering (analytic expectation)",
         "original_score_direction": "n/a",
         "benchmark_score_transform": "analytic per-target expectation",
         "parameter_count": 0, "tuning_budget": 0, "seeds": [],
         "environment": "toeholdbench",
         "dataset_exposure": "none"},
        {"method_id": "gc-baseline", "family": "analytic",
         "official_source": "internal", "source_commit": None,
         "checkpoint": None, "official_or_adapted": "internal",
         "information_regime": "analytic", "training_mode": "none",
         "objective": "GC content (direction fitted on outer-train)",
         "original_score_direction": "higher_better",
         "benchmark_score_transform": "sign fitted on train fold",
         "parameter_count": 1, "tuning_budget": 0, "seeds": [20260821],
         "environment": "toeholdbench", "dataset_exposure": "train folds only"},
        {"method_id": "thermo-scorer", "family": "analytic",
         "official_source": "internal", "source_commit": None,
         "checkpoint": None, "official_or_adapted": "internal",
         "information_regime": "analytic", "training_mode": "ridge on train",
         "objective": "ridge regression of ON-OFF on standardized biophysics",
         "original_score_direction": "higher_better",
         "benchmark_score_transform": "identity",
         "parameter_count": 10, "tuning_budget": 0, "seeds": [20260821],
         "environment": "toeholdbench",
         "dataset_exposure": "train folds only (preprocessing train-only)"},
        {"method_id": "lightgbm-biophys", "family": "biophysical",
         "official_source": "internal", "source_commit": None,
         "checkpoint": None, "official_or_adapted": "internal",
         "information_regime": "analytic/local",
         "training_mode": "target-balanced weights; 12-config inner CV",
         "objective": "regression of ON-OFF (biophysics features only)",
         "original_score_direction": "higher_better",
         "benchmark_score_transform": "identity",
         "parameter_count": "gbdt", "tuning_budget": 12,
         "seeds": [20260821, 20260822, 20260823, 20260824, 20260825],
         "environment": "toeholdbench",
         "dataset_exposure": "train folds only"},
        {"method_id": "lightgbm-seq", "family": "sequence",
         "official_source": "internal", "source_commit": None,
         "checkpoint": None, "official_or_adapted": "internal",
         "information_regime": "analytic/local",
         "training_mode": "target-balanced weights; 12-config inner CV",
         "objective": "regression of ON-OFF (4-mer features only)",
         "original_score_direction": "higher_better",
         "benchmark_score_transform": "identity",
         "parameter_count": "gbdt", "tuning_budget": 12,
         "seeds": [20260821, 20260822, 20260823, 20260824, 20260825],
         "environment": "toeholdbench",
         "dataset_exposure": "train folds only"},
        {"method_id": "lightgbm-combined", "family": "biophysical+sequence",
         "official_source": "internal", "source_commit": None,
         "checkpoint": None, "official_or_adapted": "internal",
         "information_regime": "analytic/local",
         "training_mode": "target-balanced weights; 12-config inner CV",
         "objective": "regression of ON-OFF (biophysics + 4-mer)",
         "original_score_direction": "higher_better",
         "benchmark_score_transform": "identity",
         "parameter_count": "gbdt", "tuning_budget": 12,
         "seeds": [20260821, 20260822, 20260823, 20260824, 20260825],
         "environment": "toeholdbench",
         "dataset_exposure": "train folds only"},
        # ---- TBLR (ours) + matched ablations ----
        {"method_id": "cnn60/full_tblr", "family": "TBLR",
         "official_source": "internal", "source_commit": None,
         "checkpoint": None, "official_or_adapted": "internal",
         "information_regime": "construct",
         "training_mode": "target-balanced; 12-config x 3-inner-fold CV",
         "objective": "LambdaRank@10 (delta-NDCG) + aux Huber(ON,OFF)",
         "original_score_direction": "higher_better",
         "benchmark_score_transform": "identity",
         "parameter_count": 38179, "tuning_budget": 12,
         "seeds": [20260821, 20260822, 20260823, 20260824, 20260825],
         "environment": "toeholdbench",
         "dataset_exposure": "canonical train folds only"},
        {"method_id": "cnn60/tb_mse", "family": "TBLR-ablation",
         "official_source": "internal", "source_commit": None,
         "checkpoint": None, "official_or_adapted": "internal",
         "information_regime": "construct",
         "training_mode": "target-balanced (matched pointwise comparator)",
         "objective": "pointwise MSE on ON-OFF",
         "original_score_direction": "higher_better",
         "benchmark_score_transform": "identity",
         "parameter_count": 38179, "tuning_budget": 12,
         "seeds": [20260821, 20260822, 20260823, 20260824, 20260825],
         "environment": "toeholdbench",
         "dataset_exposure": "canonical train folds only"},
        {"method_id": "cnn60/rowwise_mse", "family": "TBLR-ablation",
         "official_source": "internal", "source_commit": None,
         "checkpoint": None, "official_or_adapted": "internal",
         "information_regime": "construct",
         "training_mode": "legacy row-weighted minibatches",
         "objective": "row-weighted pointwise MSE (v0.2.1 legacy protocol)",
         "original_score_direction": "higher_better",
         "benchmark_score_transform": "identity",
         "parameter_count": 38179, "tuning_budget": 12,
         "seeds": [20260821, 20260822, 20260823, 20260824, 20260825],
         "environment": "toeholdbench",
         "dataset_exposure": "canonical train folds only"},
        {"method_id": "cnn60/tb_dual", "family": "TBLR-ablation",
         "official_source": "internal", "source_commit": None,
         "checkpoint": None, "official_or_adapted": "internal",
         "information_regime": "construct",
         "training_mode": "target-balanced",
         "objective": "dual Huber(ON)+Huber(OFF); score = ON-OFF",
         "original_score_direction": "higher_better",
         "benchmark_score_transform": "predicted_on - predicted_off",
         "parameter_count": 38179, "tuning_budget": 12,
         "seeds": [20260821, 20260822, 20260823, 20260824, 20260825],
         "environment": "toeholdbench",
         "dataset_exposure": "canonical train folds only"},
        {"method_id": "cnn60/tb_lambdarank", "family": "TBLR-ablation",
         "official_source": "internal", "source_commit": None,
         "checkpoint": None, "official_or_adapted": "internal",
         "information_regime": "construct", "training_mode": "target-balanced",
         "objective": "LambdaRank@10 only (aux weight 0)",
         "original_score_direction": "higher_better",
         "benchmark_score_transform": "identity",
         "parameter_count": 38179, "tuning_budget": 12,
         "seeds": [20260821, 20260822, 20260823, 20260824, 20260825],
         "environment": "toeholdbench",
         "dataset_exposure": "canonical train folds only"},
        # ---- official SANDSTORM (PyTorch port + official Keras identity) ----
        {"method_id": "sandstorm/full_tblr", "family": "TBLR",
         "official_source": "AlexGreenLab/GARDN-SANDSTORM",
         "source_commit": git_commit(f"{ext}/GARDN-SANDSTORM"),
         "checkpoint": None,
         "official_or_adapted": "pytorch port of official architecture",
         "information_regime": "construct+prototype-PPM",
         "training_mode": "target-balanced; 12-config x 3-inner-fold CV",
         "objective": "LambdaRank@10 + aux Huber(ON,OFF)",
         "original_score_direction": "higher_better",
         "benchmark_score_transform": "identity",
         "parameter_count": "see run manifest", "tuning_budget": 12,
         "seeds": [20260821, 20260822, 20260823, 20260824, 20260825],
         "environment": "toeholdbench",
         "dataset_exposure": "canonical train folds only"},
        {"method_id": "sandstorm/tb_mse", "family": "TBLR-ablation",
         "official_source": "AlexGreenLab/GARDN-SANDSTORM",
         "source_commit": git_commit(f"{ext}/GARDN-SANDSTORM"),
         "checkpoint": None,
         "official_or_adapted": "pytorch port of official architecture",
         "information_regime": "construct+prototype-PPM",
         "training_mode": "target-balanced (matched pointwise comparator)",
         "objective": "pointwise MSE on ON-OFF",
         "original_score_direction": "higher_better",
         "benchmark_score_transform": "identity",
         "parameter_count": "see run manifest", "tuning_budget": 12,
         "seeds": [20260821, 20260822, 20260823, 20260824, 20260825],
         "environment": "toeholdbench",
         "dataset_exposure": "canonical train folds only"},
        {"method_id": "SANDSTORM-official", "family": "official baseline",
         "official_source": "AlexGreenLab/GARDN-SANDSTORM (official Keras)",
         "source_commit": git_commit(f"{ext}/GARDN-SANDSTORM"),
         "checkpoint": None,
         "official_or_adapted": "official_reproduction (pending identity run)",
         "information_regime": "construct+prototype-PPM",
         "training_mode": "official protocol (3-fold CV, 80/20 stratified)",
         "objective": "MSE on ON,OFF (dual output)",
         "original_score_direction": "higher_better",
         "benchmark_score_transform": "predicted_on - predicted_off",
         "parameter_count": "official", "tuning_budget": 0,
         "seeds": [], "environment": "sandstorm_official",
         "dataset_exposure": "official Valeri dataset (identity reproduction)"},
        {"method_id": "Valeri-CNN-official", "family": "official baseline",
         "official_source": ("AlexGreenLab/GARDN-SANDSTORM "
                             "(GA_util.create_valeri_model, Valeri et al.)"),
         "source_commit": git_commit(f"{ext}/GARDN-SANDSTORM"),
         "checkpoint": None,
         "official_or_adapted": "official_reproduction (pending identity run)",
         "information_regime": "construct",
         "training_mode": "official protocol",
         "objective": "MSE on ON,OFF (dual output)",
         "original_score_direction": "higher_better",
         "benchmark_score_transform": "predicted_on - predicted_off",
         "parameter_count": "official", "tuning_budget": 0,
         "seeds": [], "environment": "sandstorm_official",
         "dataset_exposure": "official Valeri dataset (identity reproduction)"},
        # ---- BEACON segment masking ----
        {"method_id": "beacon-mask/*", "family": "input ablation",
         "official_source": "BEACON (NeurIPS 2024) constructs; internal model",
         "source_commit": None, "checkpoint": None,
         "official_or_adapted": "internal fixed-capacity model",
         "information_regime": "construct-148",
         "training_mode": "target-balanced; fixed capacity across variants",
         "objective": "pointwise MSE on ON-OFF with segment masks",
         "original_score_direction": "higher_better",
         "benchmark_score_transform": "identity",
         "parameter_count": "fixed (see run manifest)", "tuning_budget": 0,
         "seeds": [20260821], "environment": "toeholdbench",
         "dataset_exposure": "BEACON label view train folds only"},
        # ---- RNAElectra ----
        {"method_id": "rnaelectra/full_tblr", "family": "TBLR",
         "official_source": "FreakingPotato/RNAElectra (preprint)",
         "source_commit": "hf:FreakingPotato/RNAElectra",
         "checkpoint": f"{ext}/rnaelectra",
         "official_or_adapted": "official backbone + task-head adaptation",
         "information_regime": "construct",
         "training_mode": "target-balanced; 12-config x 3-inner-fold CV",
         "objective": "LambdaRank@10 + aux Huber(ON,OFF)",
         "original_score_direction": "higher_better",
         "benchmark_score_transform": "identity",
         "parameter_count": "see run manifest", "tuning_budget": 12,
         "seeds": [20260821, 20260822, 20260823, 20260824, 20260825],
         "environment": "toeholdbench",
         "dataset_exposure": "canonical train folds only; preprint noted"},
        {"method_id": "rnaelectra/tb_mse", "family": "TBLR-ablation",
         "official_source": "FreakingPotato/RNAElectra (preprint)",
         "source_commit": "hf:FreakingPotato/RNAElectra",
         "checkpoint": f"{ext}/rnaelectra",
         "official_or_adapted": "official backbone + task-head adaptation",
         "information_regime": "construct",
         "training_mode": "target-balanced (matched pointwise comparator)",
         "objective": "pointwise MSE on ON-OFF",
         "original_score_direction": "higher_better",
         "benchmark_score_transform": "identity",
         "parameter_count": "see run manifest", "tuning_budget": 12,
         "seeds": [20260821, 20260822, 20260823, 20260824, 20260825],
         "environment": "toeholdbench",
         "dataset_exposure": "canonical train folds only; preprint noted"},
        # ---- VISTA external track (completed) ----
        {"method_id": "vista-tsgen2", "family": "official external",
         "official_source": ("AlexGreenLab/vista; tsgen2 ranking column of "
                             "mCH_on_off_rank.xlsx (paper Fig 5D convention: "
                             "rank 1 = best)"),
         "source_commit": git_commit(f"{ext}/vista"),
         "checkpoint": None, "official_or_adapted": "official_reproduction",
         "information_regime": "external native (36-nt sites)",
         "training_mode": "none (precomputed official ranking)",
         "objective": "official tsgen2 ranking",
         "original_score_direction": "higher_better (score=-rank)",
         "benchmark_score_transform": "score = -rank",
         "parameter_count": "official", "tuning_budget": 0,
         "seeds": [], "environment": "toeholdbench",
         "dataset_exposure": "VISTA paper internal (not independent for "
                             "VISTA; baseline on its own track)"},
        {"method_id": "vista-plsda-full", "family": "official external",
         "official_source": ("AlexGreenLab/vista; PLS-DA FULL Rank ONOFF "
                             "column (official all_trained_model_params.pkl "
                             "models)"),
         "source_commit": git_commit(f"{ext}/vista"),
         "checkpoint": f"{ext}/vista/toehold-VISTA/all_trained_model_params.pkl",
         "official_or_adapted": "official_reproduction",
         "information_regime": "external native (engineered features)",
         "training_mode": "none (precomputed official ranking)",
         "objective": "PLS-DA ON/OFF Full ranking",
         "original_score_direction": "higher_better (score=-rank)",
         "benchmark_score_transform": "score = -rank",
         "parameter_count": "official", "tuning_budget": 0,
         "seeds": [], "environment": "toeholdbench",
         "dataset_exposure": "VISTA paper internal"},
        {"method_id": "transfer-cnn60/full_tblr", "family": "TBLR transfer",
         "official_source": "internal (canonical-trained transfer)",
         "source_commit": None,
         "checkpoint": "runs/v0.3.0/transfer_cnn60/transfer_s*.pt",
         "official_or_adapted": "internal",
         "information_regime": "external native (trigger30+switch30 "
                                "reconstructed from 36-nt sites)",
         "training_mode": ("full-canonical training; config from "
                           "full-canonical inner-CV aggregation; 5 frozen "
                           "seeds; no external labels read"),
         "objective": "TBLR full objective (canonical)",
         "original_score_direction": "higher_better",
         "benchmark_score_transform": "identity",
         "parameter_count": 38179, "tuning_budget": 12,
         "seeds": [20260821, 20260822, 20260823, 20260824, 20260825],
         "environment": "toeholdbench",
         "dataset_exposure": "canonical only (VISTA labels never touched "
                             "before final scoring)"},
        {"method_id": "transfer-sandstorm/full_tblr", "family": "TBLR transfer",
         "official_source": "internal (canonical-trained transfer)",
         "source_commit": None,
         "checkpoint": "runs/v0.3.0/transfer_sandstorm/transfer_s*.pt",
         "official_or_adapted": "internal",
         "information_regime": ("external native (construct59 window from "
                                "T7-suffixed switches / sensor prefix for "
                                "crowdsourced regulators)"),
         "training_mode": ("full-canonical training; config from "
                           "full-canonical inner-CV aggregation (c08: "
                           "lr_mult 2.0, wd 0, aux 0.1); 5 frozen seeds; no "
                           "external labels read"),
         "objective": "TBLR full objective (canonical)",
         "original_score_direction": "higher_better",
         "benchmark_score_transform": "identity",
         "parameter_count": 19083, "tuning_budget": 12,
         "seeds": [20260821, 20260822, 20260823, 20260824, 20260825],
         "environment": "toeholdbench",
         "dataset_exposure": ("canonical only; external exposure check: "
                              "sensor/trigger/30nt-prefix overlap 0 of 100 "
                              "on crowdsourced track")},
        # ---- pending assets (blocked; see blockers.json) ----
        {"method_id": "BEACON-B512", "family": "2024 benchmark LM",
         "official_source": "terry-r123/RNABenchmark",
         "source_commit": git_commit(f"{ext}/RNABenchmark"),
         "checkpoint": "BLOCKED: Google Drive inaccessible from server",
         "official_or_adapted": "pending asset",
         "information_regime": "pretrained RNA LM",
         "training_mode": "official fine-tuning protocol",
         "objective": "official", "original_score_direction": "higher_better",
         "benchmark_score_transform": "identity",
         "parameter_count": "official", "tuning_budget": "official",
         "seeds": [], "environment": "beacon",
         "dataset_exposure": "planned: official BEACON splits (identity)"},
        {"method_id": "SpliceBERT-MS1024", "family": "2024 benchmark LM",
         "official_source": "outlets/SpliceBERT.1024nt via terry-r123/RNABenchmark",
         "source_commit": git_commit(f"{ext}/RNABenchmark"),
         "checkpoint": ("BLOCKED: HF blocked, mirror requires auth, Drive "
                        "inaccessible"),
         "official_or_adapted": "pending asset",
         "information_regime": "pretrained RNA LM",
         "training_mode": "official fine-tuning protocol",
         "objective": "official", "original_score_direction": "higher_better",
         "benchmark_score_transform": "identity",
         "parameter_count": "official", "tuning_budget": "official",
         "seeds": [], "environment": "beacon",
         "dataset_exposure": "planned: official BEACON splits (identity)"},
        {"method_id": "RNA-FM", "family": "2024 benchmark LM",
         "official_source": "terry-r123/RNABenchmark",
         "source_commit": git_commit(f"{ext}/RNABenchmark"),
         "checkpoint": ("BLOCKED: HF blocked, mirror requires auth, Drive "
                        "inaccessible"),
         "official_or_adapted": "pending asset",
         "information_regime": "pretrained RNA LM",
         "training_mode": "official fine-tuning protocol",
         "objective": "official", "original_score_direction": "higher_better",
         "benchmark_score_transform": "identity",
         "parameter_count": "official", "tuning_budget": "official",
         "seeds": [], "environment": "beacon",
         "dataset_exposure": "planned: official BEACON splits (identity)"},
        {"method_id": "UTR-LM-MRL", "family": "2024 benchmark LM",
         "official_source": "terry-r123/RNABenchmark",
         "source_commit": git_commit(f"{ext}/RNABenchmark"),
         "checkpoint": ("BLOCKED: HF blocked, mirror requires auth, Drive "
                        "inaccessible"),
         "official_or_adapted": "pending asset",
         "information_regime": "pretrained RNA LM",
         "training_mode": "official fine-tuning protocol",
         "objective": "official", "original_score_direction": "higher_better",
         "benchmark_score_transform": "identity",
         "parameter_count": "official", "tuning_budget": "official",
         "seeds": [], "environment": "beacon",
         "dataset_exposure": "planned: official BEACON splits (identity)"},
    ]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump({"methods": methods,
                   "blockers": {
                       "BEACON LM checkpoints": (
                           "Google Drive blocked from server; HF blocked; "
                           "hf-mirror serves only cached repos anonymously. "
                           "Need user-provided checkpoint files or an HF "
                           "token (HF_TOKEN env) to authenticate the mirror "
                           "proxy."),
                       "SANDSTORM released designs (Zenodo 15058435)": (
                           "zenodo.org blocked from server (000). Needed only "
                           "for the exposure-aware architecture description "
                           "of GARDN/SANDSTORM published designs (Batch 4 "
                           "descriptive item). NOTE: Toehold-VISTA NAR 2026 "
                           "supplementary (SARS-CoV selection groups) was "
                           "fetched and analyzed 2026-08-22 "
                           "(scripts/download_vista_nar.py); the GARDN "
                           "design dump itself remains unavailable."),
                       "Crowdsourced 100-regulator data": (
                           "RESOLVED 2026-08-22: supplementary media-1.xlsx "
                           "fetched directly from PMC13370501 with the "
                           "proof-of-work challenge solved "
                           "(scripts/download_crowdsourced.py); zero "
                           "exposure vs canonical registry verified."),
                       "NUPACK 4": (
                           "Not installed anywhere on the server. SANDSTORM "
                           "identity reproduction uses the official prototype "
                           "PPM path (no NUPACK); NUPACK only needed if we "
                           "add true ensemble-PPM features per contract §6 "
                           "(user to provide legal install).")}}, fh, indent=2)
    print(f"wrote {len(methods)} methods to {OUT}")


if __name__ == "__main__":
    main()
