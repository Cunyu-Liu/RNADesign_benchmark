"""Tests for v0.3.0 Batch 1 registry (src/v03_registry.py).

Synthetic tests exercise the closure rules and split invariants on tiny data.
Integration tests verify contract acceptance criteria against the real registry
outputs in /mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/registry/ (skipped if
the registry has not been built yet).
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from v03_registry import (  # noqa: E402
    UF, rc, CONTEXT_LEN, FLANK, TRIGGER_LEN, N_OUTER,
)

REG = "/mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/registry_v3"


# ---------------------------------------------------------------------------
# synthetic: union-find closure semantics
# ---------------------------------------------------------------------------
def test_uf_union_and_groups():
    uf = UF(["a", "b", "c", "d"])
    uf.union("a", "b")
    uf.union("b", "c")
    groups = uf.groups()
    assert len(groups) == 2
    assert set(groups[uf.find("a")]) == {"a", "b", "c"}
    assert uf.find("d") == "d"


def test_rc():
    assert rc("AACT") == "AGTT"
    assert rc(rc("ACGTN")) == "ACGTN"


def test_context_geometry():
    assert CONTEXT_LEN == 512
    assert FLANK == 241
    assert TRIGGER_LEN == 30


# ---------------------------------------------------------------------------
# synthetic: closure rule semantics on a mini-canonical frame
# ---------------------------------------------------------------------------
def _mini_canon():
    return pd.DataFrame({
        "record_id": ["r1", "r2", "r3", "r4", "r5"],
        "target_id": ["vA", "vB", "tfX", "tfY", "tfZ"],
        "source_category": ["virus", "virus", "human_TF", "human_TF", "human_TF"],
        "trigger": [
            "A" * 30,          # vA
            "A" * 30,          # vB: exact duplicate of vA trigger -> rule 5b
            "C" * 30,          # tfX
            rc("C" * 30),      # tfY: RC of tfX trigger -> rule 5b
            "G" * 30,          # tfZ
        ],
        "source_accession": ["ACCV1", "ACCV2", "ACCT1", "ACCT1", "ACCT2"],
        "window_start": [101, 201, 501, 95001, 501],
        "window_end": [130, 230, 530, 95030, 530],
        "strand": ["forward"] * 5,
        "coordinate_status": ["absolute"] * 5,
        "admission_status": ["admitted_paired"] * 5,
        "ON_OFF": [1.0, 2.0, 1.0, 3.0, 0.5],
        "sequence_id": ["s1", "s2", "s3", "s4", "s5"],
    })


def test_closure_rules_fire():
    import v03_registry as vr
    canon = _mini_canon()
    contexts = {}  # skip rule 5d (no real sequences)
    uf, hits, _ = vr.closure(canon, contexts)
    # 5a: tfX & tfY share ACCT1
    assert uf.find("tfX") == uf.find("tfY")
    # 5b: vA/vB exact trigger; tfX/tfY RC trigger
    assert uf.find("vA") == uf.find("vB")
    # vA and tfX are separate (different accession, different trigger)
    assert uf.find("vA") != uf.find("tfX")
    assert uf.find("tfZ") == uf.find("tfZ")


def test_rule_5c_interval_overlap_without_shared_accession_not_merged():
    """Same accession already merges (5a); different accessions never merge via 5c."""
    import v03_registry as vr
    canon = pd.DataFrame({
        "record_id": ["r1", "r2"],
        "target_id": ["t1", "t2"],
        "source_category": ["human_TF", "human_TF"],
        "trigger": ["A" * 30, "C" * 30],
        "source_accession": ["ACC1", "ACC2"],
        "window_start": [100, 110],  # overlapping intervals but different accessions
        "window_end": [129, 139],
        "strand": ["forward", "forward"],
        "coordinate_status": ["absolute", "absolute"],
        "admission_status": ["admitted_paired"] * 2,
        "ON_OFF": [1.0, 2.0],
        "sequence_id": ["s1", "s2"],
    })
    uf, _, _ = vr.closure(canon, {})
    assert uf.find("t1") != uf.find("t2")


def test_split_keeps_clusters_intact():
    import v03_registry as vr
    canon = _mini_canon()
    uf, _, _ = vr.closure(canon, {})
    cluster_of = {}
    for root, members in uf.groups().items():
        cid = "cl_" + str(len(members)) + "_"
        for t in members:
            cluster_of[t] = cid
    fold_of, inner_of, _ = vr.make_splits(canon, uf, cluster_of)
    # every cluster's members share one fold
    by_cluster = {}
    for t, f in fold_of.items():
        by_cluster.setdefault(cluster_of[t], set()).add(f)
    assert all(len(fs) == 1 for fs in by_cluster.values())
    # folds partition all targets
    assert len(fold_of) == canon["target_id"].nunique()
    assert set(fold_of.values()) <= set(range(N_OUTER))


# ---------------------------------------------------------------------------
# integration: real registry outputs (contract Batch-1 acceptance)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def reg():
    if not os.path.isdir(REG):
        pytest.skip("registry not built yet")
    return REG


def test_registry_summary_all_checks_pass(reg):
    import json
    with open(f"{reg}/registry_summary.json") as fh:
        s = json.load(fh)
    checks = s["acceptance_checks"]
    failed = [k for k, v in checks.items() if k.startswith("pass_") and not v]
    assert not failed, f"acceptance failures: {failed}"
    assert checks["cross_fold_exact_rc_trigger_overlap"] == 0
    assert checks["clusters_crossing_folds"] == 0
    # fold balance: every fold populated within [0.5x, 1.5x] of N/5
    counts = checks["fold_target_counts"]
    assert len(counts) == N_OUTER
    n = sum(counts.values())
    for f, c in counts.items():
        assert 0.5 * n / N_OUTER <= c <= 1.5 * n / N_OUTER, f"fold {f}: {c}"


def test_eligible_rows_have_finite_labels(reg):
    import numpy as np
    df = pd.read_parquet(f"{reg}/canonical_manifest.parquet")
    el = df[df["eligibility_status"] == "eligible_ranking"]
    assert len(el) > 0
    assert np.isfinite(el["label_on"].astype(float)).all()
    assert np.isfinite(el["label_off"].astype(float)).all()
    # every fold has eligible targets
    by_fold = el.groupby("outer_fold")["target_id"].nunique()
    assert (by_fold > 0).all()


def test_canonical_manifest_schema(reg):
    df = pd.read_parquet(f"{reg}/canonical_manifest.parquet")
    required = [
        "record_id", "study_id", "assay_id", "label_view", "target_id",
        "target_cluster_id", "candidate_id", "outer_fold", "information_regime",
        "source_accession_version", "trigger_sequence",
        "switch_or_construct_sequence", "candidate_start", "candidate_end",
        "strand", "context_512", "context_mask", "mapping_status",
        "label_on", "label_off", "label_semantics", "eligibility_status",
    ]
    for c in required:
        assert c in df.columns, f"missing column {c}"
    assert (df["study_id"] == "angenent_mari_2020").all()
    assert (df["label_view"] == "canonical").all()


def test_context_center_equals_trigger(reg):
    df = pd.read_parquet(f"{reg}/canonical_manifest.parquet")
    have = df[df["context_512"].notna()]
    assert len(have) > 0
    bad = 0
    for ctx, trig in zip(have["context_512"], have["trigger_sequence"]):
        if ctx[FLANK:FLANK + TRIGGER_LEN] != trig.upper():
            bad += 1
    assert bad == 0
    # mask marks real bases; context length is 512
    assert (have["context_512"].str.len() == CONTEXT_LEN).all()
    assert (have["context_mask"].str.len() == CONTEXT_LEN).all()
    # padded positions are N and masked 0
    for ctx, mask in zip(have["context_512"].head(50), have["context_mask"].head(50)):
        for ch, m in zip(ctx, mask):
            if ch == "N":
                assert m == "0"
            else:
                assert m == "1"


def test_beacon_manifest_and_mapping(reg):
    df = pd.read_parquet(f"{reg}/beacon_manifest.parquet")
    assert len(df) == 91534
    assert (df["study_id"] == "angenent_mari_2020").all()
    assert (df["label_view"] == "beacon").all()
    # every row has a status in the allowed set
    assert set(df["mapping_status"].unique()) <= {"unique", "ambiguous", "unresolved"}
    # trigger is exactly the [3:33] slice of the construct
    slices_ok = (df["trigger_sequence"] ==
                 df["switch_or_construct_sequence"].str.slice(3, 33))
    assert slices_ok.all()
    # ambiguous rows are never eligible
    assert (df.loc[df["mapping_status"] == "ambiguous", "eligibility_status"]
            .str.startswith("excluded_").all())


def test_beacon_slice_matches_authoritative_trigger(reg):
    canon = pd.read_parquet(f"{reg}/canonical_manifest.parquet")
    beacon = pd.read_parquet(f"{reg}/beacon_manifest.parquet")
    sid2trig = canon.set_index("candidate_id")["trigger_sequence"].to_dict()
    both = beacon[beacon["candidate_id"].isin(sid2trig)]
    assert len(both) > 0
    mism = (both["trigger_sequence"] !=
            both["candidate_id"].map(sid2trig).str.upper()).sum()
    assert mism == 0


def test_cluster_and_target_tables(reg):
    tgt = pd.read_csv(f"{reg}/target_table.csv")
    cl = pd.read_csv(f"{reg}/cluster_table.csv")
    # clusters intact: one fold per cluster
    assert (tgt.groupby("target_cluster_id")["outer_fold"].nunique() == 1).all()
    # cluster table fold equals member fold
    m = tgt.groupby("target_cluster_id")["outer_fold"].first()
    assert (cl.set_index("target_cluster_id")["outer_fold"] == m).all()
    # legacy test targets marked
    legacy_test = tgt[tgt["legacy_split"] == "test"]
    assert (legacy_test["legacy_role"] == "legacy_development_test").all()
    assert len(legacy_test) == 140


def test_cross_fold_trigger_overlap_zero(reg):
    tgt = pd.read_csv(f"{reg}/target_table.csv")
    canon = pd.read_parquet(f"{reg}/canonical_manifest.parquet")
    fold_of = dict(zip(tgt["target_id"], tgt["outer_fold"]))
    from collections import defaultdict
    trig_fold = defaultdict(set)
    for trig, tid in zip(canon["trigger_sequence"], canon["target_id"]):
        t = str(trig).upper()
        trig_fold[t].add(fold_of[tid])
        trig_fold[rc(t)].add(fold_of[tid])
    cross = [t for t, fs in trig_fold.items() if len(fs) > 1]
    assert cross == []


def test_mapping_ledger_exists_with_status(reg):
    led = pd.read_csv(f"{reg}/mapping_ledger.csv")
    assert len(led) == 91534
    assert led["mapping_status"].notna().all()
    assert set(led["mapping_status"].unique()) <= {"unique", "ambiguous", "unresolved"}


def test_exclusion_ledger_and_split_manifest(reg):
    excl = pd.read_csv(f"{reg}/exclusion_ledger.csv")
    assert len(excl) > 0
    import json
    with open(f"{reg}/split_manifest.json") as fh:
        sm = json.load(fh)
    assert sm["seed"] == 20260821
    assert sm["n_outer"] == 5 and sm["n_inner"] == 3
    assert len(sm["fold_of_target"]) == tgt_count(reg)


def tgt_count(reg):
    return len(pd.read_csv(f"{reg}/target_table.csv"))
