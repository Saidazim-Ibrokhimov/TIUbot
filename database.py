import sqlite3

class Database:
    def __init__(self, db_name="data.db"):
        """Ma'lumotlar bazasiga ulanish va jadvallarni yaratish"""
        self.conn = sqlite3.connect(db_name)
        self.create_tables()

    def create_tables(self):
        """Bot ishlashi uchun kerakli barcha jadvallarni yaratish"""
        cursor = self.conn.cursor()
        
        # 1. Foydalanuvchilar jadvali
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT,
                username TEXT
            )
        """)
        
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

    # --- FOYDALANUVCHILAR BILAN ISHLASH ---

    def add_user(self, user_id, full_name, username):
        """Yangi foydalanuvchini bazaga qo'shish (agar u avval yo'q bo'lsa)"""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, full_name, username) VALUES (?, ?, ?)",
            (user_id, full_name, username)
        )
        self.conn.commit()

    def get_users_count(self):
        """Jami foydalanuvchilar sonini olish (Statistika uchun)"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        result = cursor.fetchone()
        return result[0] if result else 0

    def get_all_users(self):
        """Barcha foydalanuvchilarni olish (Rassilka uchun)"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        return cursor.fetchall()
    
    def get_all_users_info(self):
    # Jami userlar, qo'shilish sanasi va statusi bilan
        return self.cursor.execute("SELECT user_id, full_name, created_at, status FROM users").fetchall()

    def get_stats_summary(self):
        total = self.cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active = self.cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'active'").fetchone()[0]
        blocked = self.cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'blocked'").fetchone()[0]
        return total, active, blocked


    # --- FANLAR (SUBJECTS) BILAN ISHLASH ---

    def add_subject(self, name):
        """Yangi fan qo'shish. Agar fan allaqachon bo'lsa False qaytaradi"""
        cursor = self.conn.cursor()
        try:
            cursor.execute("INSERT INTO subjects (name) VALUES (?)", (name,))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_subjects(self):
        """Barcha fanlar ro'yxatini olish"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name FROM subjects")
        return cursor.fetchall()


    # --- SAVOL-JAVOBLAR BILAN ISHLASH ---

    def add_question(self, subject_id, question_text, answer_text):
        """Yakkalik savol va javobni to'g'ridan-to'g'ri bazaga qo'shish"""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO questions (subject_id, question, answer) VALUES (?, ?, ?)",
            (subject_id, question_text, answer_text)
        )
        self.conn.commit()

    def check_and_add_question(self, subject_id, question_text, answer_text):
        """
        Fayldan blokli o'qish uchun maxsus metod.
        Savol bazada bor-yo'qligini tekshiradi:
        - Agar bo'lmasa: bazaga qo'shadi va True qaytaradi.
        - Agar allaqachon bo'lsa: qayta qo'shmaydi va False qaytaradi.
        """
        cursor = self.conn.cursor()
        
        # Ushbu fanga tegishli aynan shunday savol borligini tekshirish
        cursor.execute(
            "SELECT id FROM questions WHERE subject_id = ? AND question = ?", 
            (subject_id, question_text)
        )
        existing = cursor.fetchone()
        
        if existing:
            return False  # Savol bazada allaqachon mavjud
            
        # Agar savol topilmasa, yangi qator sifatida qo'shamiz
        cursor.execute(
            "INSERT INTO questions (subject_id, question, answer) VALUES (?, ?, ?)", 
            (subject_id, question_text, answer_text)
        )
        self.conn.commit()
        return True

    def search_question(self, subject_id, query_text):
        """
        Foydalanuvchi yozgan so'zlarni parchalab, kengaytirilgan qidiruv qiladi.
        Apostrof farqlari va ortiqcha belgilarni hisobga olmaydi.
        """
        cursor = self.conn.cursor()
        
        # 1. Matnni kichik harfga o'tkazish va belgilarni standartlashtirish
        def clean_text(text):
            if not text: return ""
            text = text.lower()
            # Har xil ko'rinishdagi tutuq belgilari va apostroflarni bir xil (') holatga keltiramiz
            text = text.replace("‘", "'").replace("’", "'").replace("`", "'").replace("ʻ", "'")
            # Ortiqcha so'roq, ikki nuqta va nuqtalarni tozalaymiz
            for char in ["?", ":", "!", ".", ",", "-", "–"]:
                text = text.replace(char, " ")
            return " ".join(text.split())

        cleaned_query = clean_text(query_text)
        
        # Agar foydalanuvchi juda qisqa narsa yozgan bo'lsa
        if len(cleaned_query) < 3:
            return None

        # Bazadagi barcha savollarni olib, dastur darajasida solishtiramiz (Eng ishonchli yo'l)
        cursor.execute("SELECT question, answer FROM questions WHERE subject_id = ?", (subject_id,))
        rows = cursor.fetchall()

        # Birinchi bosqich: To'liq o'xshashlik bo'yicha qidiruv (Apostroflardan tozalangan holda)
        for question, answer in rows:
            if clean_text(question) in cleaned_query or cleaned_query in clean_text(question):
                return (answer,)

        # Ikkinchi bosqich: Agar matn uzun bo'lsa, eng muhim kalit so'zlar bo'yicha qidiruv
        words = [w for w in cleaned_query.split() if len(w) > 3] # 3 tadan uzun so'zlarni ajratamiz
        if words:
            for question, answer in rows:
                cleaned_q = clean_text(question)
                # Agar foydalanuvchi yozgan muhim so'zlarning kamida 70% foizi savolda qatnashgan bo'lsa
                match_count = sum(1 for word in words if word in cleaned_q)
                if match_count / len(words) >= 0.7:
                    return (answer,)

        return None
    def close(self):
        """Ma'lumotlar bazasi ulanishini yopish"""
        self.conn.close()