import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import db, privacy  # noqa: E402


def _fresh_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_privacy_dpdp.db")
    monkeypatch.setattr(db, "_DB_PATH", db_path)
    db.init_db()


# ---------------------------------------------------------------------------
# Consent Manager reference implementation
# ---------------------------------------------------------------------------
def test_request_consent_requires_all_fields(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    try:
        privacy.request_consent("", "purpose", ["query_text"])
        assert False, "should have raised on empty data_principal_ref"
    except ValueError:
        pass
    try:
        privacy.request_consent("user@example.com", "purpose", [])
        assert False, "should have raised on empty data_categories"
    except ValueError:
        pass


def test_consent_lifecycle_request_grant_revoke(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    consent = privacy.request_consent("user@example.com", "Answer legal queries", ["query_text"])
    assert consent["status"] == "requested"
    assert consent["granted_at"] is None

    granted = privacy.grant_consent(consent["consent_id"])
    assert granted["status"] == "granted"
    assert privacy.is_consent_valid(consent["consent_id"]) is True

    revoked = privacy.revoke_consent(consent["consent_id"])
    assert revoked["status"] == "revoked"
    assert privacy.is_consent_valid(consent["consent_id"]) is False


def test_cannot_grant_a_consent_twice(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    consent = privacy.request_consent("user@example.com", "purpose", ["query_text"])
    privacy.grant_consent(consent["consent_id"])
    try:
        privacy.grant_consent(consent["consent_id"])
        assert False, "should have raised — already granted"
    except ValueError:
        pass


def test_revoke_is_idempotent(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    consent = privacy.request_consent("user@example.com", "purpose", ["query_text"])
    privacy.grant_consent(consent["consent_id"])
    first = privacy.revoke_consent(consent["consent_id"])
    second = privacy.revoke_consent(consent["consent_id"])
    assert first["status"] == second["status"] == "revoked"


def test_expired_consent_is_invalid_and_auto_transitions(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    consent = privacy.request_consent("user@example.com", "purpose", ["query_text"], expires_in_days=-1)
    privacy.grant_consent(consent["consent_id"])
    assert privacy.is_consent_valid(consent["consent_id"]) is False
    assert privacy.get_consent(consent["consent_id"])["status"] == "expired"


def test_list_consents_filters_by_data_principal(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    privacy.request_consent("a@example.com", "purpose", ["query_text"])
    privacy.request_consent("b@example.com", "purpose", ["query_text"])
    only_a = privacy.list_consents("a@example.com")
    assert len(only_a) == 1
    assert only_a[0]["data_principal_ref"] == "a@example.com"
    assert len(privacy.list_consents()) == 2


# ---------------------------------------------------------------------------
# DPIA register
# ---------------------------------------------------------------------------
def test_record_dpia_validates_risk_level(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    ok = privacy.record_dpia("Query logging", "medium", reviewer="alice")
    assert ok["risk_level"] == "medium"
    try:
        privacy.record_dpia("Query logging", "catastrophic")
        assert False, "should have raised on invalid risk_level"
    except ValueError:
        pass


def test_list_dpias_returns_recorded_entries(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    privacy.record_dpia("Audit trail", "low")
    privacy.record_dpia("Escalation contact capture", "medium")
    assert len(privacy.list_dpias()) == 2


# ---------------------------------------------------------------------------
# Breach register + notification clock
# ---------------------------------------------------------------------------
def test_report_breach_requires_description(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    try:
        privacy.report_breach("")
        assert False, "should have raised"
    except ValueError:
        pass


def test_breach_notification_clock_not_overdue_when_fresh(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    breach = privacy.report_breach("Test incident", ["query_text"], severity="low")
    clock = breach["notification_clock"]
    assert clock["board_notification_overdue"] is False
    assert clock["hours_since_detection"] < 1


def test_breach_notification_clock_overdue_when_old_and_not_notified(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    breach = privacy.report_breach("Test incident", severity="high")
    conn = db.get_conn()
    old = "2000-01-01T00:00:00"
    conn.execute("UPDATE breach_register SET detected_at = ? WHERE breach_id = ?", (old, breach["breach_id"]))
    conn.commit()
    conn.close()
    refreshed = privacy.get_breach(breach["breach_id"])
    assert refreshed["notification_clock"]["board_notification_overdue"] is True


def test_notify_board_and_principals_clears_overdue_flag(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    breach = privacy.report_breach("Test incident", severity="high")
    conn = db.get_conn()
    conn.execute("UPDATE breach_register SET detected_at = ? WHERE breach_id = ?",
                 ("2000-01-01T00:00:00", breach["breach_id"]))
    conn.commit()
    conn.close()
    privacy.notify_board(breach["breach_id"])
    privacy.notify_principals(breach["breach_id"])
    refreshed = privacy.get_breach(breach["breach_id"])
    assert refreshed["notification_clock"]["board_notification_overdue"] is False
    assert refreshed["notification_clock"]["principal_notification_overdue"] is False


def test_notify_unknown_breach_raises(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    try:
        privacy.notify_board("breach_doesnotexist")
        assert False, "should have raised"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Records of Processing Activities (ROPA)
# ---------------------------------------------------------------------------
def test_log_processing_activity_requires_fields(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    try:
        privacy.log_processing_activity("", ["query_text"], "legitimate use")
        assert False, "should have raised"
    except ValueError:
        pass


def test_ropa_entries_are_listed_newest_first(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    privacy.log_processing_activity("Audit logging", ["query_text"], "legitimate use", 180)
    privacy.log_processing_activity("Feedback analysis", ["feedback_text"], "legitimate use", 365)
    entries = privacy.list_processing_activities()
    assert len(entries) == 2
    assert entries[0]["purpose"] == "Feedback analysis"


# ---------------------------------------------------------------------------
# Cross-border transfer restrictions
# ---------------------------------------------------------------------------
def test_check_transfer_allows_by_default_when_no_blocklist_configured(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    monkeypatch.delenv("SUTRADHARA_CROSS_BORDER_BLOCKLIST", raising=False)
    result = privacy.check_transfer("Germany")
    assert result["decision"] == "allowed"


def test_check_transfer_blocks_configured_destination(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    monkeypatch.setenv("SUTRADHARA_CROSS_BORDER_BLOCKLIST", "China, Russia")
    blocked = privacy.check_transfer("China")
    allowed = privacy.check_transfer("France")
    assert blocked["decision"] == "blocked"
    assert allowed["decision"] == "allowed"


def test_check_transfer_is_case_insensitive_and_logs_every_decision(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    monkeypatch.setenv("SUTRADHARA_CROSS_BORDER_BLOCKLIST", "china")
    privacy.check_transfer("CHINA")
    privacy.check_transfer("Japan")
    log = privacy.list_transfer_log()
    assert len(log) == 2
    decisions = {row["destination_country"]: row["decision"] for row in log}
    assert decisions["CHINA"] == "blocked"
    assert decisions["Japan"] == "allowed"


def test_check_transfer_requires_destination():
    try:
        privacy.check_transfer("")
        assert False, "should have raised"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Compliance status reflects the new, partially-closed gaps honestly
# ---------------------------------------------------------------------------
def test_compliance_status_reports_new_partial_sections():
    status = privacy.compliance_status()
    assert status["consent_manager"]["implemented"] == "partial"
    assert status["significant_data_fiduciary_obligations"]["implemented"] == "partial"
    assert status["cross_border_transfer_restrictions"]["implemented"] == "partial"
    # still honestly lists what remains unimplemented, never silently drops the caveat
    assert any("Consent Manager" in item for item in status["not_implemented"])
