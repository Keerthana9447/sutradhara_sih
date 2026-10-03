"""
Dynamic Knowledge Graph Builder.

Constructs query-dependent knowledge graph representations (nodes & edges)
from user queries, product categories, jurisdictions, governing laws, legal provisions,
and RAG retrieved sources.

Supports live Neo4j Cypher querying if configured (via NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD),
and automatically falls back to RAG corpus dynamic graph construction if Neo4j is offline or unavailable.
"""
import os
import logging
import math
from typing import List, Dict, Any, Optional

logger = logging.getLogger("ip_sakti.graph")


def _edge(
    source: str,
    target: str,
    label: str,
    confidence: float,
    provenance: Dict[str, Any],
) -> Dict[str, Any]:
    """Create an edge with an explicit confidence and auditable provenance."""
    return {
        "from": source,
        "to": target,
        "label": label,
        "confidence": confidence,
        "provenance": provenance,
    }


def _source_confidence(source: Dict[str, Any]) -> float:
    """Use retrieval's measured score, or certainty of an exact source record."""
    score = source.get("relevance_score")
    if isinstance(score, (int, float)) and not isinstance(score, bool) and math.isfinite(score) and 0 <= score <= 1:
        return float(score)
    return 1.0


# Optional Neo4j driver
try:
    from neo4j import GraphDatabase
    _NEO4J_AVAILABLE = True
except ImportError:
    GraphDatabase = None
    _NEO4J_AVAILABLE = False


def _query_neo4j_graph(query: str, category: str, jurisdiction_name: str) -> Optional[Dict[str, Any]]:
    """Try querying live Neo4j database if configured."""
    if os.getenv("SUTRADHARA_DISABLE_NEO4J") == "1":
        return None
    if not _NEO4J_AVAILABLE:
        return None
    uri = os.environ.get("NEO4J_URI")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")

    if not uri or not password:
        return None

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            cypher = """
            MATCH (c:ProductCategory {name: $category})-[:relevant_to]->(r:IPRegime)
                  -[:governed_by]->(l:Law)-[:contains]->(p:Provision)
                  -[:supported_by]->(s:Source {jurisdiction: $jurisdiction})
            RETURN c, r, l, p, s LIMIT 10
            """
            result = session.run(cypher, category=category, jurisdiction=jurisdiction_name)
            records = list(result)
            records = [
                rec for rec in records
                if isinstance(rec["s"].get("id"), str) and rec["s"].get("id").strip()
            ]
            if not records:
                driver.close()
                return None

            nodes = []
            edges = []
            seen_nodes = set()
            edge_map = {}

            def add_path_edge(source_id, target_id, label, source_ref):
                key = (source_id, target_id, label)
                if key not in edge_map:
                    edge_map[key] = _edge(
                        source_id, target_id, label, 1.0,
                        {"basis": "matched_graph_path", "source_ids": []},
                    )
                    edges.append(edge_map[key])
                source_ids = edge_map[key]["provenance"]["source_ids"]
                if source_ref not in source_ids:
                    source_ids.append(source_ref)

            for rec in records:
                c_node = rec["c"]
                r_node = rec["r"]
                l_node = rec["l"]
                p_node = rec["p"]
                s_node = rec["s"]

                if "cat" not in seen_nodes:
                    nodes.append({"id": "category", "label": c_node.get("name", category), "type": "ProductCategory"})
                    seen_nodes.add("cat")

                reg_id = f"regime_{r_node.get('name', 'regime')}"
                if reg_id not in seen_nodes:
                    nodes.append({"id": reg_id, "label": r_node.get("name", "IP Regime"), "type": "IPRegime"})
                    seen_nodes.add(reg_id)
                add_path_edge("category", reg_id, "relevant_to", s_node.get("id"))

                law_id = f"law_{l_node.get('title', 'law')}"
                if law_id not in seen_nodes:
                    nodes.append({"id": law_id, "label": l_node.get("title", "Law"), "type": "Law"})
                    seen_nodes.add(law_id)
                add_path_edge(reg_id, law_id, "governed_by", s_node.get("id"))

                prov_id = f"prov_{p_node.get('section', 'prov')}"
                if prov_id not in seen_nodes:
                    nodes.append({"id": prov_id, "label": p_node.get("section", "Provision"), "type": "Provision"})
                    seen_nodes.add(prov_id)
                add_path_edge(law_id, prov_id, "contains", s_node.get("id"))

                src_id = f"src_{s_node.get('id', 'src')}"
                if src_id not in seen_nodes:
                    nodes.append({"id": src_id, "label": s_node.get("id", "Source"), "type": "Source"})
                    seen_nodes.add(src_id)
                add_path_edge(prov_id, src_id, "supported_by", s_node.get("id"))

            driver.close()
            return {
                "nodes": nodes,
                "edges": edges,
                "note": f"Live Cypher graph retrieved from Neo4j for {category} in {jurisdiction_name}.",
                "source": "neo4j",
            }
    except Exception as e:
        logger.warning(f"Neo4j query failed: {e}. Falling back to dynamic RAG graph.")
        return None


def build_dynamic_graph(
    query: str,
    category: str,
    jurisdiction_name: str,
    retrieved_sources: List[Dict[str, Any]],
    applicable_areas: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Builds a query-dependent dynamic knowledge graph representation.

    Nodes represent:
    - Product / Query Topic
    - Product Category
    - Relevant IP Regimes
    - Governing Laws
    - Legal Provisions / Sections
    - Authoritative Sources

    Edges represent relationship types:
    - belongs_to, relevant_to, governed_by, contains, supported_by
    """
    # 1. Try Neo4j if configured
    neo4j_graph = _query_neo4j_graph(query, category, jurisdiction_name)
    if neo4j_graph:
        return neo4j_graph

    # 2. Dynamic RAG Graph Builder
    nodes = []
    edges = []

    # Node 1: Product / Query Context
    short_query = query.strip()
    if len(short_query) > 35:
        short_query = short_query[:32] + "..."

    product_node_id = "product"
    nodes.append({
        "id": product_node_id,
        "label": short_query or "Ayurvedic Query",
        "type": "Product",
        "category": "Query Context",
    })

    # Node 2: ProductCategory
    category_label = category if category and category != "n/a" else "General IP Query"
    cat_node_id = "category"
    nodes.append({
        "id": cat_node_id,
        "label": category_label,
        "type": "ProductCategory",
        "category": "Product Category",
    })

    edges.append(_edge(
        product_node_id, cat_node_id, "belongs_to", 1.0,
        {"basis": "request_input", "reference": "category", "value": category_label},
    ))

    # Node 3: IP Regimes
    regime_ids = []
    areas_to_use = list(applicable_areas) if applicable_areas else []

    valid_sources = [
        src for src in (retrieved_sources or [])
        if isinstance(src, dict) and isinstance(src.get("id"), str) and src["id"].strip()
    ]

    if valid_sources:
        for src in valid_sources:
            domain = src.get("domain")
            if domain and domain not in areas_to_use:
                areas_to_use.append(domain)

    if not areas_to_use:
        areas_to_use = ["Patents", "Traditional Knowledge"]

    for idx, area in enumerate(areas_to_use[:3]):
        reg_id = f"regime_{idx+1}"
        nodes.append({
            "id": reg_id,
            "label": area,
            "type": "IPRegime",
            "category": "IP Regime",
        })
        supporting_sources = [src for src in valid_sources if src.get("domain") == area]
        if supporting_sources:
            confidence = max(_source_confidence(src) for src in supporting_sources)
            provenance = {
                "basis": "retrieved_sources",
                "source_ids": [src["id"] for src in supporting_sources],
            }
        elif applicable_areas and area in applicable_areas:
            confidence = 1.0
            provenance = {"basis": "applicable_areas", "reference": area}
        else:
            confidence = 0.0
            provenance = {"basis": "no_supporting_source", "source_ids": []}
        edges.append(_edge(cat_node_id, reg_id, "relevant_to", confidence, provenance))
        regime_ids.append(reg_id)

    # Node 4: Laws, Provisions, and Sources from retrieved sources
    law_map = {}      # title -> node_id
    prov_map = {}     # section -> node_id
    source_map = {}   # src_id -> node_id

    if valid_sources:
        for idx, src in enumerate(valid_sources[:4]):
            law_title = src.get("title", "Governing Law")
            section = src.get("section", f"Section {idx+1}")
            src_id_val = src["id"]
            source_confidence = _source_confidence(src)
            source_provenance = {
                "basis": "retrieved_source",
                "source_ids": [src_id_val],
            }

            # Law node
            if law_title not in law_map:
                law_node_id = f"law_{len(law_map)+1}"
                law_map[law_title] = law_node_id
                nodes.append({
                    "id": law_node_id,
                    "label": law_title,
                    "type": "Law",
                    "category": "Governing Law",
                })
                target_regime = regime_ids[0] if regime_ids else cat_node_id
                edges.append(_edge(
                    target_regime, law_node_id, "governed_by", source_confidence,
                    source_provenance,
                ))
            else:
                law_node_id = law_map[law_title]

            # Provision node
            prov_key = f"{law_title}::{section}"
            if prov_key not in prov_map:
                prov_node_id = f"provision_{len(prov_map)+1}"
                prov_map[prov_key] = prov_node_id
                nodes.append({
                    "id": prov_node_id,
                    "label": section,
                    "type": "Provision",
                    "category": "Provision",
                })
                edges.append(_edge(
                    law_node_id, prov_node_id, "contains", source_confidence,
                    source_provenance,
                ))
            else:
                prov_node_id = prov_map[prov_key]

            # Source node
            if src_id_val not in source_map:
                src_node_id = f"source_{len(source_map)+1}"
                source_map[src_id_val] = src_node_id
                nodes.append({
                    "id": src_node_id,
                    "label": src_id_val,
                    "type": "Source",
                    "category": "Authoritative Source",
                })
                edges.append(_edge(
                    prov_node_id, src_node_id, "supported_by", source_confidence,
                    source_provenance,
                ))

    else:
        # No sources were actually retrieved for this query (e.g. the query
        # was abstained on, or matched nothing). Show that honestly rather
        # than fabricating a plausible-looking source that was NOT actually
        # retrieved for this specific query — a dynamic, per-query graph
        # exists specifically to reflect real retrieval, so faking a node
        # here would defeat its own purpose.
        empty_node_id = "no_evidence"
        nodes.append({
            "id": empty_node_id,
            "label": "No sources retrieved for this query",
            "type": "EmptyState",
            "category": "No Evidence",
        })
        target_regime = regime_ids[0] if regime_ids else cat_node_id
        edges.append(_edge(
            target_regime, empty_node_id, "no_evidence_found", 0.0,
            {"basis": "empty_retrieval", "reference": "retrieved_sources", "source_ids": []},
        ))

    note = f"Dynamic knowledge graph generated for '{short_query}' ({category_label}) in {jurisdiction_name} jurisdiction."

    return {
        "nodes": nodes,
        "edges": edges,
        "note": note,
        "jurisdiction": jurisdiction_name,
        "source": "dynamic_rag",
    }
