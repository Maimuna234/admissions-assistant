"""Backend user authentication store, mirroring the Figma prototype's sql.js `users` table."""
import hashlib
import os
import sqlite3
import time
import uuid
from typing import Optional

DB_PATH = os.getenv("SQL_DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "admissions_structured.db"))

VALID_ROLES = {"admin", "tutor"}
VALID_STATUSES = {"active", "inactive", "pending", "rejected"}


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(plain: str) -> str:
    """SHA-256 hex digest — matches the prototype's Web Crypto `hashPassword()` output."""
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def ensure_users_schema() -> None:
    conn = _connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id               TEXT PRIMARY KEY,
            name             TEXT NOT NULL,
            email            TEXT UNIQUE NOT NULL,
            password_hash    TEXT NOT NULL,
            role             TEXT NOT NULL DEFAULT 'tutor'
                               CHECK(role IN ('admin','tutor')),
            department       TEXT,
            status           TEXT NOT NULL DEFAULT 'pending'
                               CHECK(status IN ('active','inactive','pending','rejected')),
            rejection_reason TEXT,
            last_login       TEXT,
            created_at       TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def seed_default_users() -> None:
    conn = _connect()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", ("admin@liverpool.ac.uk",)).fetchone()
    if existing:
        conn.close()
        return

    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    admin_hash = hash_password("Admin1234!")
    tutor_hash = hash_password("Tutor1234!")
    seed = [
        ("u1", "Dr. Sarah Mitchell", "admin@liverpool.ac.uk", admin_hash, "admin", "Computer Science", "active"),
        ("u2", "James Okafor", "j.okafor@liverpool.ac.uk", tutor_hash, "tutor", "Computer Science", "active"),
        ("u3", "Priya Nair", "p.nair@liverpool.ac.uk", tutor_hash, "tutor", "Computer Science", "active"),
        ("u4", "Thomas Greenwood", "t.greenwood@liverpool.ac.uk", tutor_hash, "tutor", "Electrical Engineering", "inactive"),
        ("u5", "Amara Diallo", "a.diallo@liverpool.ac.uk", tutor_hash, "tutor", "Computer Science", "pending"),
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO users (id, name, email, password_hash, role, department, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [(*row, now) for row in seed],
    )
    conn.commit()
    conn.close()


def init_auth_db() -> None:
    ensure_users_schema()
    seed_default_users()


def get_user_by_email(email: str) -> Optional[sqlite3.Row]:
    conn = _connect()
    row = conn.execute("SELECT * FROM users WHERE lower(email) = ?", (email.strip().lower(),)).fetchone()
    conn.close()
    return row


def list_users() -> list:
    conn = _connect()
    rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def create_user(name: str, email: str, password: str, role: str = "tutor", department: Optional[str] = None) -> dict:
    conn = _connect()
    user_id = f"u{uuid.uuid4().hex[:10]}"
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    conn.execute(
        """
        INSERT INTO users (id, name, email, password_hash, role, department, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
        """,
        (user_id, name, email.strip().lower(), hash_password(password), role, department, now),
    )
    conn.commit()
    conn.close()
    return {"id": user_id, "name": name, "email": email, "role": role, "department": department, "status": "pending"}


def update_last_login(user_id: str) -> None:
    conn = _connect()
    conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (time.strftime("%Y-%m-%dT%H:%M:%S"), user_id))
    conn.commit()
    conn.close()


def update_user_status(user_id: str, status: str, rejection_reason: Optional[str] = None) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    conn = _connect()
    conn.execute(
        "UPDATE users SET status = ?, rejection_reason = ? WHERE id = ?",
        (status, rejection_reason, user_id),
    )
    conn.commit()
    conn.close()
