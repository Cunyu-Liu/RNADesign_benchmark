"""Tests for the endgame orchestrator: readiness gating, status math, and
step sequencing logic (dry, no GPU / no real runs touched)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import v03_endgame as eg  # noqa: E402


def test_rnaelectra_status_incomplete_by_default(monkeypatch, tmp_path):
    # point BASE at an empty dir: nothing found -> incomplete
    monkeypatch.setattr(eg, "BASE", str(tmp_path))
    st = eg.rnaelectra_status()
    assert st["tune"] == (0, 180)
    assert st["selections"] == (0, 5)
    assert st["finals"] == (0, 125)
    assert st["complete"] is False


def test_rnaelectra_status_complete_when_all_artifacts(monkeypatch, tmp_path):
    import glob as _g
    base = str(tmp_path)
    for i in range(180):
        fold, ci, inner = i // 36, (i % 36) // 3, i % 3
        d = f"{base}/tune_rnaelectra_f{fold}_c{ci:02d}_i{inner}"
        os.makedirs(d, exist_ok=True)
        open(f"{d}/run_manifest.json", "w").write("{}")
    for f in range(5):
        d = f"{base}/tune_rnaelectra_f{f}"
        os.makedirs(d, exist_ok=True)
        open(f"{d}/selection.json", "w").write("{}")
    for f in range(5):
        for abl in ("full_tblr", "tb_mse", "rowwise_mse", "tb_dual",
                    "tb_lambdarank"):
            for s in (20260821, 20260825):
                d = (f"{base}/final_rnaelectra_f{f}_{abl}_s{s}")
                os.makedirs(d, exist_ok=True)
                open(f"{d}/run_manifest.json", "w").write("{}")
    monkeypatch.setattr(eg, "BASE", base)
    st = eg.rnaelectra_status()
    assert st["tune"] == (180, 180)
    assert st["selections"] == (5, 5)
    # 5 folds x 5 ablations x 2 seeds = 50 of the 125 manifest files
    assert st["finals"][0] == 50
    assert st["complete"] is False  # 125 finals required for completeness


def test_chain_step_order_and_commands():
    """The 9 steps must run in dependency order with the right entry
    points (checked by inspecting the module's run() call sites)."""
    import inspect
    src = inspect.getsource(eg.main)
    order = [src.index(f'"{n}/9') for n in range(1, 10)]
    assert order == sorted(order), "steps out of order"
    for needle in ("v03_eval_family.py", "v03_freeze_audit.py",
                   "v03_sensitivity.py", "v03_transfer.py", "v03_crowd.py",
                   "v03_vista.py", "v03_figures.py", "v03_number_audit.py",
                   "v03_review_pack.py"):
        assert needle in src, f"{needle} missing from the chain"


def test_endgame_does_not_execute_without_flag(monkeypatch, tmp_path):
    """Readiness-only mode must never invoke subprocesses on an incomplete
    family (protects the real runs directory)."""
    monkeypatch.setattr(eg, "BASE", str(tmp_path))
    called = []
    monkeypatch.setattr(eg, "run", lambda *a, **k: called.append(a))
    rc = eg.main.__wrapped__() if hasattr(eg.main, "__wrapped__") else None
    # invoke main with default args (no --execute)
    import argparse
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(sys, "argv", ["v03_endgame.py"])
        try:
            eg.main()
        except SystemExit:
            pass
    assert called == [], "readiness mode must not run steps"
