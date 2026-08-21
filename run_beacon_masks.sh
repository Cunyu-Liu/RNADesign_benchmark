#!/usr/bin/env bash
# BEACON fixed-capacity segment masking: 7 variants on fold 0 (sequential).
set -u
cd /home/cunyuliu/ToeholdDesignBench
PY=/home/cunyuliu/miniconda3/envs/toeholdbench/bin/python
export CUDA_VISIBLE_DEVICES=6
for v in trigger_only rc_copy_only trigger_and_rc scaffold_only template_var full_construct segment_shuffle; do
  if [ ! -d "/mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/beacon_mask_${v}_f0" ]; then
    echo "=== $v ==="
    $PY -u src/v03_beacon_masks.py --variant "$v" --outer-fold 0 \
      --device cuda:0 --run-id "beacon_mask_${v}_f0" \
      >> logs/v03_beacon_masks.log 2>&1 || echo "FAILED $v"
  fi
done
echo ALL_MASKS_DONE >> logs/v03_beacon_masks.log
