"""Owner-scoped patent watchlist with a transparent monitoring target."""

import calendar
import datetime
import json
import secrets
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from . import db, tkdl_similarity

RULE_55_SOURCE = "https://ipindia.gov.in/writereaddata/Portal/IPOAct/1_113_1_patent-rules-2003.pdf"
MONITORING_TARGET_NOTE = (
    "The six-month date is an internal monitoring target, not a statutory deadline. "
    "Indian Patent Rules, Rule 55(1A), concerns representations after publication "
    "and before grant; verify the current legal position and grant status."
)


def _add_calendar_months(value: datetime.date, months: int) -> datetime.date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


def _urgency(target_date: datetime.date, today: datetime.date) -> tuple[str, int]:
    days_remaining = (target_date - today).days
    if days_remaining < 0:
        return "grey", days_remaining
    if days_remaining <= 30:
        return "red", days_remaining
    if days_remaining <= 90:
        return "amber", days_remaining
    return "green", days_remaining


def _serialize(row, today: Optional[datetime.date] = None) -> Dict[str, Any]:
    item = dict(row)
    publication_date = datetime.date.fromisoformat(item["publication_date"])
    target_date = _add_calendar_months(publication_date, 6)
    band, remaining = _urgency(target_date, today or datetime.date.today())
    item["risk_matches"] = json.loads(item.pop("risk_matches_json"))
    item["monitoring_target_date"] = target_date.isoformat()
    item["days_remaining"] = remaining
    item["urgency_band"] = band
    item["deadline_note"] = MONITORING_TARGET_NOTE
    item["deadline_source_url"] = RULE_55_SOURCE
    item["risk_note"] = (
        "A heuristic 0–100 text-resemblance score against a small public illustrative "
        "reference set; not an official TKDL search, infringement assessment, or legal conclusion."
    )
    return item


def create(user_id: int, filing_number: str, title: str, abstract: str,
           publication_date: str, stream: str, source_url: Optional[str]) -> Dict[str, Any]:
    try:
        published = datetime.date.fromisoformat(publication_date)
    except ValueError as error:
        raise ValueError("publication_date must be a valid YYYY-MM-DD date.") from error
    if published > datetime.date.today():
        raise ValueError("publication_date cannot be in the future.")
    if source_url:
        parsed_url = urlparse(source_url)
        if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
            raise ValueError("source_url must be an HTTP or HTTPS URL.")

    matches = tkdl_similarity.score_resemblance(
        f"{title}\n{abstract}", top_k=5, min_score=0.01
    )
    matches = [match for match in matches if match["similarity"] > 0]
    risk_score = min(100, round(max((m["similarity"] for m in matches), default=0) * 100))
    alert_id = "PRH-" + secrets.token_urlsafe(12)
    now = datetime.datetime.utcnow().isoformat()
    conn = db.get_conn()
    try:
        conn.execute(
            "INSERT INTO prahari_alerts "
            "(alert_id, user_id, filing_number, title, abstract, publication_date, "
            "stream, source_url, risk_score, risk_matches_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (alert_id, user_id, filing_number.strip(), title.strip(), abstract.strip(),
             published.isoformat(), stream, source_url, risk_score, json.dumps(matches), now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM prahari_alerts WHERE alert_id = ?", (alert_id,)
        ).fetchone()
        return _serialize(row)
    finally:
        conn.close()


def list_for_user(user_id: int, today: Optional[datetime.date] = None) -> list[Dict[str, Any]]:
    conn = db.get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM prahari_alerts WHERE user_id = ? ORDER BY publication_date DESC, created_at DESC",
            (user_id,),
        ).fetchall()
        return [_serialize(row, today) for row in rows]
    finally:
        conn.close()


def get_for_user(alert_id: str, user_id: int,
                 today: Optional[datetime.date] = None) -> Optional[Dict[str, Any]]:
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM prahari_alerts WHERE alert_id = ? AND user_id = ?",
            (alert_id, user_id),
        ).fetchone()
        return _serialize(row, today) if row else None
    finally:
        conn.close()


def delete_for_user(alert_id: str, user_id: int) -> bool:
    conn = db.get_conn()
    try:
        conn.execute("DELETE FROM form7a_drafts WHERE alert_id = ? AND user_id = ?", (alert_id, user_id))
        cursor = conn.execute(
            "DELETE FROM prahari_alerts WHERE alert_id = ? AND user_id = ?",
            (alert_id, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
