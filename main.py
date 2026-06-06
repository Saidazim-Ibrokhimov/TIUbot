import os
import asyncio
from aiogram import Bot, Dispatcher, F, html
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from dotenv import load_dotenv
from aiogram.client.default import DefaultBotProperties
from aiohttp import web  # Render uchun kerak

# Ma'lumotlar bazasi klassi
from database import Database
import reply as kb_reply
import inline as kb_inline

# Sozlamalarni yuklash
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
db = Database("data.db")

# --- RENDER PORT BINDING ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.add_routes([web.get('/', handle)])
    runner = web.AppRunner(app)
    await runner.setup()
    # Render avtomatik PORT o'zgaruvchisini taqdim etadi
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")

# --- ESKI KODINGIZ (Qisqartirilgan, o'zgarishsiz) ---
class KeyboardsAdapter:
    def main_menu_keyboard(self, is_admin=False): return kb_reply.main_menu_keyboard(is_admin)
    def admin_keyboard(self): return kb_inline.admin_keyboard()
    def subjects_keyboard(self, purpose="user"): return kb_inline.subjects_keyboard(purpose)

kb = KeyboardsAdapter()

class UserStates(StatesGroup):
    asking_question = State()

class AdminStates(StatesGroup):
    adding_subject = State()
    adding_question_text = State()
    adding_answer_text = State()
    broadcasting = State()

async def check_menu_buttons(message: Message, state: FSMContext) -> bool:
    if not message.text: return False
    msg_text = message.text.strip()
    if "Fan tanlash" in msg_text or msg_text.startswith("📚"):
        await state.clear()
        if not db.get_subjects(): await message.answer("Bazada fan yo'q.")
        else: await message.answer("Fanni tanlang:", reply_markup=kb.subjects_keyboard(purpose="user"))
        return True
    return False

# --- HANDLERLAR (Sizdagi mantiq o'zgarishsiz qoldirildi) ---
@dp.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    is_admin = message.from_user.id == ADMIN_ID
    db.add_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
    await message.answer("Salom! Botga xush kelibsiz.", reply_markup=kb.main_menu_keyboard(is_admin))

# (Bu yerga qolgan barcha handlerlaringizni qo'yib chiqing...)

# --- ASOSIY ISHGA TUSHIRISH ---
async def main():
    # 1. Portni band qilish uchun web-serverni ishga tushirish
    await start_web_server()
    # 2. Botni ishga tushirish
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())