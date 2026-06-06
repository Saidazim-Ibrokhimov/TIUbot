from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu_keyboard(is_admin=False):
    buttons = [[KeyboardButton(text="📚 Fan tanlash")]]
    if is_admin:
        buttons.append([KeyboardButton(text="⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)