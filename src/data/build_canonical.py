"""Build the Gate 0 canonical pilot dataset (O0-04) from the Angenent-Mari 2020 raw CSV.

Canonical schema follows contract section 7.2. Records are fail-closed: any row that
cannot be mapped to a source identity and tile index is excluded with a reason.
"""
import csv
import hashlib
import json
import statistics
from collections import Counter

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

RAW = "/mnt/cunyuliu/ToeholdDesignBench/raw/Toehold_Dataset_Final_2019-10-23.csv"
OUT_PARQUET = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_pilot.parquet"
OUT_SOURCEMAP = "/mnt/cunyuliu/ToeholdDesignBench/processed/source_map.csv"
OUT_SUMMARY = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_pilot_summary.json"

# --- load raw robustly (pure-python csv handles ragged rows) ---
with open(RAW, newline="") as fh:
    reader = csv.reader(fh)
    header = next(reader)
    ncol = len(header)
    rows = [row + [""] * (ncol - len(row)) for row in reader]

print(f"loaded {len(rows)} rows x {ncol} cols")

idx = {h: i for i, h in enumerate(header)}


def cell(row, name):
    return row[idx[name]]


def parse_tile(sequence_id: str):
    # sequence_id format: '<source>_tile_<N>'  (source itself may contain 'human_' etc)
    if "_tile_" in sequence_id:
        base, _, n = sequence_id.rpartition("_tile_")
        try:
            return base, int(n)
        except ValueError:
            return None, None
    return None, None


def category(source_name: str) -> str:
    if source_name.startswith("random"):
        return "random"
    if source_name.startswith("human_"):
        return "human_TF"
    return "virus"


def tile_step(cat: str) -> int:
    # contract: viral windows step 5 nt, human TF step 10 nt; random has no tiling
    return {"virus": 5, "human_TF": 10, "random": None}[cat]


records = []
excluded = Counter()
admitted = 0
paired = 0

for r in rows:
    source = cell(r, "source_sequence").strip()
    seq_id = cell(r, "sequence_id").strip()
    trigger = cell(r, "trigger").strip()
    switch = cell(r, "switch").strip()
    on_v = cell(r, "ON").strip()
    off_v = cell(r, "OFF").strip()
    onoff_v = cell(r, "ON_OFF").strip()
    qc_on = cell(r, "QC_ON").strip()
    qc_off = cell(r, "QC_OFF").strip()
    qc_onoff = cell(r, "QC_ON_OFF").strip()

    # flow-seq gate counts (raw ON/OFF characterization)
    on_gates = [cell(r, f"On_Gate{k}_counts").strip() for k in range(1, 5)]
    off_gates = [cell(r, f"Off_Gate{k}_counts").strip() for k in range(1, 5)]
    has_on_flowseq = any(g != "" for g in on_gates)
    has_off_flowseq = any(g != "" for g in off_gates)

    if not source or not seq_id:
        excluded["missing_source_or_seqid"] += 1
        continue
    base, tile = parse_tile(seq_id)
    if base is None or tile is None:
        excluded["unparsable_tile_index"] += 1
        continue
    cat = category(source)
    step = tile_step(cat)

    def fnum(v):
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    has_on = fnum(on_v) is not None
    has_off = fnum(off_v) is not None
    is_paired = has_on and has_off
    paired_characterized = has_on_flowseq and has_off_flowseq

    if is_paired:
        paired += 1

    # admission status (fail-closed)
    if is_paired:
        status = "admitted_paired"
    elif has_off or has_on:
        status = "admitted_single_label"
    else:
        status = "excluded_no_label"
        excluded[status] += 1

    window_start = tile * step if step is not None else None
    window_end = (tile * step + len(trigger)) if (step is not None and trigger) else None

    salis_onoff = cell(r, "SalisLabONOFF").strip()
    mfe_switch_off = cell(r, "mfe_seq_SwitchOFF").strip()
    mfe_switch_on = cell(r, "mfe_seq_SwitchON").strip()
    mfe_trigger = cell(r, "mfe_seq_Trigger").strip()

    gc_content = None
    if trigger:
        gc = (trigger.count("G") + trigger.count("C")) / len(trigger)
        gc_content = round(gc, 4)

    rec = {
        "record_id": f"{source}__tile_{tile}",
        "study_id": "angenent2020",
        "raw_row": seq_id,
        "target_id": source,
        "source_category": cat,
        "tile_index": tile,
        "window_start": window_start,
        "window_end": window_end,
        "window_step": step,
        "architecture_id": "first-gen-30nt",
        "reporter_id": "GFP",
        "host_id": "ecoli_BL21",
        "assay_id": "flow-seq",
        "trigger_context": "fused",
        "trigger": trigger,
        "switch": switch,
        "sequence_id": seq_id,
        "ON": fnum(on_v),
        "OFF": fnum(off_v),
        "ON_OFF": fnum(onoff_v),
        "QC_ON": fnum(qc_on),
        "QC_OFF": fnum(qc_off),
        "QC_ON_OFF": fnum(qc_onoff),
        "salis_onoff": fnum(salis_onoff),
        "mfe_switch_off": fnum(mfe_switch_off),
        "mfe_switch_on": fnum(mfe_switch_on),
        "mfe_trigger": fnum(mfe_trigger),
        "gc_trigger": gc_content,
        "has_on_flowseq": has_on_flowseq,
        "has_off_flowseq": has_off_flowseq,
        "paired_characterized": paired_characterized,
        "admission_status": status,
    }
    records.append(rec)

df = pd.DataFrame(records)
vt = df[df["source_category"] != "random"]
n_paired_char = int(df["paired_characterized"].sum())
n_paired_char_vt = int(vt["paired_characterized"].sum())
n_final_paired = int(paired)
n_final_paired_vt = int(((df["ON"].notna()) & (df["OFF"].notna()) & (df["source_category"] != "random")).sum())
print(f"total={len(df)} admitted_paired(final ON&OFF)={paired} excluded={dict(excluded)}")
print(f"paired_characterized(flow-seq)={n_paired_char} virus+TF={n_paired_char_vt}")
print(f"final_paired virus+TF={n_final_paired_vt}")

# --- write parquet ---
table = pa.Table.from_pandas(df, preserve_index=False)
pq.write_table(table, OUT_PARQUET)

# --- source map ---
g = df.groupby("target_id").agg(
    source_category=("source_category", "first"),
    n_records=("target_id", "size"),
    n_admitted_paired=("admission_status", lambda s: (s == "admitted_paired").sum()),
    n_paired_characterized=("paired_characterized", "sum"),
    min_tile=("tile_index", "min"),
    max_tile=("tile_index", "max"),
).reset_index()
g.to_csv(OUT_SOURCEMAP, index=False)

summary = {
    "n_total_rows": len(df),
    "n_admitted_paired": int(paired),
    "n_paired_characterized": n_paired_char,
    "n_paired_characterized_virus_TF": n_paired_char_vt,
    "n_final_paired_virus_TF": n_final_paired_vt,
    "n_unique_targets": int(df["target_id"].nunique()),
    "targets_by_category": df.groupby("source_category")["target_id"].nunique().to_dict(),
    "rows_by_category": df.groupby("source_category").size().to_dict(),
    "excluded": dict(excluded),
    "candidates_per_target": {
        "min": int(g["n_records"].min()),
        "median": int(g["n_records"].median()),
        "mean": round(float(g["n_records"].mean()), 1),
        "p95": int(g["n_records"].quantile(0.95)),
        "max": int(g["n_records"].max()),
    },
    "n_targets_ge_100_candidates": int((g["n_records"] >= 100).sum()),
    "n_targets_ge_10_candidates": int((g["n_records"] >= 10).sum()),
}
with open(OUT_SUMMARY, "w") as fh:
    json.dump(summary, fh, indent=2, ensure_ascii=False)

print(json.dumps(summary, indent=2, ensure_ascii=False))
print("wrote:", OUT_PARQUET, OUT_SOURCEMAP, OUT_SUMMARY)