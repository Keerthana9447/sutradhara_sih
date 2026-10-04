"""Fail-fast validation for the curated, jurisdiction-tagged evidence corpus."""
from typing import Any, Dict, Iterable, List

REQUIRED_CORPUS_FIELDS = (
    "id", "title", "jurisdiction", "domain", "source_type", "section",
    "summary", "version_date", "retrieved_date", "source_url", "authority",
    "precision",
)
VALID_JURISDICTIONS = {"India", "International"}


def validate_corpus(documents: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate every source record and return it as a materialized list.

    Invalid corpus metadata is a deployment/data-integrity error and should
    stop startup rather than yield incomplete or ambiguously cited evidence.
    """
    records = list(documents)
    seen_ids = set()
    seen_provisions = set()
    errors = []

    for index, document in enumerate(records):
        if not isinstance(document, dict):
            errors.append(f"document at index {index} is not an object")
            continue

        doc_id = document.get("id")
        label = doc_id if isinstance(doc_id, str) and doc_id.strip() else f"index {index}"
        if not isinstance(doc_id, str) or not doc_id.strip():
            errors.append(f"{label}: missing non-empty id")
        elif doc_id in seen_ids:
            errors.append(f"{label}: duplicate id")
        else:
            seen_ids.add(doc_id)

        provision_key = (
            document.get("jurisdiction"),
            document.get("title"),
            document.get("section"),
        )
        if all(isinstance(part, str) and part.strip() for part in provision_key):
            if provision_key in seen_provisions:
                errors.append(f"{label}: duplicate jurisdiction/title/section record")
            else:
                seen_provisions.add(provision_key)

        for field in REQUIRED_CORPUS_FIELDS:
            value = document.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{label}: missing non-empty {field}")
        if document.get("jurisdiction") not in VALID_JURISDICTIONS:
            errors.append(f"{label}: jurisdiction must be India or International")
        source_url = document.get("source_url")
        if isinstance(source_url, str) and source_url.strip() and not source_url.startswith(("https://", "http://")):
            errors.append(f"{label}: source_url must use http or https")

    if errors:
        raise ValueError("Invalid curated corpus:\n- " + "\n- ".join(errors))
    return records
