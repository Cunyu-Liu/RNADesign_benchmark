"""P1-3: map all human TF triggers to RefSeq transcript coordinates.

Per gene: resolve RefSeq mRNA (NM_ preferred, XM_ fallback), efetch, map 30-nt
triggers (forward preferred, revcomp fallback). Self-validating: accept ~100% map.
"""
import json
import subprocess
import time
import urllib.parse

import pandas as pd

PARQUET = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_pilot.parquet"
OUT = "/mnt/cunyuliu/ToeholdDesignBench/processed/tf_mapping.json"

COMP = str.maketrans("ACGT", "TGCA")
def rc(s): return s.translate(COMP)[::-1]

def curl(u):
    for _ in range(2):
        try:
            return subprocess.run(["curl","-sL",u], capture_output=True, text=True, timeout=60).stdout
        except Exception:
            time.sleep(1)
    return ""

def esearch_uids(term, retmax=6):
    u = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=nuccore&retmode=json&retmax=%d&term=%s" % (retmax, urllib.parse.quote(term))
    try:
        return json.loads(curl(u)).get("esearchresult", {}).get("idlist", [])
    except Exception:
        return []

def efetch_by_uid(uid):
    u = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id=%s&rettype=fasta&retmode=text" % uid
    t = curl(u)
    hdr = [l for l in t.splitlines() if l.startswith(">")]
    seq = "".join(l for l in t.splitlines() if l and not l.startswith(">")).upper().replace("U","T")
    return hdr, seq

def map_rate(seq, trigs):
    n = len(trigs)
    fwd = sum(1 for t in trigs if t.upper() in seq)
    rev = sum(1 for t in trigs if rc(t.upper()) in seq)
    return (fwd + rev) / n, fwd, rev

df = pd.read_parquet(PARQUET)
tf = df[df.source_category == "human_TF"]
genes = sorted(tf.target_id.str.replace("human_", "", regex=False).unique())
print("n_genes =", len(genes))

results = {}
n_ok = 0
for i, g in enumerate(genes):
    trigs = tf[tf.target_id == f"human_{g}"].trigger.dropna().tolist()
    # resolve: prefer curated NM_, else any refseq mRNA
    uids = esearch_uids(f"{g}[Gene Name] AND Homo sapiens[Organism] AND srcdb_refseq[properties] AND biomol_mrna[properties]")
    if not uids:
        uids = esearch_uids(f"{g}[Gene Name] AND Homo sapiens[Organism] AND biomol_mrna[properties]")
    best = None
    acc_used = None
    for uid in uids[:4]:
        hdr, seq = efetch_by_uid(uid)
        if not seq:
            continue
        rate, fwd, rev = map_rate(seq, trigs)
        if best is None or rate > best[0]:
            best = (rate, fwd, rev, len(seq))
            acc_used = (hdr[0] if hdr else uid)
        if rate >= 0.9:
            break
        time.sleep(0.2)
    if best and best[0] >= 0.9:
        n_ok += 1
        status = "ok"
    elif best and best[0] > 0:
        status = "partial"
    else:
        status = "failed"
    results[g] = {"status": status, "acc": acc_used, "rate": round(best[0],4) if best else 0.0,
                  "n": len(trigs), "fwd": best[1] if best else 0, "rc": best[2] if best else 0,
                  "len": best[3] if best else 0}
    if (i + 1) % 50 == 0 or status != "ok":
        print(f"[{i+1}/{len(genes)}] {g:20s} {status:8s} rate={results[g]['rate']:.3f} acc={acc_used}", flush=True)
    time.sleep(0.34)

with open(OUT, "w") as fh:
    json.dump(results, fh, indent=2)
print(f"\nDONE: {n_ok}/{len(genes)} genes mapped >=90%")
print("wrote", OUT)