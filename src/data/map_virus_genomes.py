"""P1: map 91k virus triggers to absolute genome coordinates (self-validating).

For each of the 23 viral source names, resolve/dowload the reference genome(s),
map every trigger (forward or revcomp), and report mapping rate + inferred stride.
An accession is only trusted when it yields ~100% forward mapping (else flagged).
"""
import json
import subprocess
import sys
from collections import Counter

import pandas as pd

PARQUET = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_pilot.parquet"
OUT = "/mnt/cunyuliu/ToeholdDesignBench/processed/virus_genome_mapping.json"

# curated name -> list of NCBI RefSeq accessions (multi-accession = segmented viruses)
NAME2ACC = {
    "smallpox": ["NC_001611.1"],           # Variola virus
    "ebola": ["NC_002549.1"],              # Zaire ebolavirus
    "marburg": ["NC_001608.3"],            # Marburg virus
    "zika": ["NC_012532.1"],               # Zika virus
    "dengue": ["NC_001477.1"],             # Dengue virus 1
    "west nile": ["NC_009942.1"],          # West Nile virus
    "yellow fever": ["NC_002031.1"],       # Yellow fever virus
    "chikungunya": ["NC_004162.2"],        # Chikungunya virus
    "rabies": ["NC_001542.1"],             # Rabies lyssavirus
    "poliovirus": ["NC_002058.3"],         # Poliovirus (Mahoney)
    "human immunodeficiency": ["NC_001802.1"],  # HIV-1 HXB2
    "human parvo": ["NC_000883.2"],        # Primate erythroparvovirus 1 (B19)
    "papilloma": ["NC_001526.4"],          # HPV-16
    "cardiovirus": ["NC_001479.1"],        # EMCV
    "astrovirus": ["NC_001943.1"],         # Human astrovirus 1
    # segmented / uncertain (resolve via esearch below, else flagged)
    "lassa": ["NC_004296.1", "NC_004297.1"],   # L + S segments
    "hantavirus": ["NC_005222.1", "NC_005223.1", "NC_005225.1"],  # Hantaan L/M/S
    "influenza: h1n1": [],   # 8 segments, resolve
    "influenza: h3n2": [],
    "coxsackie": [],
    "human rhino": [],
    "cosavirus": [],
    "leishmania": [],        # protozoan, large multi-chromosome genome
}

COMP = str.maketrans("ACGT", "TGCA")
def revcomp(s):
    return s.translate(COMP)[::-1]

def fetch_fasta(acc):
    out = subprocess.run(
        ["curl", "-sL",
         f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id={acc}&rettype=fasta&retmode=text"],
        capture_output=True, text=True, timeout=90).stdout
    seqs = [l for l in out.splitlines() if l and not l.startswith(">")]
    return "".join(seqs).upper().replace("U", "T")

def resolve_accessions(name):
    """Best-effort accession resolution via NCBI esearch for the source name."""
    term = name.replace(":", "").strip()
    try:
        out = subprocess.run(
            ["curl", "-sL",
             "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=nuccore&retmax=1&term=" +
             term + "+AND+refseq[filter]"],
            capture_output=True, text=True, timeout=30).stdout
        import re
        ids = re.findall(r"<Id>(\d+)</Id>", out)
        if ids:
            # resolve to accession via esummary
            s = subprocess.run(
                ["curl", "-sL",
                 "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=nuccore&id=" +
                 ids[0] + "&retmode=json"],
                capture_output=True, text=True, timeout=30).stdout
            import json as _j
            d = _j.loads(s)
            acc = d["result"][ids[0]].get("accessionversion")
            return [acc] if acc else []
    except Exception:
        pass
    return []

df = pd.read_parquet(PARQUET)
results = {}
for name, accs in NAME2ACC.items():
    trigs = df[df["target_id"] == name]["trigger"].dropna().tolist()
    if not accs:
        accs = resolve_accessions(name)
    if not accs:
        results[name] = {"status": "unresolved", "n_tiles": len(trigs)}
        print(f"{name:22s} n={len(trigs):5d} UNRESOLVED")
        continue
    genome = ""
    for a in accs:
        genome += fetch_fasta(a)
    if not genome:
        results[name] = {"status": "download_failed", "n_tiles": len(trigs)}
        print(f"{name:22s} n={len(trigs):5d} DOWNLOAD_FAILED")
        continue
    fwd = rc = 0
    pos = []
    for t in trigs:
        t = t.upper()
        if t in genome:
            fwd += 1
            pos.append(genome.find(t))
        elif revcomp(t) in genome:
            rc += 1
            pos.append(genome.find(revcomp(t)))
    rate = (fwd + rc) / max(1, len(trigs))
    stride = None
    if len(pos) >= 100:
        sp = sorted(pos)
        stride = Counter(sp[i+1]-sp[i] for i in range(len(sp)-1)).most_common(3)
    results[name] = {
        "status": "ok" if (fwd>0 and rc==0 and rate>0.95) else "partial",
        "accessions": accs, "n_tiles": len(trigs), "fwd": fwd, "revcomp": rc,
        "rate": round(rate, 4), "stride": stride,
    }
    print(f"{name:22s} n={len(trigs):5d} fwd={fwd:5d} rc={rc:4d} rate={rate:.3f} accs={accs} stride={stride}")

with open(OUT, "w") as fh:
    json.dump(results, fh, indent=2)
print("\nwrote", OUT)