from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import Database

db = Database("data.db")

def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="➕ Yangi Fan Qo'shish", callback_data="add_subject")],
        [InlineKeyboardButton(text="➕ Yangi Savol Qo'shish", callback_data="add_question")],
        [InlineKeyboardButton(text="📢 Xabar Yuborish (Rassilka)", callback_data="broadcast")]
    ])

def subjects_keyboard(purpose="user"):
    subjects = db.get_subjects()
    keyboard = []
    for sub_id, name in subjects:
        cb_data = f"sub_{sub_id}" if purpose == "user" else f"asub_{sub_id}"
        keyboard.append([InlineKeyboardButton(text=name, callback_data=cb_data)])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)