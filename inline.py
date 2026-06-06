from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import Database
import os

# DATABASE_URL ni main.py dan olishimiz kerak, 
# shuning uchun bu yerda qaysi bazadan foydalanishni to'g'ri ko'rsatamiz
db = Database(os.getenv("DATABASE_URL"))

def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="➕ Yangi Fan Qo'shish", callback_data="add_subject")],
        [InlineKeyboardButton(text="➕ Yangi Savol Qo'shish", callback_data="add_question")],
        [InlineKeyboardButton(text="📢 Xabar Yuborish (Rassilka)", callback_data="broadcast")]
    ])

# Bu funksiya ENDI async
async def subjects_keyboard(purpose="user"):
    subjects = await db.get_subjects()
    keyboard = []
    for sub in subjects: # row dan sub_id va name olish
        sub_id = sub['id']
        name = sub['name']
        cb_data = f"sub_{sub_id}" if purpose == "user" else f"asub_{sub_id}"
        keyboard.append([InlineKeyboardButton(text=name, callback_data=cb_data)])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)