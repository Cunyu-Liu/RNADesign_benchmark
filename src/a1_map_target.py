"""A1-1: map BEACON 91,534 rows to target_id via trigger substring matching.
Builds trigger->(source, target_id) from the primary CSV, then for each beacon seq
finds a 30-nt window that equals a known trigger (or its revcomp). Collapses to
distinct target per beacon row; reports virus vs TF record/target counts.
Output: external/beacon_prs/beacon_target_mapping.csv + a summary json.
"""
import csv, json, collections
import numpy as np

CSV = "/mnt/cunyuliu/ToeholdDesignBench/raw/Toehold_Dataset_Final_2019-10-23.csv"
BEACON_DIR = "/mnt/cunyuliu/ToeholdDesignBench/external/beacon_prs"
OUTMAP = "/mnt/cunyuliu/ToeholdDesignBench/external/beacon_prs/beacon_target_mapping.csv"
OUTSUM = "/mnt/cunyuliu/ToeholdDesignBench/processed/a1_beacon_target_attribution.json"

def rc(s):
    c = {"A":"T","T":"A","C":"G","G":"C"}
    return "".join(c.get(x,x) for x in s[::-1])

# 1) build trigger index from primary CSV
trig2target = collections.defaultdict(set)   # 30mer -> set(target_id)
trig2source = collections.defaultdict(set)
with open(CSV) as fh:
    r = csv.reader(fh); header = next(r)
    col = {h:i for i,h in enumerate(header)}
    for row in r:
        if len(row) <= max(col.values()):
            continue
        t = (row[col["trigger"]] if col["trigger"] < len(row) else "").strip().upper().replace("U","T")
        src = (row[col["source_sequence"]] if col["source_sequence"] < len(row) else "").strip()
        sid = (row[col["sequence_id"]] if col["sequence_id"] < len(row) else "").strip()
        if len(t) == 30:
            trig2target[t].add(src)          # source IS the target for virus, human_X for TF
            trig2source[t].add(src)
print("distinct 30nt triggers:", len(trig2target))

trig_set = set(trig2target.keys())
rc_set = set(rc(t) for t in trig_set)

# target category helper
def cat(s):
    if s.startswith("human_"): return "TF"
    if s.startswith("random"): return "random"
    return "virus"

# 2) map beacon rows
rows_out = []
per_line = []
BEACON_KEYS = []  # (split, orig_idx)
attrs = {"fw_target": collections.Counter(), "rc_target": collections.Counter(),
         "none": 0, "multi_target_ambiguous": 0}
for split in ["train", "val", "test"]:
    with open(f"{BEACON_DIR}/{split}.csv") as fh:
        r = csv.reader(fh); next(r)
        for row in r:
            if len(row) < 4:
                continue
            s = row[0].strip().upper().replace("U", "T")
            on, off, onoff = float(row[1]), float(row[2]), float(row[3])
            tgt = None; how = "none"
            fwd = None
            for i in range(0, len(s)-29):
                w = s[i:i+30]
                if w in trig_set:
                    fwd = w; how = "fw"; break
                if w in rc_set:
                    fwd = w; how = "rc"; break
            if fwd is not None:
                key = fwd if how == "fw" else rc(fwd)  # map both orientations to the CSV trigger
                tg = sorted(trig2target[key])
                if len(tg) == 1:
                    tgt = tg[0]
                else:
                    # multi-source target sharing the trigger -> ambiguous but usually same source family
                    tgt = "|".join(tg)
                    attrs["multi_target_ambiguous"] += 1
                attrs[f"{how}_target"][cat(tgt)] += 1
            else:
                attrs["none"] += 1
            rows_out.append([split, s, on, off, onoff, tgt, how, cat(tgt) if tgt else "NA"])

with open(OUTMAP, "w") as w:
    wcsv = csv.writer(w)
    wcsv.writerow(["split","sequence","ON","OFF","ON_OFF","target_id","match","category"])
    wcsv.writerows(rows_out)

print("\n=== beacon rows by category (matchable) ===")
print("total rows:", len(rows_out))
cat_count = collections.Counter(r[7] for r in rows_out)
print("category counts:", dict(cat_count))
# virus rows + distinct virus targets
virus_rows = [r for r in rows_out if r[7] == "virus" and r[5] and "|" not in r[5]]
virus_targets = sorted(set(r[5] for r in virus_rows))
tf_rows = [r for r in rows_out if r[7] == "TF" and r[5] and "|" not in r[5]]
tf_targets = sorted(set(r[5] for r in tf_rows))
print(f"\nvirus rows (unambiguous target): {len(virus_rows)}")
print(f"virus distinct targets: {len(virus_targets)} -> {virus_targets}")
print(f"TF rows (unambiguous): {len(tf_rows)}; TF distinct targets: {len(tf_targets)}")

# per split for virus
for split in ["train","val","test"]:
    vv = [r for r in virus_rows if r[0] == split]
    tt = set(r[5] for r in vv)
    print(f"  virus {split:5s}: rows={len(vv):5d} targets={len(tt)}")

# compare to our current canonical test virus targets (n=6)
print("\n=== compare to current canonical test virus targets ===")
import pandas as pd
canon = pd.read_parquet("/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_records.parquet")
canon = canon[canon["admission_status"]=="admitted_paired"].copy(); canon=canon[canon["ON_OFF"].notna()]
sp = pd.read_csv("/mnt/cunyuliu/ToeholdDesignBench/processed/split_manifests.csv")
canon = canon.merge(sp, on="target_id", how="left")
te = canon[canon["split"]=="test"]
te_v = te[~te["target_id"].astype(str).str.startswith("human_")]
print("canonical test virus targets:", te_v["target_id"].nunique(), sorted(te_v["target_id"].unique()))

summary = {
    "beacon_total": len(rows_out),
    "category_counts": dict(cat_count),
    "virus_rows_unambiguous": len(virus_rows),
    "virus_targets": virus_targets,
    "n_virus_targets": len(virus_targets),
    "tf_rows_unambiguous": len(tf_rows),
    "n_tf_targets": len(tf_targets),
    "attrs": {k: dict(v) if isinstance(v, collections.Counter) else v for k, v in attrs.items()},
}
json.dump(summary, open(OUTSUM, "w"), indent=2)
print("\nwrote", OUTMAP, "and", OUTSUM)