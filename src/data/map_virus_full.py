"""P1-2: map ALL 23 virus triggers to absolute coordinates using resolved accessions."""
import json
import subprocess
from collections import Counter

import pandas as pd

PARQUET = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_pilot.parquet"
OUT = "/mnt/cunyuliu/ToeholdDesignBench/processed/virus_genome_mapping_full.json"

COMP = str.maketrans("ACGT", "TGCA")
def rc(s): return s.translate(COMP)[::-1]

NAME2ACC = {
    "smallpox": ["NC_001611.1"], "dengue": ["NC_001477.1"], "west nile": ["NC_009942.1"],
    "yellow fever": ["NC_002031.1"], "chikungunya": ["NC_004162.2"], "poliovirus": ["NC_002058.3"],
    "human parvo": ["NC_000883.2"], "lassa": ["NC_004296.1", "NC_004297.1"],
    # BLAST-identified strains
    "ebola": ["NC_014372"], "marburg": ["NC_024781"], "zika": ["PZ384978"],
    "rabies": ["NC_018629"], "human immunodeficiency": ["NC_001722"],
    "papilloma": ["EF396271"], "cardiovirus": ["NC_010810"], "astrovirus": ["EU847151"],
    "hantavirus": ["AF143675"], "influenza: h1n1": ["MH201218"],
    "influenza: h3n2": ["PX908013"], "coxsackie": ["HQ164111"],
    "human rhino": ["NC_001617"], "cosavirus": ["KM516909"], "leishmania": ["NC_024115"],
}

def fetch(acc):
    out = subprocess.run(["curl","-sL",
        f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id={acc}&rettype=fasta&retmode=text"],
        capture_output=True, text=True, timeout=90).stdout
    hdr = [l for l in out.splitlines() if l.startswith(">")]
    seq = "".join(l for l in out.splitlines() if l and not l.startswith(">")).upper().replace("U","T")
    return hdr, seq

df = pd.read_parquet(PARQUET)
results = {}
total_mapped = 0
for name, accs in NAME2ACC.items():
    trigs = df[df.target_id == name].trigger.dropna().tolist()
    genome = ""
    hdrs = []
    for a in accs:
        h, s = fetch(a)
        hdrs += h
        genome += s
    fwd = rev = 0
    pos = []
    for t in trigs:
        t = t.upper()
        if t in genome:
            fwd += 1; pos.append(genome.find(t))
        elif rc(t) in genome:
            rev += 1; pos.append(genome.find(rc(t)))
    rate = (fwd + rev) / max(1, len(trigs))
    stride = None
    if len(pos) >= 100:
        sp = sorted(pos)
        stride = Counter(sp[i+1]-sp[i] for i in range(len(sp)-1)).most_common(2)
    results[name] = {"accessions": accs, "n": len(trigs), "fwd": fwd, "rc": rev,
                     "rate": round(rate, 4), "stride": stride, "title": hdrs[0][:70] if hdrs else ""}
    total_mapped += fwd + rev
    print(f"{name:22s} n={len(trigs):5d} fwd={fwd:5d} rc={rev:4d} rate={rate:.3f} {accs}")

print(f"\nTOTAL mapped triggers: {total_mapped} / {int(df[df.source_category=='virus'].shape[0])} = {total_mapped/df[df.source_category=='virus'].shape[0]:.3f}")
with open(OUT, "w") as fh:
    json.dump(results, fh, indent=2)
print("wrote", OUT)