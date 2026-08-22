"""Tests for the gate-6 sensitivity analysis (contract §12 gate 6)."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

BASE = ("/mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0")
OUT = f"{BASE}/sensitivity_gate6"


@pytest.mark.skipif(not os.path.exists(f"{OUT}/sensitivity_summary.json"),
                    reason="sensitivity artifacts not generated yet")
def test_no_reversal_and_all_variants_present():
    import json
    res = json.load(open(f"{OUT}/sensitivity_summary.json"))
    assert res["reversals"] == []
    assert res["conclusion"].startswith("NO REVERSAL")
    df = pd.read_csv(f"{OUT}/sensitivity_primary_contrast.csv")
    assert len(df) == 8  # 2 backbones x 4 variants
    assert set(df["variant"]) == {"full", "excl_legacy",
                                  "excl_context_unresolved", "excl_both"}


@pytest.mark.skipif(not os.path.exists(f"{OUT}/sensitivity_summary.json"),
                    reason="sensitivity artifacts not generated yet")
def test_full_variant_reproduces_main_contrast():
    """The 'full' sensitivity variant must equal the family-eval contrast
    (same kernel, same data) -- consistency evidence, not a new analysis."""
    df = pd.read_csv(f"{OUT}/sensitivity_primary_contrast.csv")
    for bb, ref in (("cnn60", -0.012497), ("sandstorm", -0.020448)):
        v = df[(df["backbone"] == bb) & (df["variant"] == "full")].iloc[0]
        assert abs(v["mean_diff"] - ref) < 1e-6, \
            f"{bb} full variant {v['mean_diff']} != family eval {ref}"


@pytest.mark.skipif(not os.path.exists(f"{OUT}/sensitivity_summary.json"),
                    reason="sensitivity artifacts not generated yet")
def test_exclusions_shrink_target_sets():
    df = pd.read_csv(f"{OUT}/sensitivity_primary_contrast.csv")
    for bb in ("cnn60", "sandstorm"):
        sub = df[df["backbone"] == bb].set_index("variant")
        assert sub.loc["full", "n_targets"] == 917
        assert sub.loc["excl_legacy", "n_targets"] == 778  # 139 legacy
        assert sub.loc["excl_context_unresolved", "n_targets"] == 630
        assert sub.loc["excl_both", "n_targets"] == 542
        # every restricted CI stays on the same side of zero as the full one
        assert (sub["ci_high"] < 0).all()


@pytest.mark.skipif(not os.path.exists(f"{OUT}/sensitivity_summary.json"),
                    reason="sensitivity artifacts not generated yet")
def test_ambiguous_beacon_rows_are_zero_by_construction():
    import json
    res = json.load(open(f"{OUT}/sensitivity_summary.json"))
    assert res["n_ambiguous_beacon_rows_in_eligible"] == 0
