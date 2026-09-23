"""
Runs the real eval benchmark (app/eval_runner.py) as part of the normal test
suite, so a future corpus edit, classifier tweak, or retrieval change that
regresses accuracy or (much worse) breaks jurisdiction isolation or citation
integrity fails CI immediately instead of being caught by chance in a demo.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app  # noqa: E402
from app import eval_runner  # noqa: E402

_MIN_ACCEPTABLE_ACCURACY = 0.85


def test_hard_invariants_are_zero():
    """These two must ALWAYS be zero. Anything else is a correctness bug —
    not a metric to track over time, a build-breaking regression."""
    report = eval_runner.run_benchmark(app)
    assert report["jurisdiction_isolation_violations"] == 0, (
        "A source from the wrong jurisdiction leaked into an answer — "
        f"see per_item for details: {report['per_item']}"
    )
    assert report["citation_integrity_violations"] == 0, (
        "The answer text cited a source that wasn't actually retrieved — "
        f"see per_item for details: {report['per_item']}"
    )


def test_classification_accuracy_above_threshold():
    report = eval_runner.run_benchmark(app)
    assert report["classification_accuracy"] is not None
    assert report["classification_accuracy"] >= _MIN_ACCEPTABLE_ACCURACY


def test_abstention_accuracy_above_threshold():
    report = eval_runner.run_benchmark(app)
    assert report["abstention_accuracy"] is not None
    assert report["abstention_accuracy"] >= _MIN_ACCEPTABLE_ACCURACY


def test_citation_hit_rate_above_threshold():
    report = eval_runner.run_benchmark(app)
    assert report["citation_hit_rate"] is not None
    assert report["citation_hit_rate"] >= _MIN_ACCEPTABLE_ACCURACY
