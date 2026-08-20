"""A1 (authoritative): attribute all 91,534 BEACON rows to their target using the
GSE149225 processed data (Angenent-Mari et al. 2020). Each BEACON 148-mer contains its
own on_id/off_id as a contiguous substring; those ids map to source_sequence (target)
and sequence_id. Writes beacon_authoritative_mapping.csv (split, sequence, ON, OFF,
ON_OFF, source_sequence, sequence_id, category) + status json.
Category: virus = non-human_, non-random source.
"""
import collections
import pandas as pd

GEO = "/mnt/cunyuliu/ToeholdDesignBench/external/gse149225/toehold_processed.csv"
BEACON = "/mnt/cunyuliu/ToeholdDesignBench/external/beacon_prs"
OUT = "/mnt/cunyuliu/ToeholdDesignBench/external/beacon_prs/beacon_authoritative_mapping.csv"
OUTJSON = "/mnt/cunyuliu/ToeholdDesignBench/processed/a1_authoritative_attribution.json"

geo = pd.read_csv(GEO)
id2src = {}
id2sid = {}
for _, r in geo.iterrows():
    src = r["source_sequence"]
    if not isinstance(src, str):
        continue
    for key in ("on_id", "off_id"):
        v = r[key]
        if isinstance(v, str):
            id2src.setdefault(v.strip().upper(), src)
            id2sid.setdefault(v.strip().upper(), r["sequence_id"])
lens = {len(k) for k in id2src}
print("distinct on/off ids:", len(id2src), "lengths:", sorted(lens))

def attr(s):
    s = s.upper()
    best = None   # (len_of_id, source, seqid)
    for L in lens:
        if L > len(s):
            continue
        for i in range(len(s) - L + 1):
            sub = s[i:i+L]
            if sub in id2src:
                # prefer the longest id (more specific)
                if best is None or L > best[0]:
                    best = (L, id2src[sub], id2sid.get(sub, None))
    return best

rows = []
cat_count = collections.Counter()
n_attr = 0
for split in ["train", "val", "test"]:
    be = pd.read_csv(f"{BEACON}/{split}.csv")
    for _, r in be.iterrows():
        s = str(r["sequence"]).strip().upper()
        hit = attr(s)
        if hit is None:
            src, sid, cat = None, None, "NA"
        else:
            _, src, sid = hit
            cat = "virus" if (src and not src.startswith("human_") and not src.startswith("random")) else ("TF" if src and src.startswith("human_") else "random")
            cat_count[cat] += 1
            n_attr += 1
        rows.append({"split": split, "sequence": s, "ON": r["ON"], "OFF": r["OFF"],
                     "ON_OFF": r["ON_OFF"], "source_sequence": src, "sequence_id": sid,
                     "category": cat})

df = pd.DataFrame(rows)
df.to_csv(OUT, index=False)
print("wrote", OUT, "rows", len(df))
print("attributed:", n_attr, "/", len(df), f"= {100*n_attr/len(df):.1f}%")
print("category counts:", dict(cat_count))

# virus targets
virus = df[df.category == "virus"]
print("virus rows:", len(virus), "distinct targets:", virus["source_sequence"].nunique())
vt = virus["source_sequence"].nunique()
print("virus test targets:", virus[virus.split=="test"]["source_sequence"].nunique(),
      "test rows:", (virus.split=="test").sum())

summary = {
    "authoritative_source": "GSE149225",
    "beacon_total": int(len(df)),
    "attributed": int(n_attr),
    "attribution_rate": round(n_attr / len(df), 4),
    "category_counts": {k: int(v) for k, v in cat_count.items()},
    "n_virus_targets": int(vt),
    "n_tf_sources": int(df[df["category"]=="TF"]["source_sequence"].nunique()),
    "virus_targets": sorted(virus["source_sequence"].unique()),
}
import json
json.dump(summary, open(OUTJSON, "w"), indent=2)
print("wrote", OUTJSON)
print(summary)