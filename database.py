import sqlite3

# 앱 전체에서 재사용할 연결 하나만 만듦
_conn = sqlite3.connect("database.db", timeout=10, check_same_thread=False)
_conn.row_factory = sqlite3.Row
_conn.execute("PRAGMA foreign_keys = ON")    # 외래키 활성화
_conn.execute("PRAGMA journal_mode = WAL")   # WAL 모드 — 동시 읽기/쓰기 충돌 방지

def get_db():
    return _conn    # 항상 같은 연결 반환 (매번 새로 안 만듦)

def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS prescriptions (    -- 테이블 없으면 만들고, 있으면 넘어가
            id INTEGER PRIMARY KEY AUTOINCREMENT,    -- 자동 증가 고유 ID
            hospital TEXT,                            -- 병원명
            visit_date TEXT                           -- 진료일
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS prescription_drugs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prescription_id INTEGER,
            drug_name TEXT,
            ingredient TEXT,                        -- 성분명 (e약은요 API에서 자동 검색)
            days INTEGER,
            dosage TEXT,
            frequency TEXT,
            times TEXT,
            meal_timing TEXT,
            refill_date TEXT,
            FOREIGN KEY (prescription_id) REFERENCES prescriptions(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS medication_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        drug_id INTEGER,
        taken_date TEXT,
        time_slot TEXT DEFAULT '',
        is_taken INTEGER DEFAULT 0,
        FOREIGN KEY (drug_id) REFERENCES prescription_drugs(id) ON DELETE CASCADE
    )
""")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS share_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE,
            prescription_id INTEGER,
            created_at TEXT,
            FOREIGN KEY (prescription_id) REFERENCES prescriptions(id) ON DELETE CASCADE
        )
    """)

        # 기존 DB에 time_slot 컬럼 없으면 추가 (마이그레이션)
    try:
        conn.execute("ALTER TABLE medication_logs ADD COLUMN time_slot TEXT DEFAULT ''")
        conn.commit()
    except:
        pass

        conn.commit()