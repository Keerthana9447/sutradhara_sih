import datetime
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import db, dossiers, prahari  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", str(tmp_path / "citizen-features.db"))
    db.init_db()


@pytest.fixture
def users(fresh_db):
    first = db.create_user("dossier-owner@example.com", "Owner", "correct-horse")
    second = db.create_user("other-owner@example.com", "Other", "correct-horse")
    return (
        first,
        db.create_auth_session(first["id"]),
        second,
        db.create_auth_session(second["id"]),
    )


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _dossier_payload(**changes):
    return {
        "name": "Triphala classical formulation",
        "ingredients": ["Haritaki", "Bibhitaki", "Amalaki"],
        "sourcing_type": "Cultivated and purchased",
        "indication": "Traditional digestive use",
        "target_market": "India",
        **changes,
    }


def test_dossier_create_classify_map_review_and_history(users):
    _, token, _, _ = users
    with TestClient(app) as client:
        created = client.post("/api/v1/dossiers", json=_dossier_payload(), headers=_headers(token))
        assert created.status_code == 200
        dossier_id = created.json()["dossier_id"]
        assert created.json()["status"] == "draft"
        assert created.json()["ingredients"] == ["Haritaki", "Bibhitaki", "Amalaki"]

        classified = client.post(
            f"/api/v1/dossiers/{dossier_id}/classify", json={}, headers=_headers(token)
        )
        assert classified.status_code == 200
        assert classified.json()["status"] == "classified"
        assert classified.json()["classification"]["category"] == "Classical / Generic Medicine"

        mapped = client.post(f"/api/v1/dossiers/{dossier_id}/map", headers=_headers(token))
        assert mapped.status_code == 200
        assert mapped.json()["status"] == "mapped"
        assert set(mapped.json()["mapping"]["jurisdictions"]) == {"India"}

        reviewed = client.post(
            f"/api/v1/dossiers/{dossier_id}/review",
            json={"note": "Check current licensing requirements."},
            headers=_headers(token),
        )
        assert reviewed.status_code == 200
        assert reviewed.json()["status"] == "under_review"
        assert [item["event_type"] for item in reviewed.json()["history"]] == [
            "created", "classified", "mapped", "review_started"
        ]


def test_dossier_can_keep_both_jurisdictions_separate_and_update(users):
    owner, _, _, _ = users
    dossier = dossiers.create(
        owner["id"], "Novel formulation", ["amla"], "cultivated",
        "new formulation not found in a classical text", "Both",
    )
    updated = dossiers.update_for_user(
        dossier["dossier_id"], owner["id"], {"indication": "A refined indication"}
    )
    assert updated["indication"] == "A refined indication"
    classified = dossiers.classify_for_user(dossier["dossier_id"], owner["id"])
    assert classified["status"] == "classified"
    mapped = dossiers.map_for_user(dossier["dossier_id"], owner["id"])
    assert set(mapped["mapping"]["jurisdictions"]) == {"India", "International"}
    for jurisdiction, result in mapped["mapping"]["jurisdictions"].items():
        assert all(source["jurisdiction"] == jurisdiction for source in result["sources"])


def test_dossier_clarification_stays_draft_and_requires_category_confirmation(users):
    _, token, _, _ = users
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/dossiers",
            json=_dossier_payload(
                name="Herbal product",
                ingredients=["plant extract"],
                sourcing_type="cultivated",
                indication="daily use",
            ),
            headers=_headers(token),
        ).json()
        needs_input = client.post(
            f"/api/v1/dossiers/{created['dossier_id']}/classify",
            json={},
            headers=_headers(token),
        )
        assert needs_input.status_code == 200
        assert needs_input.json()["status"] == "draft"
        assert needs_input.json()["classification"]["needs_clarification"] is True
        assert client.post(
            f"/api/v1/dossiers/{created['dossier_id']}/map", headers=_headers(token)
        ).status_code == 409
        confirmed = client.post(
            f"/api/v1/dossiers/{created['dossier_id']}/classify",
            json={"confirmed_category": "Cosmetic"},
            headers=_headers(token),
        )
        assert confirmed.json()["status"] == "classified"
        assert confirmed.json()["classification"]["category"] == "Cosmetic"


