"""Trade secrets previously had zero corpus documents despite being a live
routing area (jurisdiction.py's 'Trade Secrets' keywords) — any such query
would silently retrieve nothing and abstain. This closes that gap with a
real India common-law/contract entry and the TRIPS Art 39 international
counterpart, and checks both are actually reachable, not just present."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import jurisdiction, retrieval  # noqa: E402

TRADE_SECRET_IDS = {"IN-TRADESECRET-COMMONLAW", "INTL-TRIPS-39"}
REQUIRED = {"id", "title", "jurisdiction", "domain", "source_type", "section", "summary",
            "version_date", "retrieved_date", "source_url", "authority", "precision"}


def test_trade_secret_documents_present_with_full_schema():
    docs = {d["id"]: d for d in retrieval._CORPUS}
    assert TRADE_SECRET_IDS <= set(docs)
    for i in TRADE_SECRET_IDS:
        assert REQUIRED <= set(docs[i]), i
        assert docs[i]["domain"] == "Trade Secrets"
    assert docs["IN-TRADESECRET-COMMONLAW"]["jurisdiction"] == "India"
    assert docs["INTL-TRIPS-39"]["jurisdiction"] == "International"


def _top(query, category, jur):
    areas = jurisdiction.route_areas(query, category)
    return areas, [h["id"] for h in retrieval.retrieve([query], jur, areas, top_k=5)]


def test_india_trade_secret_query_routes_and_retrieves_the_commonlaw_entry():
    q = "Can I protect my proprietary Ayurvedic extraction process as a trade secret instead of patenting it?"
    areas, hits = _top(q, "Patent / Proprietary Medicine", "India")
    assert "Trade Secrets" in areas
    assert hits[0] == "IN-TRADESECRET-COMMONLAW"


def test_confidentiality_phrasing_without_the_words_trade_secret_still_routes():
    # Routing keywords were widened (confidentiality/NDA/breach of confidence)
    # so a natural-language question doesn't have to say "trade secret" verbatim.
    q = "What are my confidentiality options if I don't want to disclose my formulation in a patent application?"
    areas, hits = _top(q, "Classical / Generic Medicine", "India")
    assert "Trade Secrets" in areas
    assert "IN-TRADESECRET-COMMONLAW" in hits


def test_international_trade_secret_query_retrieves_trips_article_39():
    q = "What is the international standard for protecting undisclosed information or trade secrets under TRIPS?"
    areas, hits = _top(q, "Classical / Generic Medicine", "International")
    assert hits[0] == "INTL-TRIPS-39"


def test_trade_secret_documents_never_leak_across_jurisdiction():
    q = "trade secret confidentiality undisclosed information"
    for jur, other_id in (("India", "INTL-TRIPS-39"), ("International", "IN-TRADESECRET-COMMONLAW")):
        areas, hits = _top(q, "Classical / Generic Medicine", jur)
        assert other_id not in hits
