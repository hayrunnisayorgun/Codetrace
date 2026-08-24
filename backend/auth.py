import sqlite3
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from indexer import DB_PATH

SESSION_TTL_HOURS = 12
MIN_PASSWORD_LENGTH = 8


def init_users_table(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL
    );
    """)
    # Session tokens are never stored in plaintext: reading the database must
    # not be enough to take over an account, so only a SHA-256 digest is kept.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token_hash TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        expires_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """)
    conn.commit()
    conn.close()


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100_000).hex()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _create_session(user_id: int, db_path: str = DB_PATH) -> str:
    """Issue a session token, store its digest, and return the raw token."""
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)).isoformat()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (_hash_token(token), user_id, expires_at)
    )
    # Keep expired sessions from piling up.
    cursor.execute("DELETE FROM sessions WHERE expires_at < ?", (datetime.now(timezone.utc).isoformat(),))
    conn.commit()
    conn.close()
    return token


def get_user_by_token(token: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Return the token's user, or None if the token is invalid or expired."""
    if not token:
        return None

    init_users_table(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT users.email, users.name, sessions.expires_at
        FROM sessions JOIN users ON users.id = sessions.user_id
        WHERE sessions.token_hash = ?
    """, (_hash_token(token),))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    email, name, expires_at = row
    if datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
        revoke_session(token, db_path)
        return None

    return {"email": email, "name": name}


def revoke_session(token: str, db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash_token(token),))
    conn.commit()
    conn.close()


def register_user(email: str, password: str, name: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    if len(password) < MIN_PASSWORD_LENGTH:
        return {"status": "error", "message": f"Password must be at least {MIN_PASSWORD_LENGTH} characters."}

    init_users_table(db_path)

    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (email, name, password_hash, salt) VALUES (?, ?, ?, ?)",
            (email, name, password_hash, salt)
        )
        user_id = cursor.lastrowid
        conn.commit()
    except sqlite3.IntegrityError:
        # Leaning on the UNIQUE constraint instead of SELECT-then-INSERT: one
        # query, and no race between the check and the write.
        return {"status": "error", "message": "An account with this email already exists."}
    finally:
        conn.close()

    token = _create_session(user_id, db_path)
    return {"status": "success", "token": token, "user": {"email": email, "name": name}}


def login_user(email: str, password: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    init_users_table(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, password_hash, salt FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()

    # Hash even when no user matched: otherwise the response-time difference
    # would reveal which emails are registered.
    if not row:
        _hash_password(password, "dummy_salt_for_constant_time")
        return {"status": "error", "message": "Incorrect email or password."}

    user_id, name, stored_hash, salt = row
    if not hmac.compare_digest(_hash_password(password, salt), stored_hash):
        return {"status": "error", "message": "Incorrect email or password."}

    token = _create_session(user_id, db_path)
    return {"status": "success", "token": token, "user": {"email": email, "name": name}}
