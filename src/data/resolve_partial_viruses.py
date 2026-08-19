"""Resolve complete genomes for 5 partial viruses and finalize mapping."""
import json
import subprocess
import time
import urllib.parse
from collections import Counter

import pandas as pd

PARQUET = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_pilot.parquet"
COMP = str.maketrans("ACGT", "TGCA")
def rc(s): return s.translate(COMP)[::-1]
def curl(u): return subprocess.run(["curl","-sL",u], capture_output=True, text=True, timeout=90).stdout
def fetch(a):
    t = curl(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id={a}&rettype=fasta&retmode=text")
    return "".join(l for l in t.splitlines() if l and not l.startswith(">")).upper().replace("U","T")
def esearch(term, retmax=12):
    u = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=nuccore&retmode=json&retmax=%d&term=%s" % (retmax, urllib.parse.quote(term))
    try: return json.loads(curl(u)).get("esearchresult", {}).get("idlist", [])
    except Exception: return []
def accs(ids):
    if not ids: return []
    u = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=nuccore&retmode=json&id=" + ",".join(ids)
    try:
        d = json.loads(curl(u)); out=[]
        for i in ids:
            r = d.get("result",{}).get(i,{})
            out.append((r.get("accessionversion") or r.get("caption"), r.get("title",""), r.get("slen",0)))
        return out
    except Exception: return []

df = pd.read_parquet(PARQUET)
targets = {
    "zika": "Zika virus[Organism] AND complete genome[Title]",
    "papilloma": "Cervus timorensis papillomavirus[Organism] AND complete genome[Title]",
    "astrovirus": "Bat astrovirus[Organism] AND complete genome[Title]",
    "coxsackie": "Coxsackievirus B3[Organism] AND complete genome[Title]",
}
found = {}
for name, term in targets.items():
    trigs = df[df.target_id == name].trigger.dropna().tolist()
    ids = esearch(term)
    cands = accs(ids)
    print(f"\n=== {name} (n={len(trigs)}), {len(cands)} complete-genome candidates ===")
    best = None
    for acc, title, slen in cands[:10]:
        if not acc or slen < 3000:  # skip tiny
            continue
        try: seq = fetch(acc)
        except Exception: continue
        if not seq: continue
        fwd = sum(1 for t in trigs if t.upper() in seq)
        rev = sum(1 for t in trigs if rc(t.upper()) in seq)
        rate = (fwd+rev)/max(1,len(trigs))
        if rate > 0.6:
            print(f"  {acc:16s} rate={rate:.3f} fwd={fwd} rc={rev} len={slen} {title[:50]}")
        if best is None or rate > best[1]:
            best = (acc, rate, fwd, rev)
        time.sleep(0.3)
    if best:
        found[name] = list(best)
        print(f"  BEST {name}: {best[0]} rate={best[1]:.3f}")
    else:
        found[name] = None

with open("/mnt/cunyuliu/ToeholdDesignBench/processed/virus_partial_resolution.json", "w") as fh:
    json.dump(found, fh, indent=2)
print("\nRESOLVED:", {k: (v[0], v[1]) if v else None for k, v in found.items()})