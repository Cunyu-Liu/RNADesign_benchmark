"""Tests for the method x dataset exposure matrix (contract §9 Batch 4)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import v03_exposure_matrix as em  # noqa: E402


def test_canonical_trained_never_independent_on_canonical_or_beacon():
    for mid in ("cnn60/full_tblr", "sandstorm/tb_mse", "transfer-cnn60",
                "lightgbm-biophys"):
        st, _ = em.cell_for(mid, em.DATASETS[0])
        assert st == "EXPOSED_TRAIN"
        st, _ = em.cell_for(mid, em.DATASETS[1])
        assert st == "SAME_STUDY_VIEW", "BEACON never independent (contract)"


def test_external_tracks_independent_for_canonical_trained():
    for mid in ("cnn60/full_tblr", "transfer-cnn60"):
        for ds in ("VISTA mCherry", "crowdsourced 100-regulator"):
            st, _ = em.cell_for(mid, ds)
            assert st == "INDEPENDENT"


def test_sandstorm_own_designs_not_independent_for_sandstorm():
    st, _ = em.cell_for("SANDSTORM-official", "SANDSTORM released designs")
    assert st == "OWN_STUDY"
    # and description-only for everyone else
    st, _ = em.cell_for("cnn60/full_tblr", "SANDSTORM released designs")
    assert st == "SELECTION_CONDITIONED"


def test_vista_official_models_own_study():
    st, _ = em.cell_for("vista-tsgen2", "VISTA mCherry")
    assert st == "OWN_STUDY"


def test_no_training_and_pending_statuses():
    st, _ = em.cell_for("exact-random", em.DATASETS[0])
    assert st == "NO_TRAINING"
    st, _ = em.cell_for("RNA-FM", em.DATASETS[0])
    assert st == "PENDING"


def test_every_registered_method_covered():
    mids = ["exact-random", "gc-baseline", "thermo-scorer",
            "lightgbm-biophys", "lightgbm-seq", "lightgbm-combined",
            "cnn60/full_tblr", "cnn60/tb_mse", "cnn60/rowwise_mse",
            "cnn60/tb_dual", "cnn60/tb_lambdarank", "sandstorm/full_tblr",
            "sandstorm/tb_mse", "SANDSTORM-official", "Valeri-CNN-official",
            "beacon-mask/trigger_only", "rnaelectra/full_tblr",
            "rnaelectra/tb_mse", "vista-tsgen2", "vista-plsda-full",
            "transfer-cnn60", "transfer-sandstorm", "BEACON-B512", "SpliceBERT-MS1024", "RNA-FM",
            "UTR-LM-MRL"]
    rows = em.build_matrix(mids)
    assert len(rows) == len(mids)
    for row in rows:
        for ds in em.DATASETS:
            assert row[ds] in {
                "EXPOSED_TRAIN", "SAME_STUDY_VIEW", "INDEPENDENT",
                "OWN_STUDY", "SELECTION_CONDITIONED", "NO_TRAINING",
                "PENDING"}


def test_unknown_method_raises():
    with pytest.raises(KeyError):
        em.cell_for("unknown-method", em.DATASETS[0])
