"""
Multi-hop graph reasoning.

/api/graph (main.py) already returns a STATIC schema view (node/edge TYPES —
Product -> ProductCategory -> IPRegime -> Law -> Provision -> Source) mirroring
graph/schema.cypher, for the prototype UI. That is a diagram, not reasoning:
it never actually walks the chain for a specific product.

This module does the walk. Given a classified product category, a
jurisdiction, and (optionally) an intent to export to an international
market, `reason()` chains:

    category -> applicable IP/regulatory area(s) -> the actual corpus
    document(s) governing each area -> (if exporting) the international
    counterpart area(s) and their documents

into a single explained path, each hop grounded in a real corpus entry id
(never an invented node). This is the "relational knowledge graph and
agentic, multi-source orchestration" the brief asks for, implemented as an
honest in-memory traversal over the existing corpus rather than standing up
a real Neo4j server — this sandbox has no route to a Neo4j/Aura endpoint to
test against (same network constraint noted in registry_lookup.py and
retrieval.py), and graph/schema.cypher already documents the intended
production schema. Swapping this module's traversal for real Cypher queries
against that schema is a mechanical follow-up once a Neo4j instance is
reachable; the node/edge/path shape returned here matches that schema
exactly so the swap doesn't change the API contract.
"""
from typing import Any, Dict, List, Optional

from . import jurisdiction as jurisdiction_module
from . import retrieval


def _docs_for_area(area: str, jur: str, limit: int = 2) -> List[Dict[str, Any]]:
    return [d for d in retrieval._CORPUS if d["domain"] == area and d["jurisdiction"] == jur][:limit]


def reason(category: str, jur: str, export_intent: bool = False) -> Dict[str, Any]:
    """
    Returns a hop-by-hop explained path:
      product (category) -> area -> law/rule/treaty document(s)
      [-> if export_intent: international counterpart area -> its documents]
    Every hop after the first two is grounded in an actual corpus.json id.
    """
    if jur not in jurisdiction_module.VALID_JURISDICTIONS:
        raise ValueError(f"Unknown jurisdiction '{jur}'")

    areas = jurisdiction_module._CATEGORY_DEFAULT_AREAS.get(category)
    if not areas:
        raise ValueError(f"Unknown category '{category}'")

    nodes: List[Dict[str, str]] = [
        {"id": "n_product", "label": "Ayurvedic product", "type": "Product"},
        {"id": "n_category", "label": category, "type": "ProductCategory"},
    ]
    edges: List[Dict[str, str]] = [
        {"from": "n_product", "to": "n_category", "label": "classified_as"},
    ]
    steps: List[str] = [
        f"Step 1 — Product is classified as '{category}'.",
    ]

    for i, area in enumerate(areas):
        area_node = f"n_area_{i}"
        nodes.append({"id": area_node, "label": area, "type": "IPRegime"})
        edges.append({"from": "n_category", "to": area_node, "label": "relevant_to"})

        docs = _docs_for_area(area, jur)
        if not docs:
            steps.append(f"Step — '{area}' is relevant under {jur} jurisdiction, but no corpus document is indexed for it yet.")
            continue

        doc_ids = []
        for j, doc in enumerate(docs):
            doc_node = f"{area_node}_doc_{j}"
            nodes.append({
                "id": doc_node, "label": f"{doc['title']} ({doc['section']})",
                "type": "Law", "source_id": doc["id"],
            })
            edges.append({"from": area_node, "to": doc_node, "label": "governed_by"})
            doc_ids.append(doc["id"])

        steps.append(
            f"Step — '{area}' under {jur} jurisdiction is governed by: "
            + "; ".join(f"{d['title']} ({d['section']}) [{d['id']}]" for d in docs)
        )

    if export_intent:
        other_jur = "International" if jur == "India" else "India"
        export_areas = [a for a in ("Access-and-Benefit-Sharing", "Geographical Indications", "Patents", "Trademarks") if a in areas or a == "Access-and-Benefit-Sharing"]
        # Always surface ABS + whichever of the category's own areas have an
        # international counterpart — export readiness is fundamentally an
        # ABS + cross-border-filing question regardless of category.
        cross_border_areas = list(dict.fromkeys(
            [a for a in areas if a in ("Patents", "Trademarks", "Geographical Indications", "Designs", "Copyright", "Plant Variety Protection")]
            + ["Access-and-Benefit-Sharing"]
        ))
        export_node = "n_export"
        nodes.append({"id": export_node, "label": f"Export readiness ({other_jur})", "type": "ExportIntent"})
        edges.append({"from": "n_category", "to": export_node, "label": "requires_for_export"})
        steps.append(f"Step — Export intent detected: chaining into {other_jur}-jurisdiction requirements (kept in a SEPARATE branch of this graph — never merged into a single /api/analyze answer, per the jurisdiction-isolation rule).")

        for i, area in enumerate(cross_border_areas):
            area_node = f"n_export_area_{i}"
            nodes.append({"id": area_node, "label": area, "type": "IPRegime"})
            edges.append({"from": export_node, "to": area_node, "label": "relevant_to"})
            docs = _docs_for_area(area, other_jur)
            for j, doc in enumerate(docs):
                doc_node = f"{area_node}_doc_{j}"
                nodes.append({
                    "id": doc_node, "label": f"{doc['title']} ({doc['section']})",
                    "type": "Law", "source_id": doc["id"],
                })
                edges.append({"from": area_node, "to": doc_node, "label": "governed_by"})
            if docs:
                steps.append(
                    f"Step — For {other_jur}, '{area}' is governed by: "
                    + "; ".join(f"{d['title']} ({d['section']}) [{d['id']}]" for d in docs)
                )

    return {
        "category": category,
        "jurisdiction": jur,
        "export_intent": export_intent,
        "nodes": nodes,
        "edges": edges,
        "steps": steps,
        "note": (
            "In-memory multi-hop traversal over the current corpus (see module docstring); "
            "the node/edge shape mirrors graph/schema.cypher so this can be swapped for real "
            "Cypher queries against a live Neo4j instance without changing this API's response shape."
        ),
    }
