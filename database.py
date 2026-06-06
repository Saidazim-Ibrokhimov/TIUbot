import asyncpg
import os

class Database:
    def __init__(self, dsn):
        self.dsn = dsn # Render bergan Database URL
        self.conn = None

    async def connect(self):
        self.conn = await asyncpg.connect(self.dsn)
        await self.create_tables()

    async def create_tables(self):
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                full_name TEXT,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            );
            CREATE TABLE IF NOT EXISTS subjects (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE
            );
            CREATE TABLE IF NOT EXISTS questions (
                id SERIAL PRIMARY KEY,
                subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
                question TEXT,
                answer TEXT
            );
        """)

    async def add_user(self, user_id, full_name, username):
        await self.conn.execute(
            "INSERT INTO users (user_id, full_name, username) VALUES ($1, $2, $3) ON CONFLICT(user_id) DO NOTHING",
            user_id, full_name, username
        )

    async def get_users_count(self):
        return await self.conn.fetchval("SELECT COUNT(*) FROM users")

    async def get_all_users(self):
        return await self.conn.fetch("SELECT user_id FROM users")

    async def get_all_users_info(self):
        return await self.conn.fetch("SELECT user_id, full_name, created_at, status FROM users")

    async def get_stats_summary(self):
        total = await self.conn.fetchval("SELECT COUNT(*) FROM users")
        active = await self.conn.fetchval("SELECT COUNT(*) FROM users WHERE status = 'active'")
        blocked = await self.conn.fetchval("SELECT COUNT(*) FROM users WHERE status = 'blocked'")
        return total, active, blocked

    async def add_subject(self, name):
        try:
            await self.conn.execute("INSERT INTO subjects (name) VALUES ($1)", name)
            return True
        except:
            return False

    async def get_subjects(self):
        return await self.conn.fetch("SELECT id, name FROM subjects")

    async def add_question(self, subject_id, question, answer):
        await self.conn.execute("INSERT INTO questions (subject_id, question, answer) VALUES ($1, $2, $3)",
                                subject_id, question, answer)

    async def check_and_add_question(self, subject_id, question, answer):
        exists = await self.conn.fetchval("SELECT id FROM questions WHERE subject_id = $1 AND question = $2", subject_id, question)
        if exists: return False
        await self.add_question(subject_id, question, answer)
        return True

    async def search_question(self, subject_id, query_text):
        rows = await self.conn.fetch("SELECT question, answer FROM questions WHERE subject_id = $1", subject_id)
        
        def clean(t): return " ".join(t.lower().replace("'", "").replace("?", "").split())
        
        cleaned_query = clean(query_text)
        for row in rows:
            if cleaned_query in clean(row['question']): return (row['answer'],)
        return None

    async def close(self):
        await self.conn.close()