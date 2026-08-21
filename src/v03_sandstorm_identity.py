"""SANDSTORM official identity reproduction (contract §6 model panel).

Runs the official GARDN-SANDSTORM code (GA_util.create_SANDSTORM,
GA_util.contact_map PPMs, util.load_valeri_data) under the official protocol
from SANDSTORM/Predictor.ipynb cell 3:

- data: Toehold_Dataset_Final_2019-10-23.csv, rows with both ON and OFF labels
  (threshold=-1), sequences = switch+loop2+stem1+atg+stem2 (59 nt) + prepended
  C one-hot (60 nt);
- 3-fold CV: per fold, sklearn train_test_split(test_size=0.20) stratified by
  11-quantile KBinsDiscretizer bins of ON;
- Adam lr=1e-4, loss=mse, batch=64, 20 epochs;
- metrics: val MSE, ON/OFF R^2 and Spearman (mean over 3 folds).

Also trains the official Valeri CNN (GA_util.create_valeri_model) under the
same protocol for the Valeri-model identity reproduction.

Outputs: /mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/
sandstorm_identity_<ts>/identity_results.json (never overwritten).
"""
import json
import os
import sys
import time

import numpy as np

REPO = "/mnt/cunyuliu/ToeholdDesignBench/external_src/GARDN-SANDSTORM"
sys.path.insert(0, f"{REPO}/src")

DATA = "/mnt/cunyuliu/ToeholdDesignBench/raw/Toehold_Dataset_Final_2019-10-23.csv"
OUT_BASE = "/mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0"

import tensorflow as tf  # noqa: E402
import keras  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402
from sklearn.preprocessing import KBinsDiscretizer  # noqa: E402
from sklearn.metrics import r2_score  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

import util  # noqa: E402
import GA_util  # noqa: E402

# contract: no silent CPU fallback; keep TF on one GPU with memory growth
for gpu in tf.config.list_physical_devices("GPU"):
    tf.config.experimental.set_memory_growth(gpu, True)
print("TF", tf.__version__, "GPUs:", tf.config.list_physical_devices("GPU"))


def main():
    ts = time.strftime("%Y%m%dT%H%M%S")
    out_dir = f"{OUT_BASE}/sandstorm_identity_{ts}"
    if os.path.exists(out_dir):
        sys.exit(2)
    os.makedirs(out_dir)

    valeri_sequences, on, off = util.load_valeri_data(path=DATA, threshold=-1)
    print("sequences:", valeri_sequences.shape)
    on = on.values
    off = off.values

    est = KBinsDiscretizer(n_bins=11, encode="ordinal", strategy="quantile")
    est.fit(on.reshape(-1, 1))
    encoded_vals = est.transform(on.reshape(-1, 1))

    fold = 3
    results = {"sandstorm": [], "valeri": []}
    optimizer = keras.optimizers.Adam(learning_rate=0.0001)

    for i in range(fold):
        joint_model = GA_util.create_SANDSTORM(latent_dim=64, output_nodes=2)
        valeri_model = GA_util.create_valeri_model()

        switch_train, switch_test, on_train, on_test, off_train, off_test = \
            train_test_split(valeri_sequences, on, off, test_size=0.20,
                             stratify=encoded_vals)

        valeri_switch_train = tf.transpose(switch_train, (0, 2, 1))
        valeri_switch_test = tf.transpose(switch_test, (0, 2, 1))

        c = np.array([[0.0], [0.0], [1.0], [0.0]])
        c_train = np.stack((c,) * switch_train.shape[0], axis=0)
        c_test = np.stack((c,) * switch_test.shape[0], axis=0)
        switch_train_j = np.concatenate((c_train, switch_train), axis=2)
        switch_test_j = np.concatenate((c_test, switch_test), axis=2)
        ppm_train = GA_util.prototype_ppms_fast(switch_train_j)
        ppm_test = GA_util.prototype_ppms_fast(switch_test_j)

        # --- SANDSTORM (joint model) ---
        joint_model.compile(optimizer=optimizer, loss="mse")
        hist = joint_model.fit(
            [switch_train_j, ppm_train], [on_train, off_train], batch_size=64,
            validation_data=[[switch_test_j, ppm_test], [on_test, off_test]],
            epochs=20, verbose=2)
        mse = hist.history["val_loss"][-1]
        on_pred = joint_model.predict([switch_test_j, ppm_test])[0]
        off_pred = joint_model.predict([switch_test_j, ppm_test])[1]
        rec = {
            "fold": i, "val_mse": float(mse),
            "on_r2": float(r2_score(on_test, on_pred)),
            "off_r2": float(r2_score(off_test, off_pred)),
            "on_spearman": float(spearmanr(on_test, on_pred).statistic),
            "off_spearman": float(spearmanr(off_test, off_pred).statistic),
        }
        results["sandstorm"].append(rec)
        print("SANDSTORM fold", rec)

        # --- Valeri CNN ---
        valeri_model.compile(optimizer=optimizer, loss="mse")
        vhist = valeri_model.fit(
            valeri_switch_train, [on_train, off_train], batch_size=128,
            validation_data=[valeri_switch_test, [on_test, off_test]],
            epochs=20, verbose=2)
        vmse = vhist.history["val_loss"][-1]
        von_pred = valeri_model.predict(valeri_switch_test)[0]
        voff_pred = valeri_model.predict(valeri_switch_test)[1]
        vrec = {
            "fold": i, "val_mse": float(vmse),
            "on_r2": float(r2_score(on_test, von_pred)),
            "off_r2": float(r2_score(off_test, voff_pred)),
            "on_spearman": float(spearmanr(on_test, von_pred).statistic),
            "off_spearman": float(spearmanr(off_test, voff_pred).statistic),
        }
        results["valeri"].append(vrec)
        print("Valeri fold", vrec)

    summary = {}
    for model in ("sandstorm", "valeri"):
        for k in ("val_mse", "on_r2", "off_r2", "on_spearman", "off_spearman"):
            vals = [r[k] for r in results[model]]
            summary[f"{model}_{k}_mean"] = float(np.mean(vals))
            summary[f"{model}_{k}_sd"] = float(np.std(vals))
    summary["protocol"] = ("official Predictor.ipynb cell 3: 3-fold CV, "
                           "80/20 stratified by 11-quantile ON bins, Adam 1e-4, "
                           "mse, batch 64/128, 20 epochs")
    summary["per_fold"] = results
    summary["source_commit"] = os.popen(
        f"git -C {REPO} rev-parse HEAD").read().strip()
    with open(f"{out_dir}/identity_results.json", "w") as fh:
        json.dump(summary, fh, indent=2)
    print(json.dumps({k: v for k, v in summary.items()
                      if k not in ("per_fold",)}, indent=2))


if __name__ == "__main__":
    main()
