"""Gate 0 To-do C: source/window overlap & sliding-window leakage quantification (O0-05)."""
import json
import random
import statistics
from collections import defaultdict

import pandas as pd

PARQUET = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_pilot.parquet"
OUT = "/mnt/cunyuliu/ToeholdDesignBench/processed/overlap_summary.json"

df = pd.read_parquet(PARQUET)
df = df[df["admission_status"] != "excluded_no_label"].reset_index(drop=True)


def overlap_len(a, b):
    m = 0
    L = len(a)
    for k in range(1, L + 1):
        if a[-k:] == b[:k]:
            m = k
    return m


step_by_cat = defaultdict(list)
adj_identity = []
# neighbour map for leakage: (target_id, tile_index) -> trigger
tid_tile_trig = {}
for tid, g in df.groupby("target_id"):
    g = g.sort_values("tile_index")
    trig = g["trigger"].tolist()
    tiles = g["tile_index"].tolist()
    steps = [tiles[i + 1] - tiles[i] for i in range(len(tiles) - 1)]
    if steps:
        step_by_cat[df.loc[g.index[0], "source_category"]].append(min(steps))
    for t, tr in zip(tiles, trig):
        tid_tile_trig[(tid, t)] = tr
    for i in range(len(trig) - 1):
        adj_identity.append(overlap_len(trig[i], trig[i + 1]) / 30.0)

print("=== inferred tiling step by category ===")
for cat, sts in step_by_cat.items():
    print(f"  {cat}: distinct_steps={sorted(set(sts))}")

print("\n=== adjacent-trigger identity (30nt windows) ===")
print("  n_pairs =", len(adj_identity))
print("  mean = %.3f  median = %.3f  min = %.3f  max = %.3f" %
      (statistics.mean(adj_identity), statistics.median(adj_identity),
       min(adj_identity), max(adj_identity)))
for thr in [0.5, 0.8, 1.0]:
    print("  share >=%.1f identity = %.3f" %
          (thr, sum(1 for x in adj_identity if x >= thr) / len(adj_identity)))

# fast neighbour-based leakage under random row split
random.seed(0)


def neighbour_leak(split=0.2, trials=5):
    fracs = []
    keys = list(tid_tile_trig.keys())
    n = len(keys)
    for _ in range(trials):
        idx = list(range(n))
        random.shuffle(idx)
        ntest = int(n * split)
        test = set(idx[:ntest])
        train = idx[ntest:]
        train_keys = {keys[j] for j in train}
        leak = 0
        for j in test:
            tid, ti = keys[j]
            if (tid, ti + 1) in train_keys or (tid, ti - 1) in train_keys:
                leak += 1
        fracs.append(leak / max(1, len(test)))
    return sum(fracs) / len(fracs)


nl = neighbour_leak()
print("\n=== random-row-split leakage (test tile with adjacent same-source neighbour in train) ===")
print("  fraction of test tiles = %.3f" % nl)

summary = {
    "n_pairs_adjacent": len(adj_identity),
    "adjacent_identity_mean": statistics.mean(adj_identity),
    "adjacent_identity_median": statistics.median(adj_identity),
    "share_ge_0_8": sum(1 for x in adj_identity if x >= 0.8) / len(adj_identity),
    "inferred_step_by_category": {k: sorted(set(v)) for k, v in step_by_cat.items()},
    "random_split_adjacent_neighbour_leak": nl,
}
with open(OUT, "w") as fh:
    json.dump(summary, fh, indent=2)
print("wrote", OUT)