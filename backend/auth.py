import sqlite3
import hashlib
import secrets
from typing import Dict, Any
from indexer import DB_PATH


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
    conn.commit()
    conn.close()


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100_000).hex()


def register_user(email: str, password: str, name: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    init_users_table(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return {"status": "error", "message": "Bu e-posta ile zaten bir hesap var."}

    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)

    cursor.execute(
        "INSERT INTO users (email, name, password_hash, salt) VALUES (?, ?, ?, ?)",
        (email, name, password_hash, salt)
    )
    conn.commit()
    conn.close()

    return {"status": "success", "user": {"email": email, "name": name}}


def login_user(email: str, password: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    init_users_table(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name, password_hash, salt FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"status": "error", "message": "E-posta veya şifre hatalı."}

    name, stored_hash, salt = row
    if _hash_password(password, salt) != stored_hash:
        return {"status": "error", "message": "E-posta veya şifre hatalı."}

    return {"status": "success", "user": {"email": email, "name": name}}
