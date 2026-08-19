"""Gate 0 To-do C PILOT: prove 91k trigger->full-source coordinate reconstruction is feasible.

Download the Variola (smallpox) reference genome from NCBI and check whether the
'smallpox' triggers in the dataset map to it (exact substring, forward or revcomp).
If mapping succeeds, window_start/window_end become recoverable.
"""
import subprocess
import sys
from collections import Counter

import pandas as pd

PARQUET = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_pilot.parquet"
ACC = "NC_001611.1"  # Variola virus, complete genome

# fetch genome
try:
    out = subprocess.run(
        ["curl", "-sL",
         f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id={ACC}&rettype=fasta&retmode=text"],
        capture_output=True, text=True, timeout=60).stdout
except Exception as e:
    print("fetch failed", e); sys.exit(1)

lines = [l for l in out.splitlines() if l and not l.startswith(">")]
genome = "".join(lines).upper().replace("U", "T")
print("genome accession=%s length=%d" % (ACC, len(genome)))

COMP = str.maketrans("ACGT", "TGCA")
def revcomp(s):
    return s.translate(COMP)[::-1]

df = pd.read_parquet(PARQUET)
small = df[df["target_id"] == "smallpox"]["trigger"].dropna().tolist()
print("n_smallpox_tiles=%d" % len(small))

hits = {"forward": 0, "revcomp": 0, "both": 0, "miss": 0}
positions = []
for tr in small:
    tr = tr.upper()
    f = genome.find(tr)
    rc = genome.find(revcomp(tr))
    if f >= 0 and rc >= 0:
        hits["both"] += 1
    elif f >= 0:
        hits["forward"] += 1
        positions.append(f)
    elif rc >= 0:
        hits["revcomp"] += 1
        positions.append(rc)
    else:
        hits["miss"] += 1

print("mapping hits:", dict(hits))
if positions:
    import statistics
    print("window_start: min=%d median=%d max=%d (n=%d)" %
          (min(positions), int(statistics.median(positions)), max(positions), len(positions)))

# verify 5nt stride on mapped positions
if len(positions) >= 100:
    sp = sorted(positions)
    strides = [sp[i+1] - sp[i] for i in range(len(sp)-1)]
    print("stride distribution (top):", Counter(strides).most_common(6))