"""Export-market herbal regimes (EU, UK, Canada, and US) and EU Nagoya compliance:
the problem statement names these explicitly, so
they must exist as International-jurisdiction documents, be reachable by
routing, and never leak into an India answer."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import jurisdiction, retrieval  # noqa: E402

EXPORT_IDS = {
    "INTL-EU-THMPD-2004",
    "INTL-EU-EMA-HMPC-HERBAL",
    "INTL-US-DSHEA-1994",
    "INTL-US-FDA-NDI-NOTIFICATION",
    "INTL-EU-NAGOYA-REG-511-2014",
    "INTL-UK-THR-2012",
    "INTL-CA-NHP-2003",
}
REQUIRED = {"id", "title", "jurisdiction", "domain", "source_type", "section", "summary",
            "version_date", "retrieved_date", "source_url", "authority", "precision"}


def test_export_documents_present_with_full_schema_and_international_jurisdiction():
    docs = {d["id"]: d for d in retrieval._CORPUS}
    assert EXPORT_IDS <= set(docs)
    for i in EXPORT_IDS:
        assert REQUIRED <= set(docs[i]), i
        assert docs[i]["jurisdiction"] == "International"
        assert docs[i]["source_url"].startswith("https://")
        assert docs[i]["precision"]  # each states its own confidence


def test_corpus_ids_are_unique():
    ids = [d["id"] for d in retrieval._CORPUS]
    assert len(ids) == len(set(ids))


def _top(query, category):
    areas = jurisdiction.route_areas(query, category)
    return [h["id"] for h in retrieval.retrieve([query], "International", areas, top_k=5)]


def test_eu_traditional_herbal_query_retrieves_thmpd_first():
    q = "Which EU traditional herbal medicinal product registration requirements apply to my herbal medicine?"
    assert _top(q, "Classical / Generic Medicine")[0] == "INTL-EU-THMPD-2004"


def test_us_dietary_supplement_query_retrieves_dshea_first():
    q = "Can I sell my herbal capsules in the United States as a dietary supplement under DSHEA?"
    assert _top(q, "Ayurveda-Aahar / Nutraceutical")[0] == "INTL-US-DSHEA-1994"


def test_us_new_dietary_ingredient_query_retrieves_fda_guidance_first():
    q = "How do I notify FDA about a new dietary ingredient before marketing a herbal supplement?"
    assert _top(q, "Ayurveda-Aahar / Nutraceutical")[0] == "INTL-US-FDA-NDI-NOTIFICATION"


def test_eu_hmpc_monograph_query_retrieves_ema_overview_first():
    q = "Can HMPC EU herbal monographs support a traditional use registration and quality review?"
    assert _top(q, "Classical / Generic Medicine")[0] == "INTL-EU-EMA-HMPC-HERBAL"


def test_uk_traditional_herbal_query_retrieves_mhra_route_first():
    q = "How do I register a classical Ayurvedic herbal medicine for the UK under the MHRA THR route?"
    assert _top(q, "Classical / Generic Medicine")[0] == "INTL-UK-THR-2012"


def test_canada_nhp_query_retrieves_health_canada_licensing_first():
    q = "How can I verify whether my Ayurvedic medicine has a Canadian natural health product licence and NPN?"
    assert _top(q, "Classical / Generic Medicine")[0] == "INTL-CA-NHP-2003"


def test_nagoya_due_diligence_query_retrieves_eu_regulation_first():
    q = "What Nagoya due diligence duties apply when an EU company uses Indian medicinal plants?"
    assert _top(q, "Classical / Generic Medicine")[0] == "INTL-EU-NAGOYA-REG-511-2014"


def test_routing_keywords_reach_the_new_domains():
    assert "Drug regulation" in jurisdiction.route_areas("traditional herbal medicinal product registration", "Classical / Generic Medicine")
    assert "Food / nutraceutical regulation" in jurisdiction.route_areas("dietary supplement rules", "Classical / Generic Medicine")
    assert "Access-and-Benefit-Sharing" in jurisdiction.route_areas("nagoya due diligence", "Cosmetic")


def test_export_documents_never_appear_in_an_india_answer():
    for q in ("traditional herbal medicinal product registration", "dietary supplement DSHEA", "Nagoya due diligence", "Canadian natural health product NPN"):
        areas = jurisdiction.route_areas(q, "Classical / Generic Medicine")
        got = {h["id"] for h in retrieval.retrieve([q], "India", areas, top_k=10)}
        assert not (got & EXPORT_IDS), (q, got & EXPORT_IDS)
