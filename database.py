import psycopg2
import psycopg2.extras
import os

def get_db():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"), cursor_factory=psycopg2.extras.RealDictCursor)
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prescriptions (
            id SERIAL PRIMARY KEY,
            hospital TEXT,
            visit_date TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prescription_drugs (
            id SERIAL PRIMARY KEY,
            prescription_id INTEGER REFERENCES prescriptions(id) ON DELETE CASCADE,
            drug_name TEXT,
            ingredient TEXT,
            days INTEGER,
            dosage TEXT,
            frequency TEXT,
            times TEXT,
            meal_timing TEXT,
            refill_date TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS medication_logs (
            id SERIAL PRIMARY KEY,
            drug_id INTEGER REFERENCES prescription_drugs(id) ON DELETE CASCADE,
            taken_date TEXT,
            time_slot TEXT DEFAULT '',
            is_taken INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS share_links (
            id SERIAL PRIMARY KEY,
            token TEXT,
            prescription_id INTEGER REFERENCES prescriptions(id) ON DELETE CASCADE,
            created_at TEXT
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
