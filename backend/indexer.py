import sqlite3
import os
from typing import List, Dict, Any
from ast_parser import parse_python_code

DB_PATH = os.path.join(os.path.dirname(__file__), "codetrace.db")

def init_db(db_path: str = DB_PATH):
    """
    SQLite veritabanını, 'code_chunks' ve 'file_contents' tablolarını oluşturur.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS code_chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT NOT NULL,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        start_line INTEGER,
        end_line INTEGER,
        code_content TEXT NOT NULL
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS file_contents (
        file_path TEXT PRIMARY KEY,
        raw_content TEXT NOT NULL
    );
    """)
    conn.commit()
    conn.close()
    print("[INFO] SQLite veritabanı ve 'code_chunks' / 'file_contents' tabloları hazır.")

def clear_db(db_path: str = DB_PATH):
    """
    Test amaçlı: tablolardaki tüm kayıtları temizler.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM code_chunks")
    cursor.execute("DELETE FROM file_contents")
    conn.commit()
    conn.close()
    print("[INFO] Veritabanı temizlendi.")

def save_chunks_to_db(chunks: List[Dict[str, Any]], db_path: str = DB_PATH):
    """
    AST'den çıkan chunk'ları SQLite veritabanına kaydeder.
    """
    if not chunks:
        print("[WARNING] Kaydedilecek chunk bulunamadı.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    for chunk in chunks:
        cursor.execute("""
        INSERT INTO code_chunks (file_path, name, type, start_line, end_line, code_content)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            chunk["file_path"],
            chunk["name"],
            chunk["type"],
            chunk["start_line"],
            chunk["end_line"],
            chunk["code_content"]
        ))
    conn.commit()
    saved_count = len(chunks)
    conn.close()
    print(f"[SUCCESS] Toplam {saved_count} adet chunk veritabanına başarıyla kaydedildi.")

def save_file_content(file_path: str, raw_content: str, db_path: str = DB_PATH):
    """
    Bir dosyanın GitHub'dan çekilen tam ham içeriğini veritabanına kaydeder.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO file_contents (file_path, raw_content) VALUES (?, ?)
        ON CONFLICT(file_path) DO UPDATE SET raw_content = excluded.raw_content
    """, (file_path, raw_content))
    conn.commit()
    conn.close()

def get_file_content(file_path: str, db_path: str = DB_PATH) -> str:
    """
    Bir dosyanın tam ham içeriğini (varsa) döner; yoksa boş string döner.
    """
    if not os.path.exists(db_path):
        return ""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT raw_content FROM file_contents WHERE file_path = ?", (file_path,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else ""

def get_all_chunks(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """
    Veritabanındaki tüm kaydedilmiş chunk'ları listeler.
    """
    if not os.path.exists(db_path):
        return []
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, file_path, name, type, start_line, end_line, code_content FROM code_chunks")
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        results.append({
            "id": row[0],
            "file_path": row[1],
            "name": row[2],
            "type": row[3],
            "start_line": row[4],
            "end_line": row[5],
            "code_content": row[6]
        })
    return results

if __name__ == "__main__":
    init_db()
    clear_db()
    sample_code = """
def connect_database():
    print("Database connected")

class AuthManager:
    def login(self, username, password):
        return True
"""
    chunks = parse_python_code(sample_code, "auth_module.py")
    save_chunks_to_db(chunks)
    saved_data = get_all_chunks()
    print(f"\n[INFO] Veritabanındaki Kayıtlı Chunk Sayısı: {len(saved_data)}")
