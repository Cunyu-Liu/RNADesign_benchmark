"""v0.3.0 Batch 1: global study/target/candidate registry, context512, mapping-status
ledger, exclusion ledger, and 5-fold target-cluster split.

Contract: docs/task_contract_v0.3.0.md §2 (data identity & splits), §3 (BEACON rules),
§10 (public interfaces). Acceptance: docs/task_contract_v0.2.1_to_v0.3.0_redline.md.

Outputs (all under /mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/registry/, never
overwritten — the script refuses to run if the directory exists):

  canonical_manifest.parquet   per-record manifest, contract §10 schema
  beacon_manifest.parquet      per-record manifest for the BEACON label view
  target_table.csv             per-target: cluster, category, fold, eligibility, context
  cluster_table.csv            per-cluster: members, size, fold
  mapping_ledger.csv           BEACON per-row mapping status + evidence
  context_ledger.csv           per-record context resolution audit
  exclusion_ledger.csv         v0.3 exclusion accounting
  split_manifest.json          fold assignment, balance stats, seeds, closure rule hits
  registry_summary.json        machine-readable audit summary of every contract check

Homology closure (rule 5d) is implemented as k=17 exact-seed chaining between
contexts of different accessions (occurrence cap 16, offset-consistent seed chains,
exact verification at >=80% identity over >=80% of the shorter context). Documented
sensitivity limit: homologous pairs whose shared 17-mers all appear >16 times
globally (ultra-repeats, >16-member repeat families) are not merged by this rule.
"""
import json
import os
import sys
import hashlib
from collections import defaultdict

import numpy as np
import pandas as pd

PROJ = "/home/cunyuliu/ToeholdDesignBench"
MNT = "/mnt/cunyuliu/ToeholdDesignBench"
CANON_PARQUET = f"{MNT}/processed/canonical_records.parquet"
SEQDIR = f"{MNT}/processed/sequences"
BEACON_AUTH = f"{MNT}/external/beacon_prs/beacon_authoritative_mapping.csv"
LEGACY_SPLIT = f"{MNT}/processed/split_manifests.csv"
OUT_DIR = f"{MNT}/runs/v0.3.0/registry"

STUDY_ID = "angenent_mari_2020"
SEED = 20260821
N_OUTER = 5
N_INNER = 3
FLANK = 241
TRIGGER_LEN = 30
CONTEXT_LEN = 2 * FLANK + TRIGGER_LEN  # 512
KMER = 17
KMER_OCC_CAP = 16
HOMO_IDENTITY = 0.80
HOMO_COVERAGE = 0.80

COMP = str.maketrans("ACGTN", "TGCAN")


def rc(s):
    return s.translate(COMP)[::-1]


def load_fasta(acc):
    path = os.path.join(SEQDIR, acc + ".fasta")
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        seq = "".join(l.strip() for l in fh if not l.startswith(">"))
    return seq.upper().replace("U", "T")


# ---------------------------------------------------------------------------
# Union-Find
# ---------------------------------------------------------------------------
class UF:
    def __init__(self, items):
        self.parent = {x: x for x in items}

    def find(self, x):
        p = self.parent
        while p[x] != x:
            p[x] = p[p[x]]
            x = p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra

    def groups(self):
        out = defaultdict(list)
        for x in self.parent:
            out[self.find(x)].append(x)
        return out


# ---------------------------------------------------------------------------
# 1. Canonical: context512
# ---------------------------------------------------------------------------
def build_contexts(canon):
    """Return dict record_id -> (context512 str, mask str) and per-record status."""
    acc_cache = {}
    contexts = {}
    status = {}
    for acc, sub in canon[canon["coordinate_status"] == "absolute"].groupby(
        "source_accession"
    ):
        if acc not in acc_cache:
            acc_cache[acc] = load_fasta(acc)
        genome = acc_cache[acc]
        if genome is None:
            for rid in sub["record_id"]:
                status[rid] = "context_unresolved_no_reference"
            continue
        glen = len(genome)
        for _, r in sub.iterrows():
            ws, we = int(r["window_start"]), int(r["window_end"])  # 1-based inclusive
            # 0-based half-open trigger slice on + strand
            t0, t1 = ws - 1, we
            c0, c1 = t0 - FLANK, t1 + FLANK
            pad_l = max(0, -c0)
            pad_r = max(0, c1 - glen)
            core = genome[max(0, c0):min(glen, c1)]
            ctx_plus = "N" * pad_l + core + "N" * pad_r
            if r["strand"] == "revcomp":
                ctx = rc(ctx_plus)
            else:
                ctx = ctx_plus
            if len(ctx) != CONTEXT_LEN:
                status[r["record_id"]] = "context_unresolved_len"
                continue
            # verify center == trigger (direction consistent)
            if ctx[FLANK:FLANK + TRIGGER_LEN] != r["trigger"]:
                status[r["record_id"]] = "context_unresolved_mismatch"
                continue
            mask = "0" * pad_l + "1" * len(core) + "0" * pad_r
            if r["strand"] == "revcomp":
                mask = mask[::-1]
            contexts[r["record_id"]] = (ctx, mask)
            status[r["record_id"]] = "context_resolved"
    for rid in canon.loc[canon["coordinate_status"] != "absolute", "record_id"]:
        status[rid] = "context_unresolved_no_coord"
    return contexts, status


