import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import retrieval
from app.corpus_validation import validate_corpus as validate_source_corpus


def validate_corpus(documents):
    return validate_source_corpus(documents)


def test_prototype_corpus_has_required_metadata_unique_ids_and_valid_jurisdictions():
    validate_corpus(retrieval._CORPUS)


def test_validator_rejects_duplicate_corpus_ids():
    document = dict(retrieval._CORPUS[0])
    try:
        validate_corpus([document, dict(document)])
    except ValueError as error:
        assert "duplicate id" in str(error)
    else:
        raise AssertionError("Duplicate corpus IDs must fail validation.")


def test_validator_rejects_duplicate_provision_with_different_ids():
    first = dict(retrieval._CORPUS[0])
    second = dict(first, id="DIFFERENT-ID")
    try:
        validate_corpus([first, second])
    except ValueError as error:
        assert "duplicate jurisdiction/title/section" in str(error)
    else:
        raise AssertionError("Duplicate jurisdiction/title/section records must fail.")


def test_validator_rejects_missing_required_metadata():
    document = dict(retrieval._CORPUS[0])
    document["precision"] = ""
    try:
        validate_corpus([document])
    except ValueError as error:
        assert "precision" in str(error)
    else:
        raise AssertionError("Missing corpus metadata must fail validation.")
