import sqlite3
from typing import List, Dict, Any
from ast_parser import parse_python_code

DB_NAME = "codetrace.db"

def init_db(db_path: str = DB_NAME):
    """
    SQLite veritabanını ve 'code_chunks' tablosunu oluşturur.
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
    conn.commit()
    conn.close()
    print("💾 SQLite veritabanı ve 'code_chunks' tablosu hazır.")

def clear_db(db_path: str = DB_NAME):
    """
    Test amaçlı: tablodaki tüm kayıtları temizler.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM code_chunks")
    conn.commit()
    conn.close()
    print("🗑️ Veritabanı temizlendi.")

def save_chunks_to_db(chunks: List[Dict[str, Any]], db_path: str = DB_NAME):
    """
    AST'den çıkan chunk'ları SQLite veritabanına kaydeder.
    """
    if not chunks:
        print("⚠️ Kaydedilecek chunk bulunamadı.")
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
    print(f"✅ Toplam {saved_count} adet chunk veritabanına başarıyla kaydedildi.")

def get_all_chunks(db_path: str = DB_NAME) -> List[Dict[str, Any]]:
    """
    Veritabanındaki tüm kaydedilmiş chunk'ları listeler.
    """
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
    # 1. Veritabanını hazırla
    init_db()

    # 2. Her test çalıştırmasında sıfırdan başla
    clear_db()

    # 3. Test verisi oluştur
    sample_code = """
def connect_database():
    # Veritabanına bağlanır
    print("Database connected")

class AuthManager:
    def login(self, username, password):
        return True
"""
    # 4. Kodu AST ile parçala
    chunks = parse_python_code(sample_code, "auth_module.py")

    # 5. Parçaları SQLite'a kaydet
    save_chunks_to_db(chunks)

    # 6. Veritabanından geri okuyup kontrol et
    saved_data = get_all_chunks()
    print(f"\n🔍 Veritabanındaki Kayıtlı Chunk Sayısı: {len(saved_data)}")
    for item in saved_data:
        print(f" 📌 ID #{item['id']} | {item['file_path']} -> {item['name']} ({item['type']})")