def test_dossier_routes_require_auth_and_hide_other_users_records(users):
    _, owner_token, _, other_token = users
    with TestClient(app) as client:
        assert client.get("/api/v1/dossiers").status_code == 401
        created = client.post(
            "/api/v1/dossiers", json=_dossier_payload(), headers=_headers(owner_token)
        ).json()
        assert client.get(
            f"/api/v1/dossiers/{created['dossier_id']}", headers=_headers(other_token)
        ).status_code == 404
        assert client.delete(
            f"/api/v1/dossiers/{created['dossier_id']}", headers=_headers(other_token)
        ).status_code == 404
        assert client.delete(
            f"/api/v1/dossiers/{created['dossier_id']}", headers=_headers(owner_token)
        ).status_code == 200


def test_calendar_month_target_and_urgency_boundaries():
    assert prahari._add_calendar_months(datetime.date(2024, 8, 31), 6) == datetime.date(2025, 2, 28)
    assert prahari._add_calendar_months(datetime.date(2024, 2, 29), 6) == datetime.date(2024, 8, 29)
    today = datetime.date(2026, 1, 1)
    assert prahari._urgency(today, today) == ("red", 0)
    assert prahari._urgency(today + datetime.timedelta(days=30), today) == ("red", 30)
    assert prahari._urgency(today + datetime.timedelta(days=31), today) == ("amber", 31)
    assert prahari._urgency(today + datetime.timedelta(days=90), today) == ("amber", 90)
    assert prahari._urgency(today + datetime.timedelta(days=91), today) == ("green", 91)
    assert prahari._urgency(today - datetime.timedelta(days=1), today) == ("grey", -1)


def test_prahari_persists_both_streams_and_computes_risk_and_live_countdown(users):
    owner, token, _, _ = users
    today = datetime.date.today()
    publication = today.replace(year=today.year - 1)
    if publication.month == 2 and publication.day == 29 and not calendar_is_leap(publication.year):
        publication = publication.replace(day=28)
    alert = prahari.create(
        owner["id"], "IN-123", "Triphala herbal formulation",
        "A formulation using amalaki, bibhitaki and haritaki for digestive use.",
        publication.isoformat(), "domestic", "https://example.com/patent",
    )
    assert alert["stream"] == "domestic"
    assert alert["risk_score"] >= 0 and alert["risk_score"] <= 100
    assert alert["risk_matches"]
    assert alert["deadline_source_url"].endswith("patent-rules-2003.pdf")
    assert "not a statutory deadline" in alert["deadline_note"]
    assert alert["monitoring_target_date"] == prahari._add_calendar_months(publication, 6).isoformat()
    assert alert["urgency_band"] in {"red", "amber", "green", "grey"}

    with TestClient(app) as client:
        foreign = client.post(
            "/api/v1/prahari",
            json={
                "filing_number": "US-456",
                "title": "Botanical composition",
                "abstract": "A novel botanical composition and extraction method.",
                "publication_date": today.isoformat(),
                "stream": "foreign",
            },
            headers=_headers(token),
        )
        assert foreign.status_code == 200
        records = client.get("/api/v1/prahari", headers=_headers(token)).json()
        assert {item["stream"] for item in records} == {"domestic", "foreign"}
        assert client.delete(
            f"/api/v1/prahari/{foreign.json()['alert_id']}", headers=_headers(token)
        ).status_code == 200


def calendar_is_leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def test_prahari_rejects_invalid_dates_and_non_http_urls(users):
    _, token, _, _ = users
    payload = {
        "filing_number": "IN-1",
        "title": "Patent",
        "abstract": "Abstract text",
        "publication_date": "not-a-date",
        "stream": "domestic",
    }
    with TestClient(app) as client:
        assert client.post("/api/v1/prahari", json=payload, headers=_headers(token)).status_code == 400
        payload["publication_date"] = datetime.date.today().isoformat()
        payload["source_url"] = "javascript:alert(1)"
        assert client.post("/api/v1/prahari", json=payload, headers=_headers(token)).status_code == 400


def test_prahari_routes_are_owner_scoped(users):
    _, owner_token, _, other_token = users
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/prahari",
            json={
                "filing_number": "WO-77",
                "title": "Traditional herbal mixture",
                "abstract": "Herbal preparation.",
                "publication_date": datetime.date.today().isoformat(),
                "stream": "foreign",
            },
            headers=_headers(owner_token),
        ).json()
        assert client.get("/api/v1/prahari").status_code == 401
        assert client.get(
            f"/api/v1/prahari/{created['alert_id']}", headers=_headers(other_token)
        ).status_code == 404
        assert client.delete(
            f"/api/v1/prahari/{created['alert_id']}", headers=_headers(other_token)
        ).status_code == 404
