"""
Admin / Ministry Role Authentication — RBAC extension

Adds a second account type: admin / ministry role.  Citizens get role='citizen'
(default); ministry users get role='admin'.

The admin role is set at account creation via a shared SUTRADHARA_ADMIN_CODE env
variable. This is an invite-code pattern suitable for a hackathon prototype;
a production system would use a proper admin provisioning flow.
"""

import os
import hmac
from typing import Optional
from . import db, auth

def configured_admin_invite_code() -> str:
    """Admin provisioning is disabled unless deployment supplies a secret."""
    return os.environ.get("SUTRADHARA_ADMIN_CODE", "").strip()


def create_admin_user(email: str, name: str, password: str, invite_code: str):
    """Create a new admin user if the invite code matches."""
    expected = configured_admin_invite_code()
    if not expected:
        raise RuntimeError("Admin self-service signup is disabled; provision admins out of band.")
    if not hmac.compare_digest(invite_code, expected):
        raise ValueError("Invalid admin invite code.")
    conn = db.get_conn()
    # Add role column if missing
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "role" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'citizen'")
        conn.commit()
    conn.close()
    user = db.create_user(email, name, password)
    conn = db.get_conn()
    conn.execute("UPDATE users SET role='admin' WHERE id=?", (user["id"],))
    conn.commit()
    conn.close()
    user["role"] = "admin"
    return user


def get_user_role(user_id: int) -> str:
    conn = db.get_conn()
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "role" not in cols:
        conn.close()
        return "citizen"
    row = conn.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    if row is None:
        return "citizen"
    return row["role"] or "citizen"


def require_admin(user: dict):
    """Raise ValueError if the user is not an admin."""
    role = get_user_role(user["id"])
    if role != "admin":
        raise PermissionError("Admin role required.")


def ensure_role_column():
    """Idempotent: add role column to users table if missing."""
    conn = db.get_conn()
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "role" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'citizen'")
        conn.commit()
    conn.close()
