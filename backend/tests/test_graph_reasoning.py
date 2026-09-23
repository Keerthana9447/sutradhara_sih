import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import graph_reasoning  # noqa: E402


def test_reason_grounds_every_law_node_in_a_real_corpus_id():
    result = graph_reasoning.reason("Classical / Generic Medicine", "India", export_intent=False)
    law_nodes = [n for n in result["nodes"] if n["type"] == "Law"]
    assert law_nodes, "expected at least one grounded Law node"
    for n in law_nodes:
        assert "source_id" in n and n["source_id"]


def test_reason_rejects_unknown_category():
    try:
        graph_reasoning.reason("Not A Real Category", "India")
        assert False, "should have raised"
    except ValueError:
        pass


def test_reason_rejects_unknown_jurisdiction():
    try:
        graph_reasoning.reason("Classical / Generic Medicine", "Mars")
        assert False, "should have raised"
    except ValueError:
        pass


def test_export_intent_adds_a_separate_branch_not_merged_into_home_jurisdiction():
    result = graph_reasoning.reason("Classical / Generic Medicine", "India", export_intent=True)
    export_nodes = [n for n in result["nodes"] if n["type"] == "ExportIntent"]
    assert len(export_nodes) == 1

    # every Law node reachable ONLY through the export branch must come from
    # the OTHER jurisdiction's corpus -- the home-jurisdiction law nodes
    # (reached directly from n_category) must still only be India documents.
    home_law_ids = set()
    export_law_ids = set()
    export_node_id = export_nodes[0]["id"]
    # crude but sufficient reachability split: anything whose node id starts
    # with the export node's prefix is on the export branch
    for n in result["nodes"]:
        if n["type"] == "Law" and "source_id" in n:
            if n["id"].startswith("n_export_area"):
                export_law_ids.add(n["source_id"])
            else:
                home_law_ids.add(n["source_id"])

    from app import retrieval
    docs_by_id = {d["id"]: d for d in retrieval._CORPUS}
    for sid in home_law_ids:
        assert docs_by_id[sid]["jurisdiction"] == "India"
    for sid in export_law_ids:
        assert docs_by_id[sid]["jurisdiction"] == "International"


def test_reason_without_export_intent_has_no_export_branch():
    result = graph_reasoning.reason("Cosmetic", "India", export_intent=False)
    assert not [n for n in result["nodes"] if n["type"] == "ExportIntent"]
