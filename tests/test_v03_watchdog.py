"""Tests for the start-only watchdog (contract: never kill; resume-safe)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import v03_watchdog as wd  # noqa: E402


def test_fold_state_tune_when_no_selection(tmp_path):
    assert wd.fold_state(str(tmp_path), "cnn60", 0) == "tune"


def test_fold_state_final_when_selection_but_missing_finals(tmp_path):
    d = tmp_path / "tune_cnn60_f0"
    d.mkdir()
    (d / "selection.json").write_text("{}")
    assert wd.fold_state(str(tmp_path), "cnn60", 0) == "final"


def test_fold_state_done_when_all_manifests(tmp_path):
    d = tmp_path / "tune_cnn60_f0"
    d.mkdir()
    (d / "selection.json").write_text("{}")
    for abl in wd.ABLATIONS:
        for s in wd.SEEDS:
            r = tmp_path / f"final_cnn60_f0_{abl}_s{s}"
            r.mkdir()
            (r / "run_manifest.json").write_text("{}")
    assert wd.fold_state(str(tmp_path), "cnn60", 0) == "done"


def test_parse_ps_extracts_streams():
    ps = (
        "root  1  python -u src/v03_tune.py --backbone rnaelectra "
        "--outer-fold 1 --phase tune --cuda-device 4\n"
        "root  2  python -u src/v03_tblr.py --backbone sandstorm "
        "--outer-fold 3 --run-id final_sandstorm_f3_x_s1\n"
        "root  3  python something_else.py --backbone cnn60\n"
    )
    entries = wd.parse_ps(ps)
    assert ("orchestrator", "rnaelectra", 1, 4) in entries
    assert ("trainer", "sandstorm", 3, None) in entries
    assert len(entries) == 2


def test_stream_active_orphan_child_counts():
    entries = [("trainer", "sandstorm", 2, None)]
    assert wd.stream_active(entries, "sandstorm", 2)
    assert not wd.stream_active(entries, "sandstorm", 3)


def test_pick_gpu_prefers_device_with_room():
    free = {0: 9.7, 1: 3.0, 4: 8.0}
    assert wd.pick_gpu(free, prefer=4) == 4
    assert wd.pick_gpu(free, prefer=1) == 0  # falls back to max free
    assert wd.pick_gpu({0: 1.0}) is None


def test_pick_gpu_ignores_mig_by_pre_filter():
    # MIG slices are pre-filtered by gpu_free_map; pick_gpu only sees full GPUs
    free = {6: 3.3, 7: 4.7, 2: 12.0}
    assert wd.pick_gpu(free) == 2
