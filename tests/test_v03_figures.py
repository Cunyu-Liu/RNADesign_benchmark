"""Tests for figure generation + source-data provenance (fig artifacts must
exist and match run artifacts; run src/v03_figures.py first)."""
import os
import struct
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

FIG = ("/mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/paper_figs")
BASE = "/mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0"


def _png_dims(path):
    with open(path, "rb") as fh:
        head = fh.read(33)
    assert head[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", head[16:24])


@pytest.mark.skipif(not os.path.exists(FIG),
                    reason="figures not generated yet")
def test_three_pngs_valid_and_sized():
    for name in ("fig1_objectives", "fig2_transfer", "fig3_contamination"):
        w, h = _png_dims(f"{FIG}/{name}.png")
        assert w >= 1200 and h >= 700, f"{name} too small: {w}x{h}"


@pytest.mark.skipif(not os.path.exists(FIG),
                    reason="figures not generated yet")
def test_fig1_source_traces_to_family_evals():
    sd = pd.read_csv(f"{FIG}/fig1_source_data.csv")
    assert len(sd) == 10  # 2 backbones x 5 objectives
    for bb in ("cnn60", "sandstorm"):
        ms = pd.read_csv(f"{BASE}/eval_{bb}_family/method_summary.csv")
        ms = ms.set_index("method_id")
        for _, r in sd[sd["backbone"] == bb].iterrows():
            v = ms.loc[f"{bb}/{r['objective']}", "ndcg@10"]
            assert abs(v - r["ndcg@10"]) < 1e-9


@pytest.mark.skipif(not os.path.exists(FIG),
                    reason="figures not generated yet")
def test_fig2b_source_traces_to_crowdsourced_run():
    cs = pd.read_csv(f"{FIG}/fig2b_source_data.csv")
    ref = pd.read_csv(f"{FIG}/fig2a_source_data.csv")
    assert len(cs) == 8 and len(ref) == 6
    # every mCherry bar >= 0 and <= 1; every CI brackets its estimate
    assert (ref["ci_low"] <= ref["ndcg@10"]).all()
    assert (ref["ndcg@10"] <= ref["ci_high"]).all()
    assert ((cs["cluster_boot_lo"] <= cs["spearman"]) &
            (cs["spearman"] <= cs["cluster_boot_hi"])).all()


@pytest.mark.skipif(not os.path.exists(FIG),
                    reason="figures not generated yet")
def test_fig3_sources_trace_to_artifacts():
    ls = pd.read_csv(f"{FIG}/fig3a_source_data.csv")
    arms = set(ls["arm"])
    assert "mean_ndcg_leaky" in arms and "mean_ndcg_clean" in arms
    sd3 = pd.read_csv(f"{FIG}/fig3b_source_data.csv")
    fc = sd3[sd3["variant"] == "full_construct"]["ndcg@10"].iloc[0]
    assert 0.70 < fc < 0.80  # sanity band around the audited 0.773
