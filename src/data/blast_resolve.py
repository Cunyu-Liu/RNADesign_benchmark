"""P1: resolve exact virus strains by BLASTing representative triggers (self-validating)."""
import json
import time
import urllib.parse
import urllib.request

import pandas as pd

PARQUET = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_pilot.parquet"
UNRESOLVED = ["ebola", "marburg", "zika", "rabies", "human immunodeficiency",
              "papilloma", "cardiovirus", "astrovirus", "hantavirus",
              "influenza: h1n1", "influenza: h3n2", "coxsackie",
              "human rhino", "cosavirus", "leishmania"]

BASE = "https://blast.ncbi.nlm.nih.gov/blast/Blast.cgi"


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "ignore")


def blast_search(seq):
    q = urllib.parse.quote(seq)
    out = _get(f"{BASE}?CMD=Put&PROGRAM=blastn&DATABASE=nt&QUERY={q}&HITLIST_SIZE=5")
    rid = None
    for part in out.split("\n"):
        if "RID" in part and "=" in part and "RTOE" not in part:
            kv = part.split("=")
            if len(kv) == 2:
                rid = kv[1].strip()
                break
    if not rid:
        # regex fallback
        import re
        m = re.search(r"RID = ([A-Z0-9]+)", out)
        rid = m.group(1) if m else None
    if not rid:
        return {"error": "no rid", "raw": out[:200]}
    for _ in range(30):
        st = _get(f"{BASE}?CMD=Get&FORMAT_OBJECT=SearchInfo&RID={rid}")
        if "Status=READY" in st:
            break
        time.sleep(4)
    res = _get(f"{BASE}?CMD=Get&FORMAT_TYPE=JSON2_S&RID={rid}")
    try:
        d = json.loads(res)
    except Exception:
        return {"error": "bad json", "raw": res[:300]}
    hits = []
    for h in (d.get("BlastOutput2", []) or []):
        r = h["report"]["results"]
        for b in r.get("search", {}).get("hits", [])[:3]:
            hsp = b["hsps"][0]
            hits.append({
                "accession": b["description"][0]["accession"],
                "title": b["description"][0]["title"],
                "ident": hsp["identity"] / hsp["align_len"],
                "align_len": hsp["align_len"],
            })
    return hits


df = pd.read_parquet(PARQUET)
out = {}
for name in UNRESOLVED:
    trigs = df[df.target_id == name].trigger.dropna().tolist()
    if not trigs:
        out[name] = {"status": "no_triggers"}
        print(f"{name}: no triggers")
        continue
    # use the 3rd trigger (avoid extreme AT-rich ends) as probe
    probe = sorted(trigs, key=lambda s: (s.count("G") + s.count("C")))[len(trigs)//2]
    try:
        hits = blast_search(probe)
    except Exception as e:
        hits = [{"error": str(e)}]
    out[name] = {"probe": probe, "hits": hits}
    top = hits[0] if hits else {}
    print(f"{name:22s} -> {top.get('accession','?'):20s} {str(top.get('title',''))[:60]} ident={top.get('ident','?')}")

with open("/mnt/cunyuliu/ToeholdDesignBench/processed/blast_strain_search.json", "w") as fh:
    json.dump(out, fh, indent=2)
print("done")