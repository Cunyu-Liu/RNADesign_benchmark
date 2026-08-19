"""P1-3 PILOT: validate human TF gene -> RefSeq transcript -> trigger mapping."""
import json
import subprocess
import urllib.parse

import pandas as pd

PARQUET = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_pilot.parquet"
COMP = str.maketrans("ACGT", "TGCA")
def rc(s): return s.translate(COMP)[::-1]
def curl(u): return subprocess.run(["curl","-sL",u], capture_output=True, text=True, timeout=90).stdout
def esearch(term, retmax=10):
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
def fetch(a):
    t = curl(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id={a}&rettype=fasta&retmode=text")
    return "".join(l for l in t.splitlines() if l and not l.startswith(">")).upper().replace("U","T")

df = pd.read_parquet(PARQUET)
for gene in ["PROX1", "DHX9", "TP53"]:
    tid = f"human_{gene}"
    trigs = df[df.target_id == tid].trigger.dropna().tolist()
    print(f"\n=== {gene} (n={len(trigs)}) ===")
    if trigs:
        print("  sample trigger:", trigs[0])
    ids = esearch(f"{gene}[Gene Name] AND Homo sapiens[Organism] AND srcdb_refseq[properties] AND biomol_mrna[properties]")
    cands = accs(ids)
    nm = [c for c in cands if (c[0] or "").startswith("NM_")]
    print("  RefsSeq mRNA candidates:", [(c[0], c[2], c[1][:40]) for c in nm[:4]])
    if not nm:
        print("  NO NM_ found; all cands:", [(c[0], c[1][:40]) for c in cands[:5]])
        continue
    seq = fetch(nm[0][0])
    fwd = sum(1 for t in trigs if t.upper() in seq)
    rev = sum(1 for t in trigs if rc(t.upper()) in seq)
    print(f"  {nm[0][0]} len={len(seq)} fwd={fwd} rc={rev} rate={(fwd+rev)/len(trigs):.3f}")