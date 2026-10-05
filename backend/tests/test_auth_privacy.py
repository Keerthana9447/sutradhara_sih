import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import auth, db, privacy  # noqa: E402


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", str(tmp_path / "test_auth.db"))
    db.init_db()


def _user(email="a@example.com"):
    return db.create_user(email, "Asha", "correct-horse")


# --- passwords ---------------------------------------------------------------
def test_new_passwords_use_pbkdf2(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    u = _user()
    conn = db.get_conn()
    stored = conn.execute("SELECT password_hash FROM users WHERE id = ?", (u["id"],)).fetchone()[0]
    conn.close()
    assert stored.startswith("pbkdf2_sha256$")
    assert db.authenticate_user("a@example.com", "correct-horse")["id"] == u["id"]
    assert db.authenticate_user("a@example.com", "wrong") is None
    assert db.authenticate_user("nobody@example.com", "x") is None


def test_legacy_sha256_hash_is_rejected_and_requires_reset(tmp_path, monkeypatch):
    import hashlib
    _fresh_db(tmp_path, monkeypatch)
    conn = db.get_conn()
    salt = "abc123"
    legacy = hashlib.sha256((salt + "old-pass").encode()).hexdigest()
    conn.execute("INSERT INTO users (email, name, password_hash, salt, created_at) VALUES (?,?,?,?,?)",
                 ("old@example.com", "Old", legacy, salt, "2024-01-01T00:00:00"))
    conn.commit(); conn.close()
    assert db.authenticate_user("old@example.com", "old-pass") is None
    conn = db.get_conn()
    stored = conn.execute("SELECT password_hash FROM users WHERE email='old@example.com'").fetchone()[0]
    conn.close()
    assert stored == legacy
    assert db.authenticate_user("old@example.com", "old-pass") is None


# --- tokens ------------------------------------------------------------------
def test_token_resolves_to_user_and_only_hash_is_stored(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    u = _user()
    token = db.create_auth_session(u["id"])
    assert db.get_user_by_token(token)["id"] == u["id"]
    conn = db.get_conn()
    rows = conn.execute("SELECT token_hash FROM auth_sessions").fetchall()
    conn.close()
    assert len(rows) == 1 and rows[0][0] != token and token not in rows[0][0]


def test_unknown_and_signed_out_tokens_are_rejected(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    u = _user()
    token = db.create_auth_session(u["id"])
    assert db.get_user_by_token("garbage") is None
    assert db.get_user_by_token(None) is None
    db.delete_auth_session(token)
    assert db.get_user_by_token(token) is None


def test_expired_token_is_rejected_and_deleted(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    u = _user()
    token = db.create_auth_session(u["id"])
    conn = db.get_conn()
    conn.execute("UPDATE auth_sessions SET expires_at = '2000-01-01T00:00:00'")
    conn.commit(); conn.close()
    assert db.get_user_by_token(token) is None
    conn = db.get_conn()
    assert conn.execute("SELECT COUNT(*) FROM auth_sessions").fetchone()[0] == 0
    conn.close()


def test_bearer_parsing_and_identity_cross_check(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    u = _user()
    token = db.create_auth_session(u["id"])
    assert auth.parse_bearer(f"Bearer {token}") == token
    assert auth.parse_bearer(f"bearer  {token} ") == token
    assert auth.parse_bearer("Basic abc") is None and auth.parse_bearer(None) is None
    assert auth.resolve_user(f"Bearer {token}")["id"] == u["id"]
    assert auth.resolve_user("Bearer nope") is None
    assert auth.check_claimed_user(u, None) is True
    assert auth.check_claimed_user(u, u["id"]) is True
    assert auth.check_claimed_user(u, u["id"] + 1) is False   # cannot act as someone else


def test_rate_limiter_blocks_then_recovers():
    rl = auth.RateLimiter(3, 60)
    assert all(rl.allow("k", now=t) for t in (0, 1, 2))
    assert rl.allow("k", now=3) is False
    assert rl.allow("other", now=3) is True          # keyed independently
    assert rl.allow("k", now=100) is True            # window slid past
    rl.allow("z", now=0); rl.reset("z")
    assert all(rl.allow("z", now=1) for _ in range(3))


# --- chat ownership ------------------------------------------------------------
def test_session_ownership_is_enforced_in_db_layer(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    a, b = _user("a@example.com"), _user("b@example.com")
    sess = db.create_chat_session(a["id"], "mine")
    assert db.session_belongs_to(sess["id"], a["id"]) is True
    assert db.session_belongs_to(sess["id"], b["id"]) is False
    assert db.get_chat_messages(sess["id"], b["id"]) is None
    assert db.delete_chat_session(sess["id"], b["id"]) is False


# --- DPDP coverage of the new tables -----------------------------------------
def _seed(a):
    sess = db.create_chat_session(a["id"], "Triphala patent")
    db.add_chat_message(sess["id"], "user", "Can I patent Triphala?")
    db.add_chat_message(sess["id"], "assistant", "{\"answer\": \"...\"}")
    return sess


def test_export_account_includes_chat_history_but_no_secrets(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    a = _user(); _seed(a); db.create_auth_session(a["id"])
    out = privacy.export_account(a["id"])
    assert out["account"]["email"] == "a@example.com"
    assert len(out["chat_sessions"]) == 1 and len(out["chat_sessions"][0]["messages"]) == 2
    flat = repr(out)
    assert "password" not in flat and "salt" not in flat and "token" not in flat.replace("Password hashes and login tokens", "")


def test_delete_account_removes_everything_tied_to_it(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    a, b = _user("a@example.com"), _user("b@example.com")
    _seed(a); _seed(b)
    tok = db.create_auth_session(a["id"])
    db.log_escalation("q", "cat", "India", ["Patents"], ["IN-PAT-3P"], "a@example.com")
    deleted = privacy.delete_account(a["id"])
    assert deleted["users"] == 1 and deleted["chat_sessions"] == 1 and deleted["chat_messages"] == 2
    assert deleted["auth_sessions"] == 1 and deleted["escalation"] == 1
    assert db.get_user_by_token(tok) is None
    assert db.authenticate_user("a@example.com", "correct-horse") is None
    assert db.get_chat_sessions(a["id"]) == []
    # the other user is untouched
    assert len(db.get_chat_sessions(b["id"])) == 1
    try:
        privacy.export_account(a["id"]); assert False
    except ValueError:
        pass


def test_purge_expired_covers_chat_history_and_expired_tokens(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    a = _user(); _seed(a); db.create_auth_session(a["id"])
    deleted = privacy.purge_expired(retention_days=9999)
    assert deleted["chat_sessions"] == 0 and deleted["auth_sessions"] == 0
    conn = db.get_conn()
    conn.execute("UPDATE chat_sessions SET updated_at = '2000-01-01T00:00:00'")
    conn.execute("UPDATE auth_sessions SET expires_at = '2000-01-01T00:00:00'")
    conn.commit(); conn.close()
    deleted = privacy.purge_expired(retention_days=180)
    assert deleted["chat_sessions"] == 1 and deleted["chat_messages"] == 2 and deleted["auth_sessions"] == 1
    conn = db.get_conn()
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1   # accounts never age-purged
    conn.close()


def test_compliance_status_mentions_account_rights_and_gaps():
    st = privacy.compliance_status()
    assert "DELETE /api/privacy/account" in st["right_to_erasure"]["endpoint"]
    assert st["account_security"]["implemented"] == "partial"
    assert "MFA" in st["account_security"]["detail"]
