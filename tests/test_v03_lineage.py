"""Tests: §2 data-lineage manuscript claims vs registry_v3 artifacts
(contract §9: auditable claims; every manuscript number traces to an
artifact)."""

import json
import os

import pandas as pd
import pytest

REG = ("/mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/registry_v3")


@pytest.fixture(scope="module")
def tt():
    return pd.read_csv(f"{REG}/target_table.csv")


@pytest.fixture(scope="module")
def can():
    return pd.read_parquet(f"{REG}/canonical_manifest.parquet")


@pytest.mark.skipif(not os.path.exists(f"{REG}/target_table.csv"),
                    reason="registry_v3 not on this machine")
def test_registry_shape_claims(tt, can):
    assert tt["target_id"].nunique() == 931
    assert tt["target_cluster_id"].nunique() == 908
    assert len(can) == 92731


@pytest.mark.skipif(not os.path.exists(f"{REG}/split_manifest.json"),
                    reason="registry_v3 not on this machine")
def test_fold_split_and_cluster_purity(tt):
    with open(f"{REG}/split_manifest.json") as fh:
        sm = json.load(fh)
    counts = {}
    for _, f in sm["fold_of_target"].items():
        counts[f] = counts.get(f, 0) + 1
    assert sorted(counts.values()) == [186, 186, 186, 186, 187]
    cl_fold = tt.groupby("target_cluster_id")["outer_fold"].nunique()
    assert (cl_fold == 1).all()


@pytest.mark.skipif(not os.path.exists(f"{REG}/canonical_manifest.parquet"),
                    reason="registry_v3 not on this machine")
def test_context_and_eligibility_counts(can):
    assert (can["context_status"] == "context_resolved").sum() == 87989
    el = can[can["eligibility_status"] == "eligible_ranking"]
    assert el["target_id"].nunique() == 917
    assert len(el) == 52852


@pytest.mark.skipif(not os.path.exists(f"{REG}/mapping_ledger.csv"),
                    reason="registry_v3 not on this machine")
def test_beacon_mapping_ledger_counts():
    ml = pd.read_csv(f"{REG}/mapping_ledger.csv")
    ms = ml["mapping_status"].value_counts().to_dict()
    assert ms.get("unique") == 87829
    assert ms.get("unresolved") == 3705


@pytest.mark.skipif(not os.path.exists(f"{REG}/target_table.csv"),
                    reason="registry_v3 not on this machine")
def test_legacy_test_demoted(tt):
    lr = tt["legacy_role"].value_counts().to_dict()
    assert lr.get("legacy_development_test") == 140
