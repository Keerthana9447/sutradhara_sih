import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import db, privacy  # noqa: E402


def _fresh_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_privacy.db")
    monkeypatch.setattr(db, "_DB_PATH", db_path)
    db.init_db()


def test_redact_pii_masks_email_and_long_digit_runs():
    text = "contact me at jane.doe@example.com or 9876543210 about Triphala"
    redacted = privacy.redact_pii(text)
    assert "jane.doe@example.com" not in redacted
    assert "9876543210" not in redacted
    assert "[redacted-email]" in redacted
    assert "[redacted-number]" in redacted


def test_redact_pii_leaves_clean_text_untouched():
    text = "Can I patent a classical Ayurvedic formulation?"
    assert privacy.redact_pii(text) == text


def test_log_audit_stores_redacted_query_not_raw(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    db.log_audit(
        "reach me at test@example.com re: Triphala patent",
        "India", "Classical / Generic Medicine", 0.8, False, [{"id": "IN-PAT-3P"}],
    )
    conn = db.get_conn()
    row = conn.execute("SELECT query FROM audit_log").fetchone()
    conn.close()
    assert "test@example.com" not in row["query"]
    assert "[redacted-email]" in row["query"]


def test_access_report_requires_at_least_one_field(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    try:
        privacy.access_report()
        assert False, "should have raised"
    except ValueError:
        pass


def test_access_report_matches_by_query_text(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    db.log_audit("Can I patent Triphala?", "India", "Classical / Generic Medicine", 0.8, False, [])
    report = privacy.access_report(query_text="Can I patent Triphala?")
    assert report["matched_records"] == 1
    assert len(report["records"]["audit_log"]) == 1


def test_access_report_matches_by_contact_email(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    db.log_escalation("Need help with GI filing", "Classical / Generic Medicine", "India",
                       ["Geographical Indications"], ["IN-PAT-3P"], "user@contact.com")
    report = privacy.access_report(contact_email="user@contact.com")
    assert report["matched_records"] == 1


def test_erase_deletes_matched_rows_across_tables(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    db.log_audit("Can I patent Triphala?", "India", "Classical / Generic Medicine", 0.8, False, [])
    db.log_feedback("Can I patent Triphala?", None, 4, "helpful")
    deleted = privacy.erase(query_text="Can I patent Triphala?")
    assert deleted["audit_log"] == 1
    assert deleted["feedback"] == 1
    assert privacy.access_report(query_text="Can I patent Triphala?")["matched_records"] == 0


def test_purge_expired_deletes_rows_past_retention(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    db.log_audit("old query", "India", "Classical / Generic Medicine", 0.8, False, [])
    deleted = privacy.purge_expired(retention_days=0)
    assert deleted["audit_log"] == 1
    conn = db.get_conn()
    remaining = conn.execute("SELECT COUNT(*) c FROM audit_log").fetchone()["c"]
    conn.close()
    assert remaining == 0


def test_purge_expired_keeps_rows_within_retention(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    db.log_audit("recent query", "India", "Classical / Generic Medicine", 0.8, False, [])
    deleted = privacy.purge_expired(retention_days=9999)
    assert deleted["audit_log"] == 0


def test_compliance_status_lists_gaps_honestly():
    status = privacy.compliance_status()
    assert status["right_to_access"]["implemented"] is True
    assert status["right_to_erasure"]["implemented"] is True
    assert len(status["not_implemented"]) > 0
