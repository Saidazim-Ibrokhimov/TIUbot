import os
import asyncio
from aiogram import Bot, Dispatcher, F, html
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, FSInputFile
from dotenv import load_dotenv
from aiogram.client.default import DefaultBotProperties
from aiohttp import web 

from database import Database
import reply as kb_reply
import inline as kb_inline

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
db = Database(DATABASE_URL)

# --- Keyboard Adapter ---
class KeyboardsAdapter:
    def main_menu_keyboard(self, is_admin=False): return kb_reply.main_menu_keyboard(is_admin)
    def admin_keyboard(self): return kb_inline.admin_keyboard()
    async def subjects_keyboard(self, purpose="user"): return await kb_inline.subjects_keyboard(purpose)

kb = KeyboardsAdapter()

# --- Web Server ---
async def handle(request): return web.Response(text="Bot is running!")
async def start_web_server():
    app = web.Application()
    app.add_routes([web.get('/', handle)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
    await site.start()

# --- States ---
class UserStates(StatesGroup): asking_question = State()
class AdminStates(StatesGroup):
    adding_subject = State()
    choosing_subject_for_q = State()
    adding_question_text = State()
    adding_answer_text = State()
    broadcasting = State()

# --- Helpers ---
async def check_menu_buttons(message: Message, state: FSMContext) -> bool:
    if not message.text: return False
    msg = message.text.strip()
    if "Fan tanlash" in msg or msg.startswith("📚"):
        await state.clear()
        subjects = await db.get_subjects()
        if not subjects: await message.answer("Hozircha fan yo'q.")
        else: await message.answer("Fanni tanlang:", reply_markup=await kb.subjects_keyboard("user"))
        return True
    elif "Admin Panel" in msg or msg.startswith("⚙️"):
        if message.from_user.id == ADMIN_ID:
            await state.clear()
            await message.answer("Admin:", reply_markup=kb.admin_keyboard())
        return True
    return False

# --- Handlers ---
@dp.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext):
    await db.add_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
    await message.answer("Xush kelibsiz!", reply_markup=kb.main_menu_keyboard(message.from_user.id == ADMIN_ID))

@dp.message(F.text.contains("Fan tanlash"))
async def show_subjects(message: Message, state: FSMContext):
    await message.answer("Tanlang:", reply_markup=await kb.subjects_keyboard("user"))

@dp.callback_query(F.data.startswith("sub_"))
async def subject_selected(call: CallbackQuery, state: FSMContext):
    await state.update_data(chosen_subject=int(call.data.split("_")[1]))
    await state.set_state(UserStates.asking_question)
    await call.message.edit_text("Savolni yozing:")

@dp.message(UserStates.asking_question)
async def process_question(message: Message, state: FSMContext):
    if await check_menu_buttons(message, state): return
    data = await state.get_data()
    res = await db.search_question(data.get("chosen_subject"), message.text)
    await message.answer(f"Javob: {res[0]}" if res else "Topilmadi.")

# Admin Panel & Broadcast
@dp.callback_query(F.data == "broadcast")
async def start_broadcast(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.broadcasting)
    await call.message.edit_text("Xabarni yuboring:")

@dp.message(AdminStates.broadcasting)
async def do_broadcast(message: Message, state: FSMContext):
    users = await db.get_all_users()
    for u in users:
        try: await bot.send_message(u['user_id'], message.text)
        except: continue
    await message.answer("Yuborildi!")
    await state.clear()

@dp.callback_query(F.data == "admin_stats")
async def stats(call: CallbackQuery):
    u = await db.get_all_users_info()
    total, active, _ = await db.get_stats_summary()
    await call.message.answer(f"Jami: {total}\nFaol: {active}")

@dp.callback_query(F.data == "add_question")
async def add_q(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.choosing_subject_for_q)
    await call.message.edit_text("Qaysi fanga?", reply_markup=await kb.subjects_keyboard("admin"))

@dp.callback_query(F.data.startswith("asub_"))
async def admin_sub_select(call: CallbackQuery, state: FSMContext):
    await state.update_data(admin_sub_id=int(call.data.split("_")[1]))
    await state.set_state(AdminStates.adding_question_text)
    await call.message.edit_text("Matn yuboring yoki .txt fayl:")

@dp.message(AdminStates.adding_question_text)
async def process_q_text(message: Message, state: FSMContext):
    data = await state.get_data()
    sub_id = data.get("admin_sub_id")
    if message.document:
        status = await message.answer("Fayl tahlil qilinmoqda...")
        file = await bot.download_file((await bot.get_file(message.document.file_id)).file_path)
        lines = file.read().decode('utf-8').split('\n')
        curr_q, curr_a, added = "", [], 0
        for line in lines:
            line = line.strip()
            if line.upper().startswith("S:"):
                if curr_q: 
                    await db.add_question(sub_id, curr_q, "\n".join(curr_a))
                    added += 1
                curr_q = line[2:].strip(); curr_a = []
            elif line.upper().startswith("J:"): curr_a.append(line[2:].strip())
            elif curr_a: curr_a.append(line)
        await status.delete()
        await message.answer(f"{added} ta savol qo'shildi.")
        await state.clear()
    elif message.text:
        await state.update_data(admin_q_text=message.text)
        await state.set_state(AdminStates.adding_answer_text)
        await message.answer("Javobni kiriting:")

@dp.message(AdminStates.adding_answer_text)
async def process_a_text(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.add_question(data.get("admin_sub_id"), data.get("admin_q_text"), message.text)
    await message.answer("Qo'shildi!")
    await state.clear()

async def main():
    await db.connect()
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())