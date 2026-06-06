import sqlite3
import datetime

class Database:
    def __init__(self, db_name="data.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        
        # 1. Foydalanuvchilar jadvali (status va created_at qo'shildi)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        """)
        
        # Jadvalni yangilash: Agar ustunlar oldin bo'lmagan bo'lsa, xatolik bermasligi uchun
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        except: pass
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'")
        except: pass

        # 2. Fanlar jadvali
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE
            )
        """)
        
        # 3. Savol-javoblar jadvali
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER,
                question TEXT,
                answer TEXT,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
            )
        """)
        self.conn.commit()

    # --- FOYDALANUVCHILAR ---
    def add_user(self, user_id, full_name, username):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, full_name, username) VALUES (?, ?, ?)",
            (user_id, full_name, username)
        )
        self.conn.commit()

    def get_users_count(self):
        cursor = self.conn.cursor()
        return cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    def get_all_users(self):
        cursor = self.conn.cursor()
        return cursor.execute("SELECT user_id FROM users").fetchall()

    def get_all_users_info(self):
        cursor = self.conn.cursor()
        return cursor.execute("SELECT user_id, full_name, created_at, status FROM users").fetchall()

    def get_stats_summary(self):
        cursor = self.conn.cursor()
        total = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active = cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'active'").fetchone()[0]
        blocked = cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'blocked'").fetchone()[0]
        return total, active, blocked

    # --- FANLAR VA SAVOLLAR ---
    def add_subject(self, name):
        cursor = self.conn.cursor()
        try:
            cursor.execute("INSERT INTO subjects (name) VALUES (?)", (name,))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_subjects(self):
        cursor = self.conn.cursor()
        return cursor.execute("SELECT id, name FROM subjects").fetchall()

    def add_question(self, subject_id, question_text, answer_text):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO questions (subject_id, question, answer) VALUES (?, ?, ?)",
                       (subject_id, question_text, answer_text))
        self.conn.commit()

    def check_and_add_question(self, subject_id, question_text, answer_text):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM questions WHERE subject_id = ? AND question = ?", (subject_id, question_text))
        if cursor.fetchone(): return False
        cursor.execute("INSERT INTO questions (subject_id, question, answer) VALUES (?, ?, ?)", 
                       (subject_id, question_text, answer_text))
        self.conn.commit()
        return True

    def search_question(self, subject_id, query_text):
        cursor = self.conn.cursor()
        cursor.execute("SELECT question, answer FROM questions WHERE subject_id = ?", (subject_id,))
        rows = cursor.fetchall()
        
        def clean(t): return " ".join(t.lower().replace("'", "").replace("?", "").split())
        
        cleaned_query = clean(query_text)
        for q, a in rows:
            if cleaned_query in clean(q): return (a,)
        return None

    def close(self):
        self.conn.close()