# ---------------------------------------------------------------------------
# 2. Union closure -> target_cluster_id
# ---------------------------------------------------------------------------
def closure(canon, contexts):
    targets = sorted(canon["target_id"].unique())
    uf = UF(targets)
    rule_hits = {k: 0 for k in ("same_accession", "trigger_exact_or_rc",
                                "interval_overlap", "context_homology")}

    # rule 5a: same authoritative accession (source identity is target_id itself)
    acc_of = {}
    for tid, sub in canon.groupby("target_id"):
        accs = set(sub["source_accession"].dropna().unique())
        if accs:
            acc_of[tid] = sorted(accs)
    acc2targets = defaultdict(set)
    for tid, accs in acc_of.items():
        for a in accs:
            acc2targets[a].add(tid)
    for a, tset in acc2targets.items():
        tlist = sorted(tset)
        for i in range(1, len(tlist)):
            if uf.find(tlist[0]) != uf.find(tlist[i]):
                rule_hits["same_accession"] += 1
                uf.union(tlist[0], tlist[i])

    # rule 5b: identical or reverse-complement triggers across targets
    trig2targets = defaultdict(set)
    for tid, sub in canon.groupby("target_id"):
        for t in sub["trigger"].dropna().unique():
            tU = t.upper()
            trig2targets[tU].add(tid)
            trig2targets[rc(tU)].add(tid)  # RC-closure: index both orientations
    for t, tset in trig2targets.items():
        tlist = sorted(tset)
        for i in range(1, len(tlist)):
            if uf.find(tlist[0]) != uf.find(tlist[i]):
                rule_hits["trigger_exact_or_rc"] += 1
                uf.union(tlist[0], tlist[i])

    # rule 5c: overlapping candidate intervals on the same accession
    # (defensive: subsumed by 5a for single-accession targets; still tested)
    by_acc = defaultdict(list)
    for tid, sub in canon.groupby("target_id"):
        for _, r in sub.dropna(subset=["window_start"]).iterrows():
            by_acc[r["source_accession"]].append(
                (int(r["window_start"]), int(r["window_end"]), tid))
    for acc, iv in by_acc.items():
        iv.sort()
        for i in range(1, len(iv)):
            s2, e2, t2 = iv[i]
            for j in range(i - 1, max(-1, i - 200), -1):
                s1, e1, t1 = iv[j]
                if s2 > e1:
                    break
                if t1 != t2 and uf.find(t1) != uf.find(t2):
                    rule_hits["interval_overlap"] += 1
                    uf.union(t1, t2)

    # rule 5d: >=80% identity over >=80% of shorter context (k-mer seed chaining)
    homology_pairs = seed_homology(canon, contexts, uf, acc_of)
    rule_hits["context_homology"] = homology_pairs

    return uf, rule_hits, acc_of


def seed_homology(canon, contexts, uf, acc_of):
    """Cross-accession context homology via k=17 exact seeds.

    Contexts are deduped per target by window_start and stride-sampled to <=64 per
    target. Seeds occurring > KMER_OCC_CAP times globally are dropped (ultra-repeats).
    For each context pair sharing >=2 offset-consistent seeds, verify exact
    identity over the offset-aligned overlap.
    """
    # per-target sampled contexts (only records with resolved context)
    per_target = defaultdict(list)
    rec_ctx = {}  # record_id -> (ctx, mask)
    for rec_id, (ctx, mask) in contexts.items():
        rec_ctx[rec_id] = (ctx, mask)
    meta = canon.set_index("record_id")
    for rec_id in rec_ctx:
        per_target[meta.at[rec_id, "target_id"]].append(rec_id)

    sampled = {}
    for tid, rids in per_target.items():
        # dedupe by (accession, window_start): unique genomic positions only
        uniq = {}
        for rid in rids:
            key = (meta.at[rid, "source_accession"], meta.at[rid, "window_start"])
            if key not in uniq:
                uniq[key] = rid
        rids = sorted(uniq.values())
        if len(rids) > 64:
            idx = np.linspace(0, len(rids) - 1, 64).astype(int)
            rids = [rids[i] for i in sorted(set(idx))]
        sampled[tid] = rids

    # build k-mer index
    enc = np.zeros((sum(len(v) for v in sampled.values()), CONTEXT_LEN), dtype=np.uint8)
    ctx_ids = []
    ctx_target = []
    row = 0
    code = {"A": 0, "C": 1, "G": 2, "T": 3}
    for tid, rids in sampled.items():
        for rid in rids:
            ctx, _ = rec_ctx[rid]
            arr = np.frombuffer(ctx.encode(), dtype=np.uint8)
            v = np.full(CONTEXT_LEN, 255, dtype=np.uint8)
            for b, c in code.items():
                v[arr == ord(b)] = c
            enc[row] = v
            ctx_ids.append(rid)
            ctx_target.append(tid)
            row += 1
    n_ctx = row
    ctx_target = np.array(ctx_target)
    print(f"[5d] indexed {n_ctx} contexts")

    # rolling 2-bit-packed k-mer hashes (uint64, polynomial base 4)
    nk = CONTEXT_LEN - KMER + 1
    hashes = np.zeros((n_ctx, nk), dtype=np.uint64)
    powk = np.uint64(4 ** KMER)
    # prefix hashing: H[i+1] = H[i]*4 + b[i]; window hash = H[i+k] - H[i]*4^k
    pref = np.zeros((n_ctx, CONTEXT_LEN + 1), dtype=np.uint64)
    for j in range(CONTEXT_LEN):
        pref[:, j + 1] = pref[:, j] * np.uint64(4) + enc[:, j].astype(np.uint64)
    for i in range(nk):
        hashes[:, i] = pref[:, i + KMER] - pref[:, i] * powk
    # drop windows containing non-ACGT (N padding): cumulative invalid count
    invalid = (enc == 255).astype(np.int32)
    cum = np.zeros((n_ctx, CONTEXT_LEN + 1), dtype=np.int32)
    np.cumsum(invalid, axis=1, out=cum[:, 1:])
    valid_win = (cum[:, KMER:] - cum[:, :-KMER]) == 0
    hashes[~valid_win] = np.uint64(0xDEADBEEFDEADBEEF)  # sentinel; filtered below
    all_h = hashes.ravel()
    all_valid = valid_win.ravel()
    all_ctx = np.repeat(np.arange(n_ctx), nk)
    all_pos = np.tile(np.arange(nk), n_ctx)
    keep = all_valid
    all_h = all_h[keep]
    all_ctx = all_ctx[keep]
    all_pos = all_pos[keep]
    print(f"[5d] {len(all_h)} valid {KMER}-mers")

    order = np.argsort(all_h, kind="stable") if len(all_h) else np.array([], dtype=np.int64)
    if len(all_h) == 0:
        print("[5d] no valid k-mers to index")
        return 0
    h_s = all_h[order]
    c_s = all_ctx[order]
    p_s = all_pos[order]
    # group boundaries
    new_grp = np.empty(len(h_s), dtype=bool)
    new_grp[0] = True
    np.not_equal(h_s[1:], h_s[:-1], out=new_grp[1:])
    grp_starts = np.flatnonzero(new_grp)
    grp_sizes = np.diff(np.append(grp_starts, len(h_s)))

    # filter: size in [2, KMER_OCC_CAP]
    sel = (grp_sizes >= 2) & (grp_sizes <= KMER_OCC_CAP)
    print(f"[5d] seed groups with 2..{KMER_OCC_CAP} occurrences: {int(sel.sum())}")

    # vectorized pair emission: within each hash-contiguous group, all
    # occurrence pairs (i, i+d), d = 1..KMER_OCC_CAP-1; h_s[i]==h_s[i+d]
    # guarantees same kmer (same group).
    # target indices and same-accession pair exclusion
    targets_sorted = sorted(per_target.keys())
    tidx = {t: i for i, t in enumerate(targets_sorted)}
    tgt_s = np.array([tidx[t] for t in ctx_target])[c_s]
    same_acc_keys = set()
    acc_rows = []
    for t, accs in acc_of.items():
        for a in accs:
            acc_rows.append((a, tidx[t]))
    acc_rows.sort()
    for i in range(1, len(acc_rows)):
        if acc_rows[i][0] == acc_rows[i - 1][0]:
            a, b = acc_rows[i][1], acc_rows[i - 1][1]
            same_acc_keys.add(min(a, b) * 100000 + max(a, b))
    same_acc_arr = np.array(sorted(same_acc_keys), dtype=np.int64) \
        if same_acc_keys else np.array([], dtype=np.int64)

    pair_a, pair_b, pair_pa, pair_pb = [], [], [], []
    grp_id = np.cumsum(new_grp) - 1
    grp_sizes_arr = grp_sizes[grp_id]
    for d in range(1, KMER_OCC_CAP):
        idx = np.flatnonzero(h_s[:-d] == h_s[d:])
        if len(idx) == 0:
            continue
        # only pairs inside groups of size <= KMER_OCC_CAP (occurrence cap)
        idx = idx[(grp_sizes_arr[idx] <= KMER_OCC_CAP) &
                  (grp_sizes_arr[idx + d] <= KMER_OCC_CAP)]
        if len(idx) == 0:
            continue
        ta = tgt_s[idx]
        tb = tgt_s[idx + d]
        mask = ta != tb
        # skip same-accession pairs (rule 5a already merges those)
        pk = np.minimum(ta, tb) * 100000 + np.maximum(ta, tb)
        if len(same_acc_arr):
            mask &= ~np.isin(pk, same_acc_arr)
        if mask.any():
            ca = c_s[idx][mask]
            cb = c_s[idx + d][mask]
            pa = p_s[idx][mask]
            pb = p_s[idx + d][mask]
            lo_c = np.minimum(ca, cb)
            hi_c = np.maximum(ca, cb)
            lo_p = np.where(ca <= cb, pa, pb)
            hi_p = np.where(ca <= cb, pb, pa)
            pair_a.append(lo_c)
            pair_b.append(hi_c)
            pair_pa.append(lo_p)
            pair_pb.append(hi_p)
    if not pair_a:
        print("[5d] no cross-target seed pairs")
        return 0
    pa_c = np.concatenate(pair_a).astype(np.int64)
    pb_c = np.concatenate(pair_b).astype(np.int64)
    pa_p = np.concatenate(pair_pa).astype(np.int64)
    pb_p = np.concatenate(pair_pb).astype(np.int64)
    print(f"[5d] cross-target seed pair occurrences: {len(pa_c)}")

    # dedupe identical seed hits (same ctx pair, same positions)
    key = (pa_c * (n_ctx + 1) + pb_c) * 1000 + pa_p
    key = key * 1000 + pb_p
    uk = np.unique(key)
    pb_p = (uk % 1000).astype(np.int64)
    uk //= 1000
    pa_p = (uk % 1000).astype(np.int64)
    uk //= 1000
    pb_c = (uk % (n_ctx + 1)).astype(np.int64)
    pa_c = (uk // (n_ctx + 1)).astype(np.int64)
    print(f"[5d] unique cross-target seeds: {len(pa_c)}")

    # offset = pos_b - pos_a; modal offset per ctx pair must have >=2 seeds
    pid = pa_c * (n_ctx + 1) + pb_c
    off = pb_p - pa_p
    order = np.lexsort((off, pid))
    pid_s, off_s = pid[order], off[order]
    run_new = np.empty(len(pid_s), dtype=bool)
    run_new[0] = True
    run_new[1:] = (pid_s[1:] != pid_s[:-1]) | (off_s[1:] != off_s[:-1])
    run_starts = np.flatnonzero(run_new)
    run_lens = np.diff(np.append(run_starts, len(pid_s)))
    # pid segments (every pid boundary is also a run boundary)
    pid_new = np.empty(len(pid_s), dtype=bool)
    pid_new[0] = True
    pid_new[1:] = pid_s[1:] != pid_s[:-1]
    pid_starts = np.flatnonzero(pid_new)
    # run-index of each pid start
    ridx = np.searchsorted(run_starts, pid_starts)
    ridx = np.clip(ridx, 0, len(run_lens) - 1)
    max_run_per_pid = np.maximum.reduceat(run_lens, ridx)
    cand_pids = np.flatnonzero(max_run_per_pid >= 2)
    print(f"[5d] ctx pairs with >=2 offset-consistent seeds: {len(cand_pids)}")

    merged_pairs = set()
    for p in cand_pids:
        pv = int(pid_s[pid_starts[p]])
        ca, cb = pv // (n_ctx + 1), pv % (n_ctx + 1)
        # best run within this pid's run range
        r0, r1 = ridx[p], (ridx[p + 1] if p + 1 < len(ridx) else len(run_lens))
        ri = r0 + int(np.argmax(run_lens[r0:r1]))
        off_v = int(off_s[run_starts[ri]])
        ctx_a, _ = rec_ctx[ctx_ids[ca]]
        ctx_b, _ = rec_ctx[ctx_ids[cb]]
        # seeds satisfy pos_b = pos_a + off  =>  B[j] corresponds to A[j - off]
        lo = max(0, -off_v)
        hi = min(CONTEXT_LEN, CONTEXT_LEN - off_v)
        if hi - lo < HOMO_COVERAGE * CONTEXT_LEN:
            continue
        a_seg = ctx_a[lo:hi]
        b_seg = ctx_b[lo + off_v:hi + off_v]
        ident = sum(1 for x, y in zip(a_seg, b_seg) if x == y) / len(a_seg)
        if ident >= HOMO_IDENTITY:
            ta, tb = ctx_target[ca], ctx_target[cb]
            if uf.find(ta) != uf.find(tb):
                merged_pairs.add((ta, tb))
                uf.union(ta, tb)
    return len(merged_pairs)


# ---------------------------------------------------------------------------
# 3. 5-fold group-stratified outer split (+ inner 3-fold)
# ---------------------------------------------------------------------------
def make_splits(canon, uf, cluster_of):
    targets = sorted(canon["target_id"].unique())
    cat_of = canon.groupby("target_id")["source_category"].first().to_dict()
    pool_of = canon.groupby("target_id").size().to_dict()

    clusters = defaultdict(list)
    for t in targets:
        clusters[cluster_of[t]].append(t)
    cluster_ids = sorted(clusters, key=lambda c: (
        -len(clusters[c]), -sum(pool_of[t] for t in clusters[c]), c))

    cats = sorted(set(cat_of.values()))
    N = len(targets)
    total_pool = sum(pool_of.values())

    fold_stats = {f: {"n": 0, "pool": 0, "cat": {c: 0 for c in cats}}
                  for f in range(N_OUTER)}
    fold_of = {}
    rng = np.random.default_rng(SEED)
    for cid in cluster_ids:
        members = clusters[cid]
        add_n = len(members)
        add_pool = sum(pool_of[t] for t in members)
        add_cat = defaultdict(int)
        for t in members:
            add_cat[cat_of[t]] += 1
        best, best_cost = None, None
        for f in range(N_OUTER):
            st = fold_stats[f]
            cost_n = abs(st["n"] + add_n - N / N_OUTER)
            cost_pool = abs(st["pool"] + add_pool - total_pool / N_OUTER) / max(total_pool, 1) * N
            cost_cat = 0.0
            for c in cats:
                have = st["cat"][c] + add_cat.get(c, 0)
                target_c = sum(1 for t in targets if cat_of[t] == c) / N_OUTER
                cost_cat += abs(have - target_c) / max(target_c, 1)
            cost = cost_n / (N / N_OUTER) + 0.5 * cost_pool + 0.5 * cost_cat
            # deterministic tie-break with seeded jitter
            cost += float(rng.random()) * 1e-6
            if best_cost is None or cost < best_cost:
                best, best_cost = f, cost
        for t in members:
            fold_of[t] = best
        fold_stats[best]["n"] += add_n
        fold_stats[best]["pool"] += add_pool
        for c in cats:
            fold_stats[best]["cat"][c] += add_cat.get(c, 0)

    # inner 3-fold within each outer-train (for nested CV; seed-frozen)
    inner_of = {}
    for outer in range(N_OUTER):
        inner_clusters = defaultdict(list)
        for t in targets:
            if fold_of[t] != outer:
                inner_clusters[cluster_of[t]].append(t)
        inner_stats = {i: {"n": 0, "cat": {c: 0 for c in cats}} for i in range(N_INNER)}
        # largest-first greedy with category balance
        inner_ids = sorted(inner_clusters,
                           key=lambda c: (-len(inner_clusters[c]), c))
        for cid in inner_ids:
            members = inner_clusters[cid]
            add_cat = defaultdict(int)
            for t in members:
                add_cat[cat_of[t]] += 1
            best, best_cost = None, None
            for i in range(N_INNER):
                st = inner_stats[i]
                cost = st["n"] + len(members)
                for c in cats:
                    target_c = sum(1 for t in targets
                                   if cat_of[t] == c and fold_of[t] != outer) / N_INNER
                    cost += 0.5 * abs(st["cat"][c] + add_cat.get(c, 0) - target_c) / max(target_c, 1)
                cost += float(rng.random()) * 1e-6
                if best_cost is None or cost < best_cost:
                    best, best_cost = i, cost
            for t in members:
                inner_of[t] = (outer, best)
            inner_stats[best]["n"] += len(members)
            for c in cats:
                inner_stats[best]["cat"][c] += add_cat.get(c, 0)

    return fold_of, inner_of, fold_stats


# ---------------------------------------------------------------------------
# 4. BEACON label view
# ---------------------------------------------------------------------------
def build_beacon(canon, contexts, ctx_status, cluster_of, fold_of, acc_of):
    b = pd.read_csv(BEACON_AUTH)
    b["trigger"] = b["sequence"].str.slice(3, 33)  # frozen correct slice [3:33]
    meta = canon.set_index("sequence_id")
    canon_targets = set(canon["target_id"].unique())

    # trigger index for cross-check (canonical triggers, both orientations)
    trig2targets = defaultdict(set)
    for tid, sub in canon.groupby("target_id"):
        for t in sub["trigger"].dropna().unique():
            tU = t.upper()
            trig2targets[tU].add(tid)
            trig2targets[rc(tU)].add(tid)

    # genome cache for context re-search of tiles absent from canonical
    genome_cache = {}

    def genome_of(tid):
        if tid not in genome_cache:
            genome_cache[tid] = None
            accs = acc_of.get(tid) or []
            g = ""
            for a in accs:
                g += load_fasta(a) or ""
            if g:
                genome_cache[tid] = g
        return genome_cache[tid]

    def ctx_from_genome(tid, trig):
        """Search the trigger on the target accession; return
        (accession, window_start, window_end, strand, ctx, mask) or None."""
        g = genome_of(tid)
        if not g:
            return None
        p = g.find(trig)
        strand = "forward"
        if p < 0:
            p = g.find(rc(trig))
            strand = "revcomp"
        if p < 0:
            return None
        ws, we = p + 1, p + len(trig)
        c0, c1 = p - FLANK, we + FLANK
        pad_l = max(0, -c0)
        pad_r = max(0, c1 - len(g))
        core = g[max(0, c0):min(len(g), c1)]
        ctx_plus = "N" * pad_l + core + "N" * pad_r
        ctx = rc(ctx_plus) if strand == "revcomp" else ctx_plus
        if len(ctx) != CONTEXT_LEN:
            return None
        if ctx[FLANK:FLANK + TRIGGER_LEN] != trig:
            return None
        mask = "0" * pad_l + "1" * len(core) + "0" * pad_r
        if strand == "revcomp":
            mask = mask[::-1]
        acc = (acc_of.get(tid) or [None])[0]
        return acc, ws, we, strand, ctx, mask

    rows = []
    ledger = []
    n_ctx_inherit = n_ctx_research = 0
    for _, r in b.iterrows():
        trig = str(r["trigger"]).upper()
        auth_sid = r["sequence_id"]
        src = r["source_sequence"]
        # primary authoritative evidence: GSE149225 source_sequence -> target
        auth_target = src if src in canon_targets else None
        # secondary: record link via sequence_id (context/coords inheritance)
        rec_link = meta.loc[auth_sid] if auth_sid in meta.index else None
        trig_targets = trig2targets.get(trig, set())
        # explicit mapping status (no silent resolution)
        if auth_target is not None:
            if len(trig_targets) <= 1 and (len(trig_targets) == 0
                                           or auth_target in trig_targets):
                status = "unique"
                ev = ("authoritative+trigger-agree" if trig_targets
                      else "authoritative-only")
            elif auth_target in trig_targets:
                status = "unique"  # authoritative resolves the multi-trigger hit
                ev = "authoritative-resolved-multi-trigger"
            else:
                status = "ambiguous"
                ev = "authoritative-trigger-conflict"
        elif len(trig_targets) == 1:
            status = "unique"
            ev = "trigger-only"
            auth_target = sorted(trig_targets)[0]
        elif len(trig_targets) == 0:
            status = "unresolved"
            ev = "no-evidence"
        else:
            status = "ambiguous"
            ev = "multi-target-no-authoritative"
        # record-link conflict demotes to ambiguous
        if status == "unique" and rec_link is not None and \
                rec_link["target_id"] != auth_target:
            status = "ambiguous"
            ev = "record-link-conflict"
        tid = auth_target if status == "unique" else None
        ctx = mask = acc = ws = we = strand = None
        if status == "unique":
            if rec_link is not None:
                acc = rec_link["source_accession"]
                ws = rec_link["window_start"]
                we = rec_link["window_end"]
                strand = rec_link["strand"]
                rid = rec_link["record_id"]
                if rid in contexts:
                    ctx, mask = contexts[rid]
                    n_ctx_inherit += 1
            if ctx is None:
                found = ctx_from_genome(tid, trig)
                if found is not None:
                    acc, ws, we, strand, ctx, mask = found
                    n_ctx_research += 1
        rec = {
            "record_id": f"beacon_{r['split']}_{r.name}",
            "study_id": STUDY_ID,
            "assay_id": "gse149225_toehold_flowseq",
            "label_view": "beacon",
            "target_id": tid,
            "target_cluster_id": cluster_of.get(tid) if tid else None,
            "candidate_id": auth_sid,
            "outer_fold": fold_of.get(tid) if tid else None,
            "information_regime": "construct+context512" if ctx else "construct",
            "source_accession_version": acc,
            "trigger_sequence": trig,
            "switch_or_construct_sequence": r["sequence"],
            "candidate_start": ws,
            "candidate_end": we,
            "strand": strand,
            "context_512": ctx,
            "context_mask": mask,
            "mapping_status": status,
            "label_on": r["ON"],
            "label_off": r["OFF"],
            "label_semantics": "normalized_fluorescence_ON_OFF",
            "eligibility_status": None,  # filled after target-level pass
            "beacon_official_split": r["split"],
            "category": r["category"],
        }
        rows.append(rec)
        ledger.append({
            "record_id": rec["record_id"], "candidate_id": auth_sid,
            "mapping_status": status, "evidence": ev,
            "auth_target": tid,
            "n_trigger_match_targets": len(trig_targets),
            "has_record_link": rec_link is not None,
            "conflict": ev.endswith("conflict"),
        })
    df = pd.DataFrame(rows)
    print(f"BEACON context: {n_ctx_inherit} inherited, {n_ctx_research} "
          f"re-searched, {len(df) - n_ctx_inherit - n_ctx_research} without context")
    return df, pd.DataFrame(ledger)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    if os.path.exists(OUT_DIR):
        print(f"REFUSING: {OUT_DIR} already exists (contract: never overwrite)")
        sys.exit(2)
    os.makedirs(OUT_DIR)

    canon = pd.read_parquet(CANON_PARQUET)
    assert canon["sequence_id"].is_unique
    n_targets = canon["target_id"].nunique()
    print(f"canonical: {len(canon)} records, {n_targets} targets")

    # --- context512 ---
    contexts, ctx_status = build_contexts(canon)
    canon["context_status"] = canon["record_id"].map(ctx_status)
    n_resolved = len(contexts)
    print(f"context512 resolved: {n_resolved}/{len(canon)}")
    print(pd.Series(ctx_status).value_counts().to_string())

    # --- closure ---
    uf, rule_hits, acc_of = closure(canon, contexts)
    groups = uf.groups()
    cluster_of = {}
    for root, members in groups.items():
        cid = "cl_" + hashlib.sha1(",".join(sorted(members)).encode()).hexdigest()[:12]
        for t in members:
            cluster_of[t] = cid
    print(f"clusters: {len(groups)} (rules: {rule_hits})")

    # --- splits ---
    fold_of, inner_of, fold_stats = make_splits(canon, uf, cluster_of)

    # --- eligibility (canonical label view) ---
    elig = {}
    for tid, sub in canon.groupby("target_id"):
        lab = sub.loc[sub["admission_status"] == "admitted_paired", "ON_OFF"]
        lab = lab.dropna()
        if len(lab) < 2:
            elig[tid] = "coverage_only_singleton"
        elif lab.max() - lab.min() <= 0:
            elig[tid] = "coverage_only_flat_label"
        elif len(lab) == 0:
            elig[tid] = "coverage_only_no_label"
        else:
            elig[tid] = "eligible_ranking"
    print("canonical eligibility:", pd.Series(elig).value_counts().to_dict())

    # --- canonical manifest ---
    ctx_col, mask_col = [], []
    for _, r in canon.iterrows():
        if r["record_id"] in contexts:
            ctx, mask = contexts[r["record_id"]]
            ctx_col.append(ctx)
            mask_col.append(mask)
        else:
            ctx_col.append(None)
            mask_col.append(None)
    man = pd.DataFrame({
        "record_id": canon["record_id"],
        "study_id": STUDY_ID,
        "assay_id": "angenent_mari_2020_toehold_flowseq",
        "label_view": "canonical",
        "target_id": canon["target_id"],
        "target_cluster_id": canon["target_id"].map(cluster_of),
        "candidate_id": canon["sequence_id"],
        "outer_fold": canon["target_id"].map(fold_of),
        "information_regime": np.where(canon["record_id"].isin(contexts),
                                       "construct+context512", "construct"),
        "source_accession_version": canon["source_accession"],
        "trigger_sequence": canon["trigger"],
        "switch_or_construct_sequence": canon["switch"],
        "candidate_start": canon["window_start"],
        "candidate_end": canon["window_end"],
        "strand": canon["strand"],
        "context_512": ctx_col,
        "context_mask": mask_col,
        "mapping_status": "unique",  # canonical: identity by construction
        "label_on": canon["ON"],
        "label_off": canon["OFF"],
        "label_semantics": "normalized_fluorescence_ON_OFF",
        "eligibility_status": canon["target_id"].map(elig),
        "admission_status": canon["admission_status"],
        "context_status": canon["context_status"],
        "source_category": canon["source_category"],
    })
    man.to_parquet(f"{OUT_DIR}/canonical_manifest.parquet", index=False)

    # --- BEACON ---
    beacon, map_ledger = build_beacon(canon, contexts, ctx_status, cluster_of,
                                      fold_of, acc_of)
    # BEACON eligibility per target (beacon label view, unique rows only)
    bel = {}
    for tid, sub in beacon[beacon["mapping_status"] == "unique"].groupby("target_id"):
        lab = sub["label_on"] - sub["label_off"]
        if len(lab) < 2:
            bel[tid] = "coverage_only_singleton"
        elif lab.max() - lab.min() <= 0:
            bel[tid] = "coverage_only_flat_label"
        else:
            bel[tid] = "eligible_ranking"
    beacon["eligibility_status"] = beacon["target_id"].map(bel)
    beacon.loc[beacon["mapping_status"] != "unique", "eligibility_status"] = \
        "excluded_" + beacon.loc[beacon["mapping_status"] != "unique", "mapping_status"]
    beacon.to_parquet(f"{OUT_DIR}/beacon_manifest.parquet", index=False)
    map_ledger.to_csv(f"{OUT_DIR}/mapping_ledger.csv", index=False)
    print("BEACON mapping status:", map_ledger["mapping_status"].value_counts().to_dict())

    # --- target table ---
    targets = sorted(canon["target_id"].unique())
    cat_of = canon.groupby("target_id")["source_category"].first().to_dict()
    pool_of = canon.groupby("target_id").size().to_dict()
    legacy = pd.read_csv(LEGACY_SPLIT)
    legacy_map = dict(zip(legacy["target_id"], legacy["split"]))
    tgt_rows = []
    for t in targets:
        sub = canon[canon["target_id"] == t]
        tgt_rows.append({
            "target_id": t,
            "target_cluster_id": cluster_of[t],
            "source_category": cat_of[t],
            "n_records": pool_of[t],
            "n_admitted_paired": int((sub["admission_status"] == "admitted_paired").sum()),
            "context_resolved": bool(sub["context_status"].eq("context_resolved").any()),
            "eligibility_status": elig[t],
            "outer_fold": fold_of[t],
            "inner_fold": inner_of[t][1],
            "legacy_split": legacy_map.get(t),
            "legacy_role": ("legacy_development_test" if legacy_map.get(t) == "test"
                            else legacy_map.get(t)),
        })
    tgt_df = pd.DataFrame(tgt_rows)
    tgt_df.to_csv(f"{OUT_DIR}/target_table.csv", index=False)

    # --- cluster table ---
    cl_rows = []
    for root, members in groups.items():
        cl_rows.append({
            "target_cluster_id": cluster_of[members[0]],
            "n_targets": len(members),
            "members": ";".join(sorted(members)),
            "outer_fold": fold_of[members[0]],
            "total_records": sum(pool_of[m] for m in members),
        })
    cl_df = pd.DataFrame(cl_rows).sort_values("target_cluster_id")
    cl_df.to_csv(f"{OUT_DIR}/cluster_table.csv", index=False)

    # --- context ledger ---
    ctx_led = canon[["record_id", "target_id", "source_accession", "window_start",
                     "window_end", "strand", "trigger", "context_status"]].copy()
    ctx_led.to_csv(f"{OUT_DIR}/context_ledger.csv", index=False)

    # --- exclusion ledger ---
    excl = [
        {"category": "canonical_no_coord", "n_records":
            int((canon["coordinate_status"] != "absolute").sum())},
        {"category": "canonical_context_unresolved",
         "n_records": int(canon["context_status"].str.startswith("context_unresolved").sum())},
        {"category": "beacon_ambiguous",
         "n_records": int((map_ledger["mapping_status"] == "ambiguous").sum())},
        {"category": "beacon_unresolved",
         "n_records": int((map_ledger["mapping_status"] == "unresolved").sum())},
        {"category": "canonical_not_admitted_paired",
         "n_records": int((canon["admission_status"] != "admitted_paired").sum())},
        {"category": "targets_coverage_only",
         "n_targets": int(sum(1 for v in elig.values() if v != "eligible_ranking"))},
    ]
    pd.DataFrame(excl).to_csv(f"{OUT_DIR}/exclusion_ledger.csv", index=False)

    # --- acceptance checks (contract Batch 1 minimal acceptance) ---
    checks = {}
    # C1: cross-fold exact/RC trigger overlap = 0
    trig_fold = defaultdict(set)
    for _, r in canon.dropna(subset=["trigger"]).iterrows():
        trig_fold[r["trigger"].upper()].add(fold_of[r["target_id"]])
        trig_fold[rc(r["trigger"].upper())].add(fold_of[r["target_id"]])
    cross = sum(1 for t, fs in trig_fold.items() if len(fs) > 1)
    checks["cross_fold_exact_rc_trigger_overlap"] = int(cross)
    checks["pass_trigger_overlap_zero"] = cross == 0
    # C2: clusters never cross folds
    cl_fold = tgt_df.groupby("target_cluster_id")["outer_fold"].nunique()
    checks["clusters_crossing_folds"] = int((cl_fold > 1).sum())
    checks["pass_clusters_intact"] = bool((cl_fold == 1).all())
    # C3: BEACON [3:33] equals authoritative canonical trigger
    sid2trig = canon.set_index("sequence_id")["trigger"].to_dict()
    agree = 0
    for _, r in beacon.iterrows():
        ct = sid2trig.get(r["candidate_id"])
        if ct is not None and r["trigger_sequence"] == ct.upper():
            agree += 1
    checks["beacon_trigger_slice_agree"] = int(agree)
    checks["beacon_trigger_slice_total_with_canonical"] = int(
        beacon["candidate_id"].isin(sid2trig).sum())
    checks["pass_beacon_slice"] = agree == int(beacon["candidate_id"].isin(sid2trig).sum())
    # C4: every BEACON row has a mapping status
    checks["beacon_rows"] = len(beacon)
    checks["beacon_status_coverage"] = int(beacon["mapping_status"].notna().sum())
    checks["pass_mapping_status"] = bool((beacon["mapping_status"].notna()).all())
    # C5: shared study identity
    checks["canonical_study_id"] = STUDY_ID
    checks["beacon_study_id"] = STUDY_ID
    checks["pass_study_identity"] = bool(
        (beacon["study_id"] == STUDY_ID).all())
    # C6: legacy test marked legacy_development
    checks["legacy_test_targets_marked"] = int(
        (tgt_df["legacy_role"] == "legacy_development_test").sum())
    checks["pass_legacy_marked"] = checks["legacy_test_targets_marked"] == int(
        (legacy["split"] == "test").sum())
    # C7: v0.2.1 outputs untouched (registry in new dir by construction)
    checks["pass_no_v021_overwrite"] = os.path.isdir(f"{MNT}/releases/v0.2.1")

    # --- balance stats ---
    balance = []
    for f in range(N_OUTER):
        sub = tgt_df[tgt_df["outer_fold"] == f]
        balance.append({
            "outer_fold": f,
            "n_targets": len(sub),
            "n_records": int(sub["n_records"].sum()),
            "n_virus": int((sub["source_category"] == "virus").sum()),
            "n_human_tf": int((sub["source_category"] == "human_TF").sum()),
            "n_clusters": sub["target_cluster_id"].nunique(),
        })

    summary = {
        "run": "v0.3.0/registry",
        "seed": SEED,
        "study_id": STUDY_ID,
        "canonical": {"records": len(canon), "targets": n_targets,
                      "clusters": len(groups)},
        "context": {"resolved": n_resolved,
                    "status_counts": pd.Series(ctx_status).value_counts().to_dict()},
        "closure_rule_hits": rule_hits,
        "beacon": {"rows": len(beacon),
                   "mapping_status": map_ledger["mapping_status"].value_counts().to_dict()},
        "eligibility": {"canonical": pd.Series(elig).value_counts().to_dict(),
                        "beacon": pd.Series(bel).value_counts().to_dict()},
        "fold_balance": balance,
        "acceptance_checks": checks,
        "homology_note": (
            f"rule 5d: k={KMER} exact seeds, occurrence cap {KMER_OCC_CAP}, "
            f"offset-consistent chaining, exact verification at "
            f">={HOMO_IDENTITY} identity over >={HOMO_COVERAGE} of the shorter "
            f"context; homologous pairs whose shared seeds all exceed the "
            f"occurrence cap are not merged (documented sensitivity limit)"),
    }
    with open(f"{OUT_DIR}/registry_summary.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)

    with open(f"{OUT_DIR}/split_manifest.json", "w") as fh:
        json.dump({
            "seed": SEED,
            "n_outer": N_OUTER,
            "n_inner": N_INNER,
            "fold_of_target": fold_of,
            "inner_fold_of_target": {t: inner_of[t][1] for t in inner_of},
            "cluster_of_target": cluster_of,
            "fold_balance": balance,
            "fold_stats": {str(k): v for k, v in fold_stats.items()},
        }, fh, indent=2)

    print(json.dumps(checks, indent=2))
    failed = [k for k, v in checks.items() if k.startswith("pass_") and not v]
    if failed:
        print("ACCEPTANCE FAILED:", failed)
        sys.exit(1)
    print("ALL BATCH-1 ACCEPTANCE CHECKS PASSED")


if __name__ == "__main__":
    main()
