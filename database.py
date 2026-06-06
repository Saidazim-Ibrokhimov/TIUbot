import asyncpg

class Database:
    def __init__(self, dsn):
        self.dsn = dsn
        self.conn = None

    async def connect(self):
        # pool yaratish ulanishlarni barqaror saqlaydi
        self.conn = await asyncpg.create_pool(self.dsn)
        await self.create_tables()

    async def create_tables(self):
        async with self.conn.acquire() as connection:
            await connection.execute("""
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
        async with self.conn.acquire() as connection:
            await connection.execute(
                "INSERT INTO users (user_id, full_name, username) VALUES ($1, $2, $3) ON CONFLICT(user_id) DO NOTHING",
                user_id, full_name, username
            )

    async def get_subjects(self):
        async with self.conn.acquire() as connection:
            return await connection.fetch("SELECT id, name FROM subjects")

    async def get_all_users_info(self):
        async with self.conn.acquire() as connection:
            return await connection.fetch("SELECT user_id, full_name, created_at, status FROM users")

    async def get_stats_summary(self):
        async with self.conn.acquire() as connection:
            total = await connection.fetchval("SELECT COUNT(*) FROM users")
            active = await connection.fetchval("SELECT COUNT(*) FROM users WHERE status = 'active'")
            blocked = await connection.fetchval("SELECT COUNT(*) FROM users WHERE status = 'blocked'")
            return total, active, blocked

    async def add_subject(self, name):
        async with self.conn.acquire() as connection:
            try:
                await connection.execute("INSERT INTO subjects (name) VALUES ($1)", name)
                return True
            except:
                return False

    async def check_and_add_question(self, subject_id, question, answer):
        async with self.conn.acquire() as connection:
            exists = await connection.fetchval("SELECT id FROM questions WHERE subject_id = $1 AND question = $2", subject_id, question)
            if exists: return False
            await connection.execute("INSERT INTO questions (subject_id, question, answer) VALUES ($1, $2, $3)", subject_id, question, answer)
            return True

    async def add_question(self, subject_id, question, answer):
        async with self.conn.acquire() as connection:
            await connection.execute("INSERT INTO questions (subject_id, question, answer) VALUES ($1, $2, $3)", subject_id, question, answer)

    async def search_question(self, subject_id, query_text):
        async with self.conn.acquire() as connection:
            rows = await connection.fetch("SELECT question, answer FROM questions WHERE subject_id = $1", subject_id)
            # Oddiy qidiruv logikasi
            for row in rows:
                if query_text.lower() in row['question'].lower():
                    return (row['answer'],)
            return None