#!/bin/bash
# BEACON-B512 identity line: waits until flash_attn is importable in the beacon
# env (source build finishing in background), then waits until GPU3 is free of
# the opensource adapter runs, then runs BEACON smoke + identity (official
# all_task.sh lr=1e-5, 3 seeds) on GPU3.
set -u
PY=/mnt/cunyuliu/ToeholdDesignBench/envs/beacon/bin/python
LOG=/mnt/cunyuliu/ToeholdDesignBench/logs/identity_beacon_seq.log
echo "[beacon-line] start $(date)" >> $LOG

# ---- wait for flash_attn to be importable ----
while ! $PY -c "import flash_attn" >/dev/null 2>&1; do
    sleep 300
done
echo "[beacon-line] flash_attn ready $(date)" >> $LOG

# ---- wait for GPU3 to be free of the opensource adapter/torch runs ----
while pgrep -f "v03_beacon_identity.py --model" >/dev/null 2>&1; do
    sleep 300
done
sleep 60
echo "[beacon-line] GPU3 free $(date); running BEACON smoke" >> $LOG

# ---- BEACON smoke (all 4 checkpoints incl. BEACON-B512) ----
cd /mnt/cunyuliu/ToeholdDesignBench/external_src/RNABenchmark
CUDA_VISIBLE_DEVICES=3 $PY /mnt/cunyuliu/ToeholdDesignBench/logs/smoke_beacon_lm.py >> $LOG 2>&1 \
    || echo "[beacon-line] smoke FAILED rc=$?" >> $LOG

# ---- BEACON-B512 identity (official lr=1e-5, 3 seeds) ----
cd /home/cunyuliu/ToeholdDesignBench
$PY src/v03_beacon_identity.py --model BEACON-B512 \
    --seeds 666,20260821,20260822 --cuda-device 3 --execute >> $LOG 2>&1 \
    || echo "[beacon-line] identity FAILED rc=$?" >> $LOG
echo "[beacon-line] done $(date)" >> $LOG