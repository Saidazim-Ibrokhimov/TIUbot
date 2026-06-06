import os
import asyncio
from aiogram import Bot, Dispatcher, F, html
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from dotenv import load_dotenv
from aiogram.client.default import DefaultBotProperties
from aiohttp import web 
from aiogram.types import FSInputFile
import datetime

# Ma'lumotlar bazasi klassini import qilish
from database import Database

# Tugmalar modullarini import qilish
import reply as kb_reply
import inline as kb_inline

class KeyboardsAdapter:
    """Kod ichidagi kb. bilan boshlangan eski chaqiriqlarni avtomat moslovchi klass"""
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

bot = Bot(token=BOT_TOKEN,
          default=DefaultBotProperties(parse_mode="HTML"))
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

    port = int(os.environ.get("PORT", 8080))

    site = web.TCPSite(
        runner,
        host="0.0.0.0",
        port=port
    )

    await site.start()
    print(f"Web server started on port {port}")

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
    """Foydalanuvchi yoki admin holat ichida turganda tasodifan asosiy menyu tugmalarini bossa,
    holatni darhol tozalaydi va tegishli menyuga yo'naltiradi."""
    if not message.text:
        return False
        
    msg_text = message.text.strip()
    
    if "Fan tanlash" in msg_text or msg_text.startswith("📚"):
        await state.clear()
        if not db.get_subjects():
            await message.answer("Hozircha bazada hech qanday fan yo'q.")
        else:
            await message.answer("Savol bermoqchi bo'lgan fanni tanlang:", reply_markup=kb.subjects_keyboard(purpose="user"))
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
    db.add_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
    
    await message.answer(
        f"Salom, {html.bold(message.from_user.full_name)}!\nSavol-javob botiga xush kelibsiz.\n Kerakli fanni tanlang, aniq va tekshirilgan javoblarni oling. \n\n {html.bold("G'oya muallifi va producer")} @Saidazim_Ibroximov",
        reply_markup=kb.main_menu_keyboard(is_admin)
    )

@dp.message(F.text.contains("Fan tanlash"))
async def show_subjects(message: Message, state: FSMContext):
    await state.clear()
    if not db.get_subjects():
        await message.answer("Hozircha bazada hech qanday fan yo'q.")
        return
    await message.answer("Savol bermoqchi bo'lgan fanni tanlang:", reply_markup=kb.subjects_keyboard(purpose="user"))
   
@dp.callback_query(F.data.startswith("sub_"))
async def subject_selected(call: CallbackQuery, state: FSMContext):
    subject_id = int(call.data.split("_")[1])
    await state.update_data(chosen_subject=subject_id)
    await state.set_state(UserStates.asking_question)
    
    await call.message.edit_text("Ushbu fan bo'yicha savolingizni matn ko'rinishida kiriting:")
    await call.answer()

@dp.message(UserStates.asking_question)
async def process_question(message: Message, state: FSMContext):
    if await check_menu_buttons(message, state):
        return

    data = await state.get_data()
    subject_id = data.get("chosen_subject")
    query = message.text

    # Bazadan qidirish
    result = db.search_question(subject_id, query)

    if result:
        await message.answer(f"🔎 {html.bold('Topilgan javob:')}\n\n{result[0]}")
    else:
        await message.answer("⚠️ Afsuski, ushbu savolga bazadan javob topilmadi. Boshqa so'zlar bilan qaytadan urinib ko'ring.")


# --- ADMIN PANEL HANDLERLARI ---

@dp.message(F.text.contains("Admin Panel"))
async def admin_panel(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.clear()
    await message.answer("Admin boshqaruv paneli:", reply_markup=kb.admin_keyboard())

@dp.callback_query(F.data == "export_stats")
async def export_stats_to_txt(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    
    users = db.get_all_users_info()
    total, active, blocked = db.get_stats_summary()
    
    # Fayl nomini va tarkibini tayyorlash
    file_name = "bot_statistika.txt"
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(f"📊 BOT STATISTIKASI - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("------------------------------------\n")
        f.write(f"Jami foydalanuvchilar: {total}\n")
        f.write(f"Faol foydalanuvchilar: {active}\n")
        f.write(f"Tark etganlar (bloklaganlar): {blocked}\n\n")
        f.write("ID | Ismi | Qo'shilgan sana | Status\n")
        for u in users:
            f.write(f"{u[0]} | {u[1]} | {u[2]} | {u[3]}\n")
            
    # Faylni yuborish
    await call.message.answer_document(FSInputFile(file_name), caption="Mana, barcha foydalanuvchilar statistikasi.")
    await call.answer()
    
    # Faylni o'chirish (serverni tozalash uchun)
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
    
    if db.add_subject(subject_name):
        await message.answer(f"✅ Yangi fan muvaffaqiyatli qo'shildi: {subject_name}", reply_markup=kb.main_menu_keyboard(True))
    else:
        await message.answer("❌ Bu fan bazada allaqachon mavjud!")
    await state.clear()

@dp.callback_query(F.data == "add_question")
async def start_add_question(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    if not db.get_subjects():
        await call.message.answer("Avval fan qo'shishingiz kerak!")
        await call.answer()
        return
        
    await state.set_state(AdminStates.choosing_subject_for_q)
    await call.message.edit_text("Qaysi fanga savol qo'shmoqchisiz? Tanlang:", reply_markup=kb.subjects_keyboard(purpose="admin"))
    await call.answer()

@dp.callback_query(F.data.startswith("asub_"))
async def admin_subject_selected(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    subject_id = int(call.data.split("_")[1])
    await state.update_data(admin_sub_id=subject_id)
    
    await state.set_state(AdminStates.adding_question_text)
    await call.message.edit_text("Savol matnini kiriting yoki blokli `.txt` faylini yuboring:")
    await call.answer()


# --- MUKAMMAL VA CHIDAMLI FAYL PARSERI (YANGILANGAN) ---
@dp.message(AdminStates.adding_question_text)
async def process_admin_q_text(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if await check_menu_buttons(message, state): return 

    data = await state.get_data()
    subject_id = data.get("admin_sub_id")

    # A VARIANT: AGAR SIZ `.TXT` FAYL TASHAGAN BO'LSANGIZ
    if message.document:
        document = message.document
        
        if not document.file_name.endswith('.txt'):
            await message.answer("❌ Iltimos, faqat `.txt` formatidagi matnli fayl yuboring!")
            return

        status_msg = await message.answer("🔄 Blokli fayl aniqlandi. Tahlil qilinmoqda...")

        file_info = await bot.get_file(document.file_id)
        file_bytes = await bot.download_file(file_info.file_path)
        
        # Windows va Linux formatlarini moslashtirish (\r\n ni tozalash)
        raw_text = file_bytes.read().decode('utf-8')
        normalized_text = raw_text.replace('\r\n', '\n').replace('\r', '\n')
        lines = normalized_text.split('\n')
        
        added_count = 0
        skipped_count = 0

        current_question = ""
        current_answer = []

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue  # Bo'sh qatorlarni tashlab ketamiz

            # Yangi Savol bloki boshlanishi
            if line_str.upper().startswith("S:"):
                # Agarda undan oldin to'liq savol va javob yig'ilgan bo'lsa saqlab olamiz
                if current_question and current_answer:
                    ans_text = "\n".join(current_answer).strip()
                    if db.check_and_add_question(subject_id, current_question, ans_text):
                        added_count += 1
                    else:
                        skipped_count += 1
                    current_answer = []
                
                current_question = line_str[2:].strip()
                
            # Javob bloki boshlanishi
            elif line_str.upper().startswith("J:"):
                current_answer.append(line_str[2:].strip())
                
            # Agar S: yoki J: bo'lmasa, demak bu javobning davomi yoki modda raqami (masalan 733-modda)
            else:
                if current_answer: 
                    # Javob matni allaqachon boshlangan bo'lsa, davomiga qo'shamiz
                    current_answer.append(line_str)
                elif current_question:
                    # Agar hali J: boshlanmagan bo'lsa, demak bu savolning pastki qatori
                    current_question += "\n" + line_str

        # Eng oxirgi savol blokini ham bazaga yozib qo'yish
        if current_question and current_answer:
            ans_text = "\n".join(current_answer).strip()
            if db.check_and_add_question(subject_id, current_question, ans_text):
                added_count += 1
            else:
                skipped_count += 1

        await status_msg.delete() # Kutish xabarini o'chiramiz
        await message.answer(
            f"📋 <b>Faylni qayta ishlash yakunlandi:</b>\n\n"
            f"✅ {added_count} ta yangi savol-javob muvaffaqiyatli bazaga qo'shildi.\n"
            f"⚠️ {skipped_count} ta takroriy savol o'tkazib yuborildi.",
            reply_markup=kb.main_menu_keyboard(True)
        )
        await state.clear()
        return

    # B VARIANT: SIZ ODDIY MATN KO'RINISHIDA BITTALIK SAVOL YOZGAN BO'LSANGIZ
    if message.text:
        await state.update_data(admin_q_text=message.text)
        await state.set_state(AdminStates.adding_answer_text)
        await message.answer("Endi ushbu savolning javobini kiriting:")
        return

    await message.answer("❌ Iltimos, savol matnini kiriting yoki `.txt` formatidagi faylni yuboring!")


@dp.message(AdminStates.adding_answer_text)
async def process_admin_a_text(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if await check_menu_buttons(message, state): return 

    data = await state.get_data()
    sub_id = data.get("admin_sub_id")
    question = data.get("admin_q_text")
    answer = message.text

    db.add_question(sub_id, question, answer)
    await message.answer("✅ Savol va javob muvaffaqiyatli bazaga yuklandi!", reply_markup=kb.main_menu_keyboard(True))
    await state.clear()


# --- RASSILKA (XABAR YUBORISH) ---

@dp.callback_query(F.data == "broadcast")
async def start_broadcast(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await state.set_state(AdminStates.broadcasting)
    await call.message.edit_text("Foydalanuvchilarga yuboriladigan xabar matnini kiriting:")
    await call.answer()

@dp.message(AdminStates.broadcasting)
async def do_broadcast(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if await check_menu_buttons(message, state): return 

    users = db.get_all_users()
    count = 0
    
    await message.answer("Xabar yuborish boshlandi...")
    for user in users:
        try:
            await message.copy_to(chat_id=user[0])
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await message.answer(f"📢 Xabar {count} ta faol foydalanuvchiga muvaffaqiyatli yetkazildi.")
    await state.clear()


async def main():
    # Render portni band qilish
    await start_web_server()

    # Telegram bot
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())