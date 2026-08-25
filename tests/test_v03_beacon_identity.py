"""Dry unit tests for v03_beacon_identity (no GPU, no training runs)."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import v03_beacon_identity as vbi  # noqa: E402


def test_paper_values_complete():
    # all four required LMs have a paper PRS row with mean+sd
    for m in ("BEACON-B512", "SpliceBERT-MS1024", "RNA-FM", "UTR-LM-MRL"):
        assert m in vbi.PAPER_PRS
        assert vbi.PAPER_PRS[m]["sd"] > 0


def test_model_spec_complete_and_ckpt_rel():
    for m in vbi.PAPER_PRS:
        spec = vbi.MODEL_SPEC[m]
        assert spec["model_type"]
        assert vbi.rel_ckpt(m).startswith(("baseline/", "opensource/"))
        assert spec["max_len"] > 0


def test_verdict_within_2sd():
    v = vbi.verdict(55.20, 55.20, 0.26)
    assert v["within_2sd"] is True


def test_verdict_within_2sd_edge_inside():
    # mean + (2*sd - epsilon) must pass
    v = vbi.verdict(55.20 + 2 * 0.26 - 1e-6, 55.20, 0.26)
    assert v["within_2sd"] is True


def test_verdict_outside_2sd_fails():
    v = vbi.verdict(55.20 + 2 * 0.26 + 1e-3, 55.20, 0.26)
    assert v["within_2sd"] is False


def test_ingest_convention():
    c = vbi.ingest_convention(91534)
    assert c["n_columns"] == 4
    assert c["upper"] is True
    assert c["u_to_t"] is True


def test_run_name_sanitized_lr():
    n = vbi.run_name("BEACON-B512", 0, 1e-5)
    assert n.startswith("BEACON-B512_s0_")
    # no '.' or 'e-0' gaps that would be awkward paths
    assert "." not in n
    assert "e-0" not in n


def test_build_cmd_paths_and_hyperparams():
    cmd = vbi.build_cmd("BEACON-B512", 0, 1e-5, "/out", 3, 26000)
    s = " ".join(cmd)
    assert "train_programmable_rna_switches.py" in s
    assert vbi.CKPT_ROOT in s
    assert vbi.DATA_DIR in s
    assert "--learning_rate 1e-05" in s
    assert "--num_train_epochs 30" in s
    assert "--token_type single" in s
    assert "--model_type rnalm" in s
    assert "--fp16" in s
    assert "--seed 0" in s


def test_beacon_python_interpreter_path_resolves():
    # guards against the double-"ToeholdDesignBench" path bug
    assert os.path.exists(vbi.BEACON_PY), vbi.BEACON_PY
    assert vbi.BEACON_PY.endswith("/envs/beacon/bin/python")


def test_parse_results_none_when_missing(tmp_path):
    assert vbi.parse_results(str(tmp_path)) is None


def test_parse_results_reads_json(tmp_path):
    d = tmp_path / "results" / "r"
    d.mkdir(parents=True)
    (d / "test_results.json").write_text(json.dumps({"eval_r^2_mean": 0.5520}))
    rj = vbi.parse_results(str(d))
    assert rj["eval_r^2_mean"] == 0.5520


def test_scale_r2_to_percent():
    rj = {"eval_r^2_mean": 0.5520}
    assert vbi._scale_r2(rj, "r^2_mean") == pytest.approx(0.5520, rel=1e-6)
    # paper unit is percent; _scale_r2 returns raw 0-1 then caller *100
    assert vbi._scale_r2(rj, "r^2_mean") * 100.0 == pytest.approx(55.20)


def test_is_opensource_partition():
    assert vbi.is_opensource("SpliceBERT-MS1024")
    assert vbi.is_opensource("RNA-FM")
    assert vbi.is_opensource("UTR-LM-MRL")
    assert not vbi.is_opensource("BEACON-B512")


def test_lr_grid_bounds_match_paper_table6():
    assert vbi.LR_SEARCH_GRID[0] == 1e-5
    assert vbi.LR_SEARCH_GRID[-1] == 5e-3
    # strictly increasing
    assert all(a < b for a, b in zip(vbi.LR_SEARCH_GRID, vbi.LR_SEARCH_GRID[1:]))


def test_lr_tag_filesystem_safe():
    for lr in vbi.LR_SEARCH_GRID:
        t = vbi.lr_tag(lr)
        assert "." not in t
        assert " " not in t
        assert "/" not in t
        assert t.startswith("1e") or t.startswith("5e")


def test_search_dir_token_single_lr_prefix():
    # search_sweep wraps lr_tag with exactly one "lr" prefix
    for lr in vbi.LR_SEARCH_GRID:
        tok = f"lr{vbi.lr_tag(lr)}"
        assert tok.startswith("lr1e") or tok.startswith("lr5e")
        assert tok.count("lr") == 1


def test_read_val_best_metric_present_and_missing(tmp_path):
    # missing -> None
    assert vbi.read_val_best_metric(str(tmp_path)) is None
    # present -> returns best_metric fraction
    ts = tmp_path / "trainer_state.json"
    ts.write_text(json.dumps({"best_metric": 0.57}))
    assert vbi.read_val_best_metric(str(tmp_path)) == pytest.approx(0.57)


def test_pick_best_lr_picks_highest_val():
    recs = [
        {"lr": 1e-5, "val_r2_pct": 50.0},
        {"lr": 1e-4, "val_r2_pct": 57.7},
        {"lr": 1e-3, "val_r2_pct": 55.0},
    ]
    assert vbi.pick_best_lr(recs) == 1e-4


def test_pick_best_lr_skips_none_raises_if_all_none():
    recs = [{"lr": 1e-5, "val_r2_pct": None}]
    with pytest.raises(ValueError):
        vbi.pick_best_lr(recs)


def test_pick_best_lr_skips_nan_and_failed():
    import math
    recs = [
        {"lr": 1e-5, "val_r2_pct": 50.0},
        {"lr": 1e-4, "val_r2_pct": 0.5778 * 100.0},
        {"lr": 1e-3, "val_r2_pct": math.nan},
        {"lr": 5e-3, "val_r2_pct": None, "failed": True},
    ]
    # NaN / failed/None high-lr rows must not poison the selection
    assert vbi.pick_best_lr(recs) == 1e-4