#!/bin/bash
# Sequential driver for the opensource LM identity runs on GPU3.
# Chained after the already-running UTR-LM adapter process: waits for it to
# finish, then runs RNA-FM and SpliceBERT-MS1024 (each: LR search + 3 seeds).
set -u
PY=/mnt/cunyuliu/ToeholdDesignBench/envs/beacon/bin/python
LOG=/mnt/cunyuliu/ToeholdDesignBench/logs/identity_opensource_seq.log
echo "[driver] start $(date)" >> $LOG

# ---- wait for UTR-LM adapter (started earlier) to finish ----
while pgrep -f "v03_beacon_identity.py --model UTR-LM-MRL" >/dev/null 2>&1; do
    sleep 600
done
echo "[driver] UTR-LM done $(date); launching RNA-FM" >> $LOG
cd /home/cunyuliu/ToeholdDesignBench
$PY src/v03_beacon_identity.py --model RNA-FM --lr-search \
    --seeds 666,20260821,20260822 --cuda-device 3 --execute >> $LOG 2>&1 \
    || echo "[driver] RNA-FM FAILED rc=$?" >> $LOG
echo "[driver] RNA-FM done rc=$? $(date); launching SpliceBERT-MS1024" >> $LOG
$PY src/v03_beacon_identity.py --model SpliceBERT-MS1024 --lr-search \
    --seeds 666,20260821,20260822 --cuda-device 3 --execute >> $LOG 2>&1 \
    || echo "[driver] SpliceBERT FAILED rc=$?" >> $LOG
echo "[driver] all opensource done $(date)" >> $LOG