"""P1-5: final canonical dataset build with absolute coordinates + provenance artifacts.

Reorder: reuse resolved accessions, re-map triggers recording (window_start, window_end, strand),
then emit canonical_records.parquet + license_matrix + exclusion_ledger + hash_manifest.
Sequences are cached to disk to avoid re-downloads.
"""
import hashlib
import json
import os
import subprocess

import pandas as pd

PARQUET = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_pilot.parquet"
VIRUS_ACC = "/mnt/cunyuliu/ToeholdDesignBench/processed/virus_genome_mapping_full.json"
TF_ACC = "/mnt/cunyuliu/ToeholdDesignBench/processed/tf_mapping.json"
SEQDIR = "/mnt/cunyuliu/ToeholdDesignBench/processed/sequences"
OUT_DIR = "/mnt/cunyuliu/ToeholdDesignBench/processed"
os.makedirs(SEQDIR, exist_ok=True)

COMP = str.maketrans("ACGT", "TGCA")
def rc(s): return s.translate(COMP)[::-1]

def fetch_cached(acc):
    p = os.path.join(SEQDIR, acc + ".fasta")
    if os.path.exists(p):
        content = open(p).read()
        return "".join(l for l in content.splitlines() if l and not l.startswith(">")).upper().replace("U", "T")
    u = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id={acc}&rettype=fasta&retmode=text"
    t = subprocess.run(["curl", "-sL", u], capture_output=True, text=True, timeout=120).stdout
    seqs = [l for l in t.splitlines() if l and not l.startswith(">")]
    if not seqs:
        return ""
    open(p, "w").write(t)
    return "".join(seqs).upper().replace("U", "T")

def parse_acc(hdr):
    # '>NM_001357.5 Homo sapiens ...' -> 'NM_001357.5'
    s = hdr.lstrip(">").strip().split()[0] if hdr else ""
    return s

df = pd.read_parquet(PARQUET)

# --- resolve source -> accession list ---
virus_acc = json.load(open(VIRUS_ACC))
tf_acc = json.load(open(TF_ACC))

source_acc = {}
for name, v in virus_acc.items():
    if v.get("accessions"):
        source_acc[name] = v["accessions"]
for gene, v in tf_acc.items():
    a = parse_acc(v.get("acc", "") or "")
    if a and v.get("status") in ("ok", "partial"):
        source_acc[f"human_{gene}"] = [a]

# --- map each trigger -> absolute position ---
records = []
excl = {"no_accession": 0, "no_match": 0}
for tid, sub in df.groupby("target_id"):
    if tid not in source_acc:
        excl["no_accession"] += sub.shape[0]
        continue
    genome = ""
    for a in source_acc[tid]:
        genome += fetch_cached(a)
    if not genome:
        excl["no_accession"] += sub.shape[0]
        continue
    for _, r in sub.iterrows():
        t = r["trigger"]
        if not t:
            excl["no_match"] += 1
            continue
        tu = t.upper()
        p = genome.find(tu)
        strand = "forward"
        if p < 0:
            rev = rc(tu)
            p = genome.find(rev)
            strand = "revcomp"
        if p < 0:
            excl["no_match"] += 1
            continue
        records.append({
            "record_id": r["record_id"], "source_accession": source_acc[tid][0],
            "window_start": p + 1, "window_end": p + len(tu), "strand": strand,
        })

coord = pd.DataFrame(records)
print("coords records:", len(coord), " exclusion:", excl)
coord.to_parquet(f"{OUT_DIR}/coordinates.parquet", index=False)

# --- final canonical merge (drop relative window cols to avoid collision) ---
df2 = df.drop(columns=["window_start", "window_end", "window_step"], errors="ignore")
final = df2.merge(coord, on="record_id", how="left")
final["coordinate_status"] = final["window_start"].notna().map({True: "absolute", False: "no_coord"})
FINAL_PARQUET = f"{OUT_DIR}/canonical_records.parquet"
final.to_parquet(FINAL_PARQUET, index=False)
print("final canonical:", final.shape, " abs-coord records:", int(final["coordinate_status"].eq("absolute").sum()))

# --- license matrix ---
lic = [
    {"asset": "Toehold_Dataset_Final_2019-10-23.csv", "license": "CC BY 4.0", "source": "Angenent-Mari 2020 / GitHub lrsoenksen/CL_RNA_SynthBio", "redistributable": "yes"},
    {"asset": "RefSeq genomes/transcripts (NC_/NM_/XM_)", "license": "public domain (NCBI)", "source": "NCBI RefSeq", "redistributable": "yes"},
    {"asset": "VISTA mCH_on_off_rank.xlsx", "license": "unclear (no explicit LICENSE)", "source": "AlexGreenLab/vista", "redistributable": "verify"},
]
pd.DataFrame(lic).to_csv(f"{OUT_DIR}/license_matrix.csv", index=False)

# --- exclusion ledger ---
ledger = [{"category": k, "n_records": v} for k, v in excl.items()]
ledger += [{"category": "excluded_no_label (no final ON&OFF)", "n_records": int((df["admission_status"] != "admitted_paired").sum())}]
pd.DataFrame(ledger).to_csv(f"{OUT_DIR}/exclusion_ledger.csv", index=False)

# --- hash manifest ---
mani = {}
for f in [FINAL_PARQUET, PARQUET, f"{OUT_DIR}/coordinates.parquet",
          "/mnt/cunyuliu/ToeholdDesignBench/raw/Toehold_Dataset_Final_2019-10-23.csv"]:
    if os.path.exists(f):
        mani[f] = hashlib.sha256(open(f, "rb").read()).hexdigest()
json.dump(mani, open(f"{OUT_DIR}/hash_manifest.json", "w"), indent=2)

print("license_matrix.csv, exclusion_ledger.csv, hash_manifest.json written")
print("P1-5 complete")