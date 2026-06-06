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
import datetime

# Ma'lumotlar bazasi klassini import qilish
from database import Database

# Tugmalar modullarini import qilish
import reply as kb_reply
import inline as kb_inline

class KeyboardsAdapter:
    def main_menu_keyboard(self, is_admin=False):
        return kb_reply.main_menu_keyboard(is_admin)
        
    def admin_keyboard(self):
        return kb_inline.admin_keyboard()
        
    def subjects_keyboard(self, purpose="user"):
        return kb_inline.subjects_keyboard(purpose)

kb = KeyboardsAdapter()

# Sozlamalarni yuklash
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
db = Database(DATABASE_URL) # PostgreSQL URL bilan

# --- RENDER PORT BINDING ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.add_routes([web.get('/', handle)])
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()

# FSM (Holatlar)
class UserStates(StatesGroup):
    choosing_subject = State()
    asking_question = State()

class AdminStates(StatesGroup):
    adding_subject = State()
    choosing_subject_for_q = State()
    adding_question_text = State()
    adding_answer_text = State()
    broadcasting = State()

# --- GLOBAL MENYU TUGMALARINI TEKSHIRUVCHI AQLLI FUNKSIYA ---
async def check_menu_buttons(message: Message, state: FSMContext) -> bool:
    if not message.text: return False
    msg_text = message.text.strip()
    
    if "Fan tanlash" in msg_text or msg_text.startswith("📚"):
        await state.clear()
        subjects = await db.get_subjects() # await qo'shildi
        if not subjects:
            await message.answer("Hozircha bazada hech qanday fan yo'q.")
        else:
            await message.answer("Savol bermoqchi bo'lgan fanni tanlang:", reply_markup=await kb.subjects_keyboard(purpose="user"))
        return True
        
    elif "Admin Panel" in msg_text or msg_text.startswith("⚙️"):
        if message.from_user.id == ADMIN_ID:
            await state.clear()
            await message.answer("Admin boshqaruv paneli:", reply_markup=kb.admin_keyboard())
        return True
    return False

# --- FOYDALANUVCHI HANDLERLARI ---
@dp.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    is_admin = message.from_user.id == ADMIN_ID
    await db.add_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
    
    await message.answer(
        f"Assalomu alaykum, {html.bold(message.from_user.full_name)}!\n\nKerakli fanni tanlang, aniq va tekshirilgan javoblarni oling. \n\n {html.bold('Creator:')} @Saidazim_Ibroximov",
        reply_markup=kb.main_menu_keyboard(is_admin)
    )

@dp.message(F.text.contains("Fan tanlash"))
async def show_subjects(message: Message, state: FSMContext):
    await state.clear()
    if not await db.get_subjects():
        await message.answer("Hozircha bazada hech qanday fan yo'q.")
        return
    await message.answer("Savol bermoqchi bo'lgan fanni tanlang:", reply_markup=await kb.subjects_keyboard(purpose="user"))
   
@dp.callback_query(F.data.startswith("sub_"))
async def subject_selected(call: CallbackQuery, state: FSMContext):
    subject_id = int(call.data.split("_")[1])
    await state.update_data(chosen_subject=subject_id)
    await state.set_state(UserStates.asking_question)
    await call.message.edit_text("Ushbu fan bo'yicha savolingizni matn ko'rinishida kiriting:")
    await call.answer()

@dp.message(UserStates.asking_question)
async def process_question(message: Message, state: FSMContext):
    if await check_menu_buttons(message, state): return
    data = await state.get_data()
    subject_id = data.get("chosen_subject")
    result = await db.search_question(subject_id, message.text)
    if result:
        await message.answer(f"🔎 {html.bold('Topilgan javob:')}\n\n{result[0]}")
    else:
        await message.answer("⚠️ Afsuski, ushbu savolga bazadan javob topilmadi.")

# --- ADMIN PANEL HANDLERLARI ---
@dp.message(F.text.contains("Admin Panel"))
async def admin_panel(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    await message.answer("Admin boshqaruv paneli:", reply_markup=kb.admin_keyboard())

@dp.callback_query(F.data == "admin_stats")
async def export_stats_to_txt(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    users = await db.get_all_users_info()
    total, active, blocked = await db.get_stats_summary()
    
    file_name = "bot_statistika.txt"
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(f"📊 BOT STATISTIKASI - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("------------------------------------\n")
        f.write(f"Jami: {total}\nFaol: {active}\nTark etganlar: {blocked}\n\n")
        for u in users:
            f.write(f"{u[0]} | {u[1]} | {u[2]} | {u[3]}\n")
            
    await call.message.answer_document(FSInputFile(file_name), caption="Statistika.")
    await call.answer()
    os.remove(file_name)

@dp.callback_query(F.data == "add_subject")
async def start_add_subject(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await state.set_state(AdminStates.adding_subject)
    await call.message.edit_text("Yangi fanning nomini kiriting:")
    await call.answer()

@dp.message(AdminStates.adding_subject)
async def save_subject(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if await check_menu_buttons(message, state): return 
    subject_name = message.text.strip()
    if await db.add_subject(subject_name):
        await message.answer(f"✅ Yangi fan qo'shildi: {subject_name}", reply_markup=kb.main_menu_keyboard(True))
    else:
        await message.answer("❌ Bu fan allaqachon mavjud!")
    await state.clear()

@dp.callback_query(F.data == "add_question")
async def start_add_question(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    if not await db.get_subjects():
        await call.message.answer("Avval fan qo'shishingiz kerak!")
        await call.answer()
        return
    await state.set_state(AdminStates.choosing_subject_for_q)
    await call.message.edit_text("Qaysi fanga savol qo'shmoqchisiz?", reply_markup=await kb.subjects_keyboard(purpose="admin"))
    await call.answer()

@dp.callback_query(F.data.startswith("asub_"))
async def admin_subject_selected(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    subject_id = int(call.data.split("_")[1])
    await state.update_data(admin_sub_id=subject_id)
    await state.set_state(AdminStates.adding_question_text)
    await call.message.edit_text("Savol matnini kiriting yoki .txt fayl yuboring:")
    await call.answer()

@dp.message(AdminStates.adding_question_text)
async def process_admin_q_text(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if await check_menu_buttons(message, state): return 
    data = await state.get_data()
    subject_id = data.get("admin_sub_id")

    if message.document:
        file_info = await bot.get_file(message.document.file_id)
        file_bytes = await bot.download_file(file_info.file_path)
        raw_text = file_bytes.read().decode('utf-8')
        lines = raw_text.replace('\r\n', '\n').split('\n')
        
        added, skipped = 0, 0
        curr_q, curr_a = "", []
        for line in lines:
            line_str = line.strip()
            if not line_str: continue
            if line_str.upper().startswith("S:"):
                if curr_q: 
                    if await db.check_and_add_question(subject_id, curr_q, "\n".join(curr_a)): added += 1
                    else: skipped += 1
                curr_q = line_str[2:].strip(); curr_a = []
            elif line_str.upper().startswith("J:"): curr_a.append(line_str[2:].strip())
            elif curr_a: curr_a.append(line_str)
            elif curr_q: curr_q += "\n" + line_str
        
        if curr_q: 
            if await db.check_and_add_question(subject_id, curr_q, "\n".join(curr_a)): added += 1
            else: skipped += 1
        await message.answer(f"✅ {added} ta savol qo'shildi, {skipped} ta o'tkazib yuborildi.")
        await state.clear()
        return

    elif message.text:
        await state.update_data(admin_q_text=message.text)
        await state.set_state(AdminStates.adding_answer_text)
        await message.answer("Javobni kiriting:")

@dp.message(AdminStates.adding_answer_text)
async def process_admin_a_text(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if await check_menu_buttons(message, state): return 
    data = await state.get_data()
    await db.add_question(data.get("admin_sub_id"), data.get("admin_q_text"), message.text)
    await message.answer("✅ Muvaffaqiyatli yuklandi!", reply_markup=kb.main_menu_keyboard(True))
    await state.clear()

@dp.callback_query(F.data == "broadcast")
async def start_broadcast(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await state.set_state(AdminStates.broadcasting)
    await call.message.edit_text("Xabar matnini kiriting:")
    await call.answer()

@dp.message(AdminStates.broadcasting)
async def do_broadcast(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if await check_menu_buttons(message, state): return 
    users = await db.get_all_users()
    count = 0
    for user in users:
        try:
            await message.copy_to(chat_id=user[0])
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    await message.answer(f"📢 Xabar {count} kishiga yuborildi.")
    await state.clear()

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())