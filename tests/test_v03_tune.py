"""Tests for the tuning orchestrator (contract §7: per-backbone env)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import v03_tune as vt  # noqa: E402


def test_interpreter_for_rnaelectra_uses_dedicated_env():
    # contract: rnaelectra needs transformers 4.49 (dedicated env on /mnt)
    assert vt.interpreter_for("rnaelectra") == vt.PY_RNAELECTRA
    assert "rnaelectra" in vt.PY_RNAELECTRA
    assert vt.PY_RNAELECTRA.startswith("/mnt/cunyuliu/")


def test_interpreter_for_other_backbones_use_toeholdbench():
    for bb in ("cnn60", "sandstorm"):
        assert vt.interpreter_for(bb) == vt.PY
    assert vt.PY.startswith("/home/cunyuliu/miniconda3/envs/toeholdbench")


def test_config_grid_is_12_and_frozen():
    cfgs = vt.configs()
    assert len(cfgs) == 12
    assert {c["lr_mult"] for c in cfgs} == {0.5, 1.0, 2.0}
    assert {c["weight_decay"] for c in cfgs} == {"0", "default"}
    assert {c["aux"] for c in cfgs} == {0.1, 0.5}
    assert vt.FINAL_SEEDS == [20260821, 20260822, 20260823, 20260824, 20260825]
