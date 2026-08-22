"""Tests for the VISTA SARS-CoV selection-conditioned analysis."""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import v03_vista_sars as vs  # noqa: E402


def test_parse_group():
    assert vs.parse_group("VISTA_GFP_low_onoff_1032") == "VISTA_GFP_low_onoff"
    assert vs.parse_group("tsgen2_GFP_SARSCoV2_11_N_5") == \
        "tsgen2_GFP_SARSCoV2_11_N"
    assert vs.parse_group("VISTA_LacZ_SARS_COV_2_N_12") == \
        "VISTA_LacZ_SARS_COV_2_N"


def test_load_groups_alignment_and_shape():
    df = vs.load_groups()
    assert len(df) == 72
    assert df["group"].nunique() == 6
    assert set(df["group"].value_counts()) == {12}
    # alignment invariant enforced inside load_groups (would raise otherwise)
    assert (df["trigger30"].str.len() == 30).all()
    assert (df["switch30"].str.len() == 30).all()


def test_group_summary_contains_all_groups():
    df = vs.load_groups()
    s = vs.group_summary(df, "ON/OFF Full RNA ")
    assert len(s) == 6
    assert set(s["group"]) == set(df["group"])
    assert (s["n"] == 12).all()


@pytest.mark.parametrize("g,expect_higher", [
    ("VISTA_GFP_high_onoff", "VISTA_GFP_low_onoff"),
])
def test_vista_selection_groups_separate_measured_onoff(g, expect_higher):
    # paper-native check: VISTA's high-onoff selection group should measure
    # higher ON/OFF than the low group (the paper's own validation design)
    df = vs.load_groups()
    hi = df[df["group"] == g]["ON/OFF Full RNA "].mean()
    lo = df[df["group"] == expect_higher]["ON/OFF Full RNA "].mean()
    assert hi > lo


def test_construct59_window_after_t7_promoter():
    df = vs.load_groups()
    cons = vs.construct59_of(df)
    assert len(cons) == 72
    assert all(len(c) == 59 for c in cons)
    # the toehold (switch30) must be the first 30 nt of the construct window
    for c, s30 in zip(cons, df["switch30"]):
        assert c[:30] == s30
