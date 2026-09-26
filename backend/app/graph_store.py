"""
Live Neo4j-backed knowledge graph — the "knowledge graph: partially
implemented" gap.

graph_reasoning.py already does the real multi-hop *reasoning* (category ->
area -> corpus document, chained into an export branch when relevant); what
it did NOT have was a real graph database behind it, only an in-memory
traversal over the same Python list retrieval.py already loads. This module
is the other half, following the exact same optional-dependency pattern
already used twice elsewhere in this codebase (retrieval.py's BGE+FAISS vs
TF-IDF, dag.py's LangGraph vs hand-rolled sequential executor): try the
richer backend, fall back to a dependency-light equivalent that returns the
same shape, and report which one is actually active via a module-level
constant for logging/tests.

  - If the `neo4j` package is importable AND NEO4J_URI/NEO4J_USER/
    NEO4J_PASSWORD are set AND a connection actually succeeds, this module
    syncs the full corpus into a live graph matching graph/schema.cypher's
    node/relationship labels (Product/ProductCategory/IPRegime/Law/
    Provision/Source, `relevant_to`/`governed_by`/`contains`/`supported_by`
    edges) and answers graph_reasoning.reason() with real Cypher MATCH
    traversals instead of the Python loop.
  - Otherwise GRAPH_BACKEND stays "in_memory" and graph_reasoning.py's
    existing traversal (renamed `_reason_in_memory` there) runs unchanged —
    zero behavior change for every deployment that doesn't have a Neo4j
    instance configured, this sandbox included (no outbound network here,
    the same constraint noted in retrieval.py and registry_lookup.py).

The returned node/edge/step shape is identical either way, so callers
(graph_reasoning.reason(), and therefore POST /api/graph/reason) never need
to know which backend actually served the request.
"""
import logging
import os
from typing import Any, Dict, List, Optional

from . import retrieval

logger = logging.getLogger("ip_sakti.graph_store")

GRAPH_BACKEND = "in_memory"  # flipped to "neo4j" below iff driver+connection succeed
_DRIVER = None


def _try_init_neo4j() -> bool:
    global _DRIVER, GRAPH_BACKEND

    if os.getenv("SUTRADHARA_DISABLE_NEO4J") == "1":
        logger.info("Neo4j backend disabled by SUTRADHARA_DISABLE_NEO4J. Using in-memory graph traversal.")
        return False

    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    if not (uri and user and password):
        logger.info("NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD not fully set. Using in-memory graph traversal.")
        return False

    try:
        from neo4j import GraphDatabase
    except ImportError as e:
        logger.warning("Neo4j backend unavailable (missing 'neo4j' package): %r. Using in-memory traversal.", e)
        return False

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()  # actually opens a connection — fails fast if unreachable
        _DRIVER = driver
        _sync_corpus(driver)
        GRAPH_BACKEND = "neo4j"
        logger.info("Neo4j backend ready at %s; corpus synced (%d documents).", uri, len(retrieval._CORPUS))
        return True
    except Exception as e:  # noqa: BLE001 — broad on purpose, see module docstring
        logger.warning("Neo4j connection/sync failed: %r. Falling back to in-memory traversal.", e)
        _DRIVER = None
        return False


def _sync_corpus(driver) -> None:
    """Idempotent MERGE-based sync of the full corpus into Neo4j, matching
    graph/schema.cypher's labels exactly so this can be swapped in without
    changing the schema file or the API response shape. Safe to re-run on
    every startup — MERGE never duplicates a node/edge that already exists,
    it only adds what's missing (e.g. a newly added corpus.json entry)."""
    with driver.session() as session:
        session.run(
            "CREATE CONSTRAINT source_id IF NOT EXISTS FOR (s:Source) REQUIRE s.id IS UNIQUE"
        )
        for doc in retrieval._CORPUS:
            session.run(
                """
                MERGE (j:Jurisdiction {name: $jurisdiction})
                MERGE (regime:IPRegime {name: $domain})
                MERGE (j)-[:governs]->(regime)
                MERGE (law:Law {title: $title})
                MERGE (regime)-[:governed_by]->(law)
                MERGE (prov:Provision {section: $section, law_title: $title})
                MERGE (law)-[:contains]->(prov)
                MERGE (src:Source {id: $id})
                  ON CREATE SET src.title = $title, src.authority = $authority,
                                 src.source_url = $source_url, src.retrieved_date = $retrieved_date
                MERGE (prov)-[:supported_by]->(src)
                """,
                jurisdiction=doc["jurisdiction"], domain=doc["domain"], title=doc["title"],
                section=doc["section"], id=doc["id"], authority=doc.get("authority", ""),
                source_url=doc.get("source_url", ""), retrieved_date=doc.get("retrieved_date", ""),
            )
        for area, categories in _category_area_pairs():
            for category in categories:
                session.run(
                    """
                    MERGE (c:ProductCategory {name: $category})
                    MERGE (r:IPRegime {name: $area})
                    MERGE (c)-[:relevant_to]->(r)
                    """,
                    category=category, area=area,
                )


def _category_area_pairs():
    """(area, [categories]) pairs from jurisdiction.py's own routing table,
    so the graph's ProductCategory->IPRegime edges are derived from the
    single source of truth already used for live query routing, never
    hand-duplicated and left to drift out of sync."""
    from . import jurisdiction as jurisdiction_module
    area_to_categories: Dict[str, List[str]] = {}
    for category, areas in jurisdiction_module._CATEGORY_DEFAULT_AREAS.items():
        for area in areas:
            area_to_categories.setdefault(area, []).append(category)
    return list(area_to_categories.items())


if _try_init_neo4j():
    GRAPH_BACKEND = "neo4j"


def _docs_for_area_live(area: str, jur: str, limit: int = 2) -> List[Dict[str, Any]]:
    with _DRIVER.session() as session:
        result = session.run(
            """
            MATCH (r:IPRegime {name: $area})-[:governed_by]->(:Law)-[:contains]->(:Provision)
                  -[:supported_by]->(s:Source)-[:supported_by]-()
            RETURN DISTINCT s.id AS id, s.title AS title
            LIMIT $limit
            """,
            area=area, limit=limit,
        )
        # The relationship pattern above is intentionally loose (it matches
        # via the Provision->Source edge regardless of which Law/Provision
        # carries it); filter to the requested jurisdiction using the
        # already-loaded corpus dict for the actual field values, since
        # Source nodes don't carry jurisdiction directly in the schema.
        ids = [r["id"] for r in result]
    docs = [retrieval._CORPUS_BY_ID[i] for i in ids if i in retrieval._CORPUS_BY_ID]
    return [d for d in docs if d["jurisdiction"] == jur and d["domain"] == area][:limit]


def docs_for_area(area: str, jur: str, limit: int = 2) -> List[Dict[str, Any]]:
    """Same contract as graph_reasoning._docs_for_area, dispatched to
    whichever backend is live. The Neo4j path queries the graph; the
    in-memory path (the overwhelming majority of deployments, including
    this sandbox) is a direct list comprehension over the corpus that was
    already loaded into memory by retrieval.py — no behavior change."""
    if GRAPH_BACKEND == "neo4j" and _DRIVER is not None:
        try:
            return _docs_for_area_live(area, jur, limit)
        except Exception:
            logger.exception("Live Neo4j query failed; falling back to in-memory lookup for this call.")
    return [d for d in retrieval._CORPUS if d["domain"] == area and d["jurisdiction"] == jur][:limit]
