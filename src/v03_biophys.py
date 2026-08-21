"""Corrected biophysical baselines (contract §8) + analytic/local baselines.

- Preprocessing fitted ONLY on the training fold (outer-train for final runs,
  outer-train-minus-inner-fold for tuning): salis log1p -> standardize; MFE/GC
  standardized; missing values -> train median + missingness indicator; Salis
  never backfills to MFE.
- LightGBM variants: biophysics-only, sequence-only (4-mer counts), combined;
  target-balanced training via per-record weights 1/n_records(target); 12
  pre-declared configs per variant tuned by 3-fold inner CV on outer-train;
  5 final seeds.
- Analytic baselines: GC scorer (direction fitted on outer-train only) and
  corrected thermodynamic scorer (ridge on standardized biophysics fitted on
  outer-train).

Emits predictions parquet per method in contract §10 schema under
/mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/biophys_<ts>/.
"""
import json
import os
import sys
import time
from itertools import product

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

PROJ = "/home/cunyuliu/ToeholdDesignBench"
MNT = "/mnt/cunyuliu/ToeholdDesignBench"
REG = f"{MNT}/runs/v0.3.0/registry_v3"
sys.path.insert(0, f"{PROJ}/src")
from toeholdbench.evaluator import expected_ndcg  # noqa: E402

BIO = ["salis_onoff", "mfe_switch_off", "mfe_switch_on", "mfe_trigger",
       "gc_trigger"]
SEEDS = [20260821, 20260822, 20260823, 20260824, 20260825]
CONFIGS = [
    {"num_leaves": a, "learning_rate": b, "min_child_samples": c}
    for a in (31, 63) for b in (0.05, 0.1) for c in (20, 100)
][:12]
VARIANTS = ["lightgbm-biophys", "lightgbm-seq", "lightgbm-combined"]


def kmer_features(seqs, k=4):
    table = {"".join(p): i for i, p in enumerate(product("ACGT", repeat=k))}
    X = np.zeros((len(seqs), len(table)), dtype=np.float32)
    for i, s in enumerate(seqs):
        s = str(s).upper()
        for j in range(len(s) - k + 1):
            idx = table.get(s[j:j + k])
            if idx is not None:
                X[i, idx] += 1
    return X


def fit_preprocess(train_df):
    stats = {}
    for c in BIO:
        v = train_df[c].astype(float)
        if c == "salis_onoff":
            v = np.log1p(v.clip(lower=0))
        stats[c] = {"mu": float(v.mean()), "sd": float(v.std() + 1e-12),
                    "median": float(v.median()),
                    "log1p": c == "salis_onoff"}
    return stats


def apply_preprocess(df, stats):
    cols = {}
    for c in BIO:
        v = df[c].astype(float)
        st = stats[c]
        miss = v.isna().values
        if st["log1p"]:
            v = np.log1p(v.clip(lower=0))
        v = v.fillna(st["median"])
        cols[c] = ((v - st["mu"]) / st["sd"]).values.astype(np.float32)
        cols[f"{c}_missing"] = miss.astype(np.float32)
    return np.column_stack([cols[c] for c in cols])


def mean_ndcg(target_ids, y, scores):
    df = pd.DataFrame({"tid": target_ids, "y": y, "s": scores})
    vals = [expected_ndcg(sub["s"].values, sub["y"].values, 10)
            for _, sub in df.groupby("tid")]
    return float(np.mean(vals))


