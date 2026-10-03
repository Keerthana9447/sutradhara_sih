"""Owner-scoped, persistent formulation dossier lifecycle."""

import datetime
import json
import secrets
from typing import Any, Dict, Optional

from . import classifier, db, jurisdiction, retrieval


def _record_event(conn, dossier_id: str, event_type: str, payload: Dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO dossier_history (dossier_id, event_type, payload_json, created_at) "
        "VALUES (?, ?, ?, ?)",
        (dossier_id, event_type, json.dumps(payload), datetime.datetime.utcnow().isoformat()),
    )


def _serialize(row, conn) -> Dict[str, Any]:
    item = dict(row)
    item["ingredients"] = json.loads(item.pop("ingredients_json"))
    classification_json = item.pop("classification_json")
    mapping_json = item.pop("mapping_json")
    item["classification"] = json.loads(classification_json) if classification_json else None
    item["mapping"] = json.loads(mapping_json) if mapping_json else None
    item["history"] = [
        {
            "event_type": event["event_type"],
            "payload": json.loads(event["payload_json"]),
            "created_at": event["created_at"],
        }
        for event in conn.execute(
            "SELECT event_type, payload_json, created_at FROM dossier_history "
            "WHERE dossier_id = ? ORDER BY id",
            (item["dossier_id"],),
        ).fetchall()
    ]
    return item


def create(user_id: int, name: str, ingredients: list[str], sourcing_type: str,
           indication: str, target_market: str) -> Dict[str, Any]:
    now = datetime.datetime.utcnow().isoformat()
    dossier_id = "DOS-" + secrets.token_urlsafe(12)
    conn = db.get_conn()
    try:
        conn.execute(
            "INSERT INTO formulation_dossiers "
            "(dossier_id, user_id, name, ingredients_json, sourcing_type, indication, "
            "target_market, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?)",
            (dossier_id, user_id, name.strip(), json.dumps([i.strip() for i in ingredients]),
             sourcing_type.strip(), indication.strip(), target_market, now, now),
        )
        _record_event(conn, dossier_id, "created", {"status": "draft"})
        conn.commit()
        row = conn.execute(
            "SELECT * FROM formulation_dossiers WHERE dossier_id = ?", (dossier_id,)
        ).fetchone()
        return _serialize(row, conn)
    finally:
        conn.close()


def list_for_user(user_id: int) -> list[Dict[str, Any]]:
    conn = db.get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM formulation_dossiers WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
        return [_serialize(row, conn) for row in rows]
    finally:
        conn.close()


def get_for_user(dossier_id: str, user_id: int) -> Optional[Dict[str, Any]]:
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM formulation_dossiers WHERE dossier_id = ? AND user_id = ?",
            (dossier_id, user_id),
        ).fetchone()
        return _serialize(row, conn) if row else None
    finally:
        conn.close()


def update_for_user(dossier_id: str, user_id: int, changes: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    fields = {
        "name": "name",
        "ingredients": "ingredients_json",
        "sourcing_type": "sourcing_type",
        "indication": "indication",
        "target_market": "target_market",
    }
    values = {
        fields[key]: json.dumps([i.strip() for i in value]) if key == "ingredients"
        else value.strip() if isinstance(value, str) else value
        for key, value in changes.items() if value is not None
    }
    if not values:
        return get_for_user(dossier_id, user_id)

    now = datetime.datetime.utcnow().isoformat()
    assignments = ", ".join(f"{column} = ?" for column in values)
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT dossier_id FROM formulation_dossiers WHERE dossier_id = ? AND user_id = ?",
            (dossier_id, user_id),
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            f"UPDATE formulation_dossiers SET {assignments}, updated_at = ? "
            "WHERE dossier_id = ? AND user_id = ?",
            (*values.values(), now, dossier_id, user_id),
        )
        updated_fields = sorted(key for key, value in changes.items() if value is not None)
        _record_event(conn, dossier_id, "updated", {"fields": updated_fields})
        conn.commit()
        row = conn.execute(
            "SELECT * FROM formulation_dossiers WHERE dossier_id = ?", (dossier_id,)
        ).fetchone()
        return _serialize(row, conn)
    finally:
        conn.close()


def classify_for_user(dossier_id: str, user_id: int,
                      confirmed_category: Optional[str] = None) -> Optional[Dict[str, Any]]:
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM formulation_dossiers WHERE dossier_id = ? AND user_id = ?",
            (dossier_id, user_id),
        ).fetchone()
        if row is None:
            return None
        dossier = dict(row)
        ingredients = json.loads(dossier["ingredients_json"])
        query = (
            f"{dossier['name']}. Ingredients: {', '.join(ingredients)}. "
            f"Sourcing: {dossier['sourcing_type']}. Indication: {dossier['indication']}."
        )
        result = classifier.classify(query, confirmed_category).model_dump()
        now = datetime.datetime.utcnow().isoformat()
        next_status = "classified" if not result["needs_clarification"] else "draft"
        conn.execute(
            "UPDATE formulation_dossiers SET classification_json = ?, status = ?, updated_at = ? "
            "WHERE dossier_id = ? AND user_id = ?",
            (json.dumps(result), next_status, now, dossier_id, user_id),
        )
        _record_event(conn, dossier_id, "classified", result)
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM formulation_dossiers WHERE dossier_id = ?", (dossier_id,)
        ).fetchone()
        return _serialize(updated, conn)
    finally:
        conn.close()


def map_for_user(dossier_id: str, user_id: int) -> Optional[Dict[str, Any]]:
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM formulation_dossiers WHERE dossier_id = ? AND user_id = ?",
            (dossier_id, user_id),
        ).fetchone()
        if row is None:
            return None
        dossier = dict(row)
        if dossier["status"] not in ("classified", "mapped", "under_review"):
            raise ValueError("Classify this dossier before mapping its evidence.")
        classification = json.loads(dossier["classification_json"] or "{}")
        if classification.get("needs_clarification"):
            raise ValueError("Confirm a product category before mapping this dossier.")
        ingredients = json.loads(dossier["ingredients_json"])
        query = (
            f"{dossier['name']}. Ingredients: {', '.join(ingredients)}. "
            f"Sourcing: {dossier['sourcing_type']}. Indication: {dossier['indication']}."
        )
        areas = jurisdiction.route_areas(query, classification["category"])
        markets = ("India", "International") if dossier["target_market"] == "Both" else (dossier["target_market"],)
        mappings = {}
        for market in markets:
            sources = retrieval.retrieve([query], market, areas, top_k=5)
            mappings[market] = {"applicable_areas": areas, "sources": sources}
        mapping = {
            "jurisdictions": mappings,
            "note": "Evidence is stored by jurisdiction; sources from different jurisdictions are not combined.",
        }
        now = datetime.datetime.utcnow().isoformat()
        conn.execute(
            "UPDATE formulation_dossiers SET mapping_json = ?, status = 'mapped', updated_at = ? "
            "WHERE dossier_id = ? AND user_id = ?",
            (json.dumps(mapping), now, dossier_id, user_id),
        )
        _record_event(conn, dossier_id, "mapped", {"jurisdictions": list(markets), "source_count": sum(len(m["sources"]) for m in mappings.values())})
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM formulation_dossiers WHERE dossier_id = ?", (dossier_id,)
        ).fetchone()
        return _serialize(updated, conn)
    finally:
        conn.close()


def review_for_user(dossier_id: str, user_id: int, note: Optional[str] = None) -> Optional[Dict[str, Any]]:
    now = datetime.datetime.utcnow().isoformat()
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT status FROM formulation_dossiers WHERE dossier_id = ? AND user_id = ?",
            (dossier_id, user_id),
        ).fetchone()
        if row is None:
            return None
        if row["status"] not in ("mapped", "under_review"):
            raise ValueError("Map evidence for this dossier before starting a review.")
        conn.execute(
            "UPDATE formulation_dossiers SET status = 'under_review', updated_at = ? "
            "WHERE dossier_id = ? AND user_id = ?",
            (now, dossier_id, user_id),
        )
        _record_event(conn, dossier_id, "review_started", {"note": (note or "").strip()})
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM formulation_dossiers WHERE dossier_id = ?", (dossier_id,)
        ).fetchone()
        return _serialize(updated, conn)
    finally:
        conn.close()


def delete_for_user(dossier_id: str, user_id: int) -> bool:
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT dossier_id FROM formulation_dossiers WHERE dossier_id = ? AND user_id = ?",
            (dossier_id, user_id),
        ).fetchone()
        if row is None:
            return False
        conn.execute("DELETE FROM dossier_history WHERE dossier_id = ?", (dossier_id,))
        conn.execute(
            "DELETE FROM formulation_dossiers WHERE dossier_id = ? AND user_id = ?",
            (dossier_id, user_id),
        )
        conn.commit()
        return True
    finally:
        conn.close()
