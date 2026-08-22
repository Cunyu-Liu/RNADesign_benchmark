"""Endgame orchestrator: the full post-RNAElectra analysis chain (contract
§9 Batch 4 close-out).

Checks RNAElectra family completion first; reports readiness without
running anything unless --execute is passed. Steps (idempotent where the
underlying scripts are; run directories are never overwritten):

  1. eval family (rnaelectra)          -- v03_eval_family.py
  2. protocol freeze audit (all)       -- v03_freeze_audit.py
  3. gate-6 sensitivity (all families) -- v03_sensitivity.py
  4. transfer model (rnaelectra)       -- v03_transfer.py --device cuda:N
  5. crowdsourced track (3 backbones)  -- v03_crowd.py
  6. VISTA mCherry (3 transfers)       -- v03_vista.py
  7. figures (auto 3 families)         -- v03_figures.py
  8. number audit                      -- v03_number_audit.py
  9. review pack refresh               -- v03_review_pack.py

Manual steps after this script: paper §7/§8/§12 fills, three-reviewer
sign-off, editor synthesis (contract requires human-judgment steps to stay
human-driven).

Usage:
  python src/v03_endgame.py                 # readiness report only
  python src/v03_endgame.py --execute --cuda-device 3
"""
import argparse
import glob
import os
import subprocess
import sys
import time

PROJ = "/home/cunyuliu/ToeholdDesignBench"
BASE = "/mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0"
PY = "/home/cunyuliu/miniconda3/envs/toeholdbench/bin/python"
BIOPHYS_EXTRA = (f"{BASE}/biophys_20260822T023805/predictions.parquet")


def rnaelectra_status():
    n_tune = len(glob.glob(
        f"{BASE}/tune_rnaelectra_f?_c??_i?/run_manifest.json"))
    n_sel = len(glob.glob(
        f"{BASE}/tune_rnaelectra_f?/selection.json"))
    n_final = len(glob.glob(
        f"{BASE}/final_rnaelectra_f?_*_s20*/run_manifest.json"))
    return {
        "tune": (n_tune, 180),
        "selections": (n_sel, 5),
        "finals": (n_final, 125),
        "complete": (n_tune == 180 and n_sel == 5 and n_final == 125),
    }


def run(label, cmd, env_extra=None, check=True):
    print(f"\n=== {label} ===")
    print(" ".join(cmd))
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    r = subprocess.run(cmd, cwd=PROJ, env=env)
    if check and r.returncode != 0:
        print(f"STEP FAILED: {label} (rc={r.returncode})")
        sys.exit(1)
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true",
                    help="run the chain; default is readiness report only")
    ap.add_argument("--cuda-device", default="3",
                    help="physical GPU for the transfer training step")
    args = ap.parse_args()

    st = rnaelectra_status()
    print(f"RNAElectra family: tune {st['tune'][0]}/{st['tune'][1]}, "
          f"selections {st['selections'][0]}/{st['selections'][1]}, "
          f"finals {st['finals'][0]}/{st['finals'][1]} -> "
          f"{'COMPLETE' if st['complete'] else 'IN FLIGHT'}")

    if not st["complete"]:
        print("\nNot ready. Re-run when the family completes "
              "(the watchdog advances folds automatically).")
        return 0
    if not args.execute:
        print("\nFamily complete. Re-run with --execute to run the chain.")
        return 0

    gpu_env = {"CUDA_DEVICE_ORDER": "PCI_BUS_ID",
               "CUDA_VISIBLE_DEVICES": args.cuda_device}
    t0 = time.time()

    run("1/9 rnaelectra family evaluation",
        [PY, "-u", "src/v03_eval_family.py", "--backbone", "rnaelectra",
         "--extra", BIOPHYS_EXTRA])
    run("2/9 protocol freeze audit (all families)",
        [PY, "-u", "src/v03_freeze_audit.py"])
    run("3/9 gate-6 sensitivity (all families)",
        [PY, "-u", "src/v03_sensitivity.py"])
    run("4/9 rnaelectra transfer training (5 frozen seeds)",
        [PY, "-u", "src/v03_transfer.py", "--backbone", "rnaelectra",
         "--run-id", "transfer_rnaelectra", "--device", "cuda:0"],
        env_extra=gpu_env)
    run("5/9 crowdsourced track (cnn60 sandstorm rnaelectra)",
        [PY, "-u", "src/v03_crowd.py", "--backbones", "cnn60", "sandstorm",
         "rnaelectra"], env_extra=gpu_env)
    run("6/9 VISTA mCherry (3 transfer families)",
        [PY, "-u", "src/v03_vista.py", "--transfer-run", "transfer_cnn60",
         "transfer_sandstorm", "transfer_rnaelectra"],
        env_extra=gpu_env)
    run("7/9 figures (auto families)",
        [PY, "-u", "src/v03_figures.py"])
    rc = run("8/9 manuscript number audit",
             [PY, "-u", "src/v03_number_audit.py"], check=False)
    if rc != 0:
        print("NOTE: number audit flagged missing numbers -- expected until "
              "the RNAElectra rows are added to the manuscript §7/§8/§12; "
              "fill the paper, then re-run the audit.")
    run("9/9 review pack refresh",
        [PY, "-u", "src/v03_review_pack.py"])

    print(f"\nENDGAME CHAIN DONE in {(time.time() - t0) / 60:.1f} min")
    print("Remaining manual steps: paper fills, three-reviewer sign-off, "
          "editor synthesis, outputs re-assembly "
          "(scripts/assemble_outputs.py).")


if __name__ == "__main__":
    main()