def main():
    ts = time.strftime("%Y%m%dT%H%M%S")
    out_dir = f"{MNT}/runs/v0.3.0/biophys_{ts}"
    os.makedirs(out_dir, exist_ok=False)

    canon = pd.read_parquet(f"{REG}/canonical_manifest.parquet")
    rec = pd.read_parquet(f"{MNT}/processed/canonical_records.parquet")
    df = canon[canon["eligibility_status"] == "eligible_ranking"].copy()
    df = df.merge(rec[["record_id"] + BIO], on="record_id", how="left")
    with open(f"{REG}/split_manifest.json") as fh:
        sm = json.load(fh)
    df["inner_fold"] = df["target_id"].map(sm["inner_fold_of_target"])
    df = df.reset_index(drop=True)
    print(f"eligible rows: {len(df)}")

    print("building 4-mer features (trigger + switch)...")
    seqX = np.hstack([kmer_features(df["trigger_sequence"].values),
                      kmer_features(df["switch_or_construct_sequence"].values)
                      ]).astype(np.float32)
    print("seq features:", seqX.shape)

    import lightgbm as lgb

    def feat_matrix(name, rows, bio_arr):
        if name == "lightgbm-biophys":
            return bio_arr
        if name == "lightgbm-seq":
            return seqX[rows]
        return np.hstack([bio_arr, seqX[rows]])

    all_preds = []
    fold_records = []
    for fold in range(5):
        train_df = df[df["outer_fold"] != fold]
        test_df = df[df["outer_fold"] == fold]
        tr_rows = train_df.index.values
        te_rows = test_df.index.values
        stats = fit_preprocess(train_df)
        bio_train = apply_preprocess(train_df, stats)
        bio_test = apply_preprocess(test_df, stats)
        y_train = (train_df["label_on"] - train_df["label_off"]).values
        w_train = (1.0 / train_df.groupby("target_id")["record_id"].transform(
            "count")).values

        fold_info = {"fold": fold, "selected_configs": {}, "inner_val": {}}
        for name in VARIANTS:
            # 12-config inner-CV tuning per variant (train-fold-only preprocessing)
            best_cfg, best_score = None, -1
            for cfg in CONFIGS:
                scores = []
                for ifold in (0, 1, 2):
                    va = train_df[train_df["inner_fold"] == ifold]
                    tr = train_df[train_df["inner_fold"] != ifold]
                    if len(va) == 0 or len(tr) == 0:
                        continue
                    st_i = fit_preprocess(tr)
                    btr = apply_preprocess(tr, st_i)
                    bva = apply_preprocess(va, st_i)
                    Xtr = feat_matrix(name, tr.index.values, btr)
                    Xva = feat_matrix(name, va.index.values, bva)
                    ytr = (tr["label_on"] - tr["label_off"]).values
                    yva = (va["label_on"] - va["label_off"]).values
                    wtr = (1.0 / tr.groupby("target_id")["record_id"]
                           .transform("count")).values
                    m = lgb.LGBMRegressor(n_estimators=300, verbose=-1,
                                          random_state=20260821, **cfg)
                    m.fit(Xtr, ytr, sample_weight=wtr)
                    sc = m.predict(Xva)
                    scores.append(mean_ndcg(va["target_id"].values, yva, sc))
                ms = float(np.mean(scores))
                if ms > best_score:
                    best_score, best_cfg = ms, cfg
            fold_info["selected_configs"][name] = best_cfg
            fold_info["inner_val"][name] = best_score

            # final: 5 seeds on the full outer-train
            Xtr = feat_matrix(name, tr_rows, bio_train)
            Xte = feat_matrix(name, te_rows, bio_test)
            for seed in SEEDS:
                m = lgb.LGBMRegressor(n_estimators=300, verbose=-1,
                                      random_state=seed, **best_cfg)
                m.fit(Xtr, y_train, sample_weight=w_train)
                sc = m.predict(Xte)
                all_preds.append(pd.DataFrame({
                    "run_id": f"biophys_{ts}", "track_id": "canonical_v03",
                    "fold": fold, "target_id": test_df["target_id"].values,
                    "target_cluster_id": test_df["target_cluster_id"].values,
                    "record_id": test_df["record_id"].values,
                    "method_id": name, "seed": seed, "score": sc}))
            print(f"fold {fold} {name}: cfg={best_cfg} "
                  f"inner NDCG={best_score:.4f}")

        # analytic baselines (train-fitted only)
        gc_tr = train_df["gc_trigger"].values
        gc_corr = np.corrcoef(np.nan_to_num(gc_tr), y_train)[0, 1]
        sign = -1.0 if gc_corr >= 0 else 1.0
        gc_score = sign * np.nan_to_num(test_df["gc_trigger"].values)
        all_preds.append(pd.DataFrame({
            "run_id": f"biophys_{ts}", "track_id": "canonical_v03",
            "fold": fold, "target_id": test_df["target_id"].values,
            "target_cluster_id": test_df["target_cluster_id"].values,
            "record_id": test_df["record_id"].values,
            "method_id": "gc-baseline", "seed": 20260821, "score": gc_score}))
        ridge = Ridge(alpha=1.0)
        ridge.fit(bio_train, y_train, sample_weight=w_train)
        th_score = ridge.predict(bio_test)
        all_preds.append(pd.DataFrame({
            "run_id": f"biophys_{ts}", "track_id": "canonical_v03",
            "fold": fold, "target_id": test_df["target_id"].values,
            "target_cluster_id": test_df["target_cluster_id"].values,
            "record_id": test_df["record_id"].values,
            "method_id": "thermo-scorer", "seed": 20260821,
            "score": th_score}))
        fold_info["gc_train_corr"] = float(gc_corr)
        fold_records.append(fold_info)

    preds = pd.concat(all_preds, ignore_index=True)
    preds.to_parquet(f"{out_dir}/predictions.parquet", index=False)
    with open(f"{out_dir}/run_manifest.json", "w") as fh:
        json.dump({"methods": sorted(preds["method_id"].unique()),
                   "n_predictions": len(preds), "folds": fold_records,
                   "config_grid": CONFIGS,
                   "preprocessing": ("train-fold-only; salis log1p+standardize; "
                                     "median impute + missingness indicator; "
                                     "salis never backfills to MFE")}, fh,
                  indent=2)
    print(f"wrote {len(preds)} predictions to {out_dir}")


if __name__ == "__main__":
    main()
