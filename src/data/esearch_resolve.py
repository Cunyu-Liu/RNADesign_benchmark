"""P1: self-validating strain resolution via esearch (multi-candidate) + efetch test-map."""
import json
import subprocess
import time
import urllib.parse

import pandas as pd

PARQUET = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_pilot.parquet"
COMP = str.maketrans("ACGT", "TGCA")

def rc(s): return s.translate(COMP)[::-1]

def curl(url):
    out = subprocess.run(["curl", "-sL", url], capture_output=True, text=True, timeout=60).stdout
    return out

def esearch(term, retmax=20):
    u = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=nuccore&retmode=json&retmax=%d&term=%s" % (retmax, urllib.parse.quote(term))
    try:
        d = json.loads(curl(u))
        return d.get("esearchresult", {}).get("idlist", [])
    except Exception:
        return []

def accs_for_ids(ids):
    if not ids:
        return []
    u = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=nuccore&retmode=json&id=" + ",".join(ids)
    try:
        d = json.loads(curl(u))
        out = []
        for i in ids:
            r = d.get("result", {}).get(i, {})
            acc = r.get("accessionversion") or r.get("caption")
            title = r.get("title", "")
            out.append((acc, title))
        return out
    except Exception:
        return []

def fetch(acc):
    u = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id=%s&rettype=fasta&retmode=text" % acc
    t = curl(u)
    return "".join(l for l in t.splitlines() if l and not l.startswith(">")).upper().replace("U", "T")

def map_rate(seq, trigs):
    n = len(trigs)
    fwd = sum(1 for t in trigs if t.upper() in seq)
    rev = sum(1 for t in trigs if rc(t.upper()) in seq)
    return (fwd + rev) / n, fwd, rev

# organism terms for unresolved viruses (colloquial -> NCBI organism)
ORG = {
    "ebola": "Zaire ebolavirus[Organism]",
    "marburg": "Marburg marburgvirus[Organism]",
    "zika": "Zika virus[Organism]",
    "rabies": "Rabies lyssavirus[Organism]",
    "human immunodeficiency": "Human immunodeficiency virus 1[Organism]",
    "hantavirus": "Hantaan orthohantavirus[Organism]",
    "astrovirus": "Human astrovirus[Organism]",
    "lassa": "Lassa virus[Organism]",
}

df = pd.read_parquet(PARQUET)
results = {}
for name, org in ORG.items():
    trigs = df[df.target_id == name].trigger.dropna().tolist()
    ids = esearch(org + " AND complete genome[Title]", retmax=15)
    print(f"\n=== {name} (n={len(trigs)}) esearch ids={len(ids)} ===")
    cands = accs_for_ids(ids)
    best = None
    for acc, title in cands[:12]:
        if not acc:
            continue
        try:
            seq = fetch(acc)
        except Exception:
            continue
        if not seq:
            continue
        rate, fwd, rev = map_rate(seq, trigs)
        if rate > 0.5:
            print(f"  {acc:18s} rate={rate:.3f} fwd={fwd} rc={rev} len={len(seq)} {title[:45]}")
        if rate > (best[1] if best else 0):
            best = (acc, rate, fwd, rev, len(seq), title)
    results[name] = best
    if best:
        print(f"  BEST: {best[0]} rate={best[1]:.3f}")
    time.sleep(0.4)

with open("/mnt/cunyuliu/ToeholdDesignBench/processed/esearch_strain_resolution.json", "w") as fh:
    json.dump({k: (v[0], v[1]) if v else None for k, v in results.items()}, fh, indent=2)
print("\nDONE")