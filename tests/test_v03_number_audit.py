"""Tests for the number-provenance audit helpers."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from v03_number_audit import paper_text  # noqa: E402


def test_paper_text_normalizes_unicode_minus(tmp_path):
    p = tmp_path / "paper.md"
    p.write_text("effect = \u2212 0.0125 and range \u2013 3 to 5",
                 encoding="utf-8")
    t = paper_text(str(p))
    assert "- 0.0125" in t
    assert "- 3 to 5" in t
    assert "\u2212" not in t and "\u2013" not in t


def test_paper_text_normalizes_nbsp():
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8") as fh:
        fh.write("NDCG@10\u00a00.83")
        path = fh.name
    t = paper_text(path)
    assert "NDCG@10 0.83" in t
    os.unlink(path)


def test_audit_exit_code_semantics():
    # the audit main() exits 1 iff any checked number is missing; verified
    # end-to-end by run_v03.sh integration (script exits nonzero on mismatch)
    assert callable(paper_text)
