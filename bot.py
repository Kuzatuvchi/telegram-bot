import logging
import os
import re
from dotenv import load_dotenv
load_dotenv()
from groq import Groq
from datetime import datetime, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ===================== SOZLAMALAR =====================


import os

BOT_TOKEN    = os.environ.get("BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
ADMIN_ID     = int(os.environ.get("ADMIN_ID"))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===================== GLOBAL MA'LUMOTLAR =====================
member_count = 0
joined_count = 0
left_count = 0
joined_users = []
left_users = []

leave_reasons = {
    "safar_yoq": {"label": "Safarga bormayman", "count": 0},
    "narx":      {"label": "Narx munosib emas", "count": 0},
    "boshqa":    {"label": "Boshqa guruhga o'tdim", "count": 0},
    "vaqt":      {"label": "Hozircha vaqtim yo'q", "count": 0},
    "other":     {"label": "Boshqa sabab", "count": 0},
}
pending_leave = {}

company_info = {
    "info": """Bu guruh umra safari firmasi ellikboshiga tegishli.
Ellikboshi guruh a'zolarini umra safariga tayyorlaydi va yo'llovchi bo'ladi.
Guruh a'zolari maxfiy saqlanadi.
Ellikboshi bilan bog'lanish: @Sarvari_olam_ummati (yoki +998903630179)"""

}

your_style_examples = []

daily_knowledge = [
    {
        "title": "🕌 Umra niyati",
        "text": "Umra qilmoqchi bo'lgan kishi ihromga kirishdan oldin niyat qilishi kerak. "
                "Niyat qalbda bo'lishi kifoya, lekin tilga ham olsa — afzal. "
                "«Labbayka Allohumma umratan» deb niyat qilinadi."
    },
    {
        "title": "✈️ Safar odobi",
        "text": "Safarga chiqqanda 2 rakat safar namozi o'qish sunnat. "
                "Uydan chiqishda: «Bismillah, tavakkaltu alalloh» deyiladi. "
                "Safar duosi o'qiladi: «Allohumma inni as'aluka fi safarina haazal birra vattaqwa...»"
    },
    {
        "title": "🤍 Ihrom haqida",
        "text": "Erkaklar ihromda tikuvli kiyim kiymaydi — 2 dona oq mato. "
                "Ayollar oddiy hijobda bo'lishi mumkin, yuz va qo'l ochiq qoladi. "
                "Ihromda janjal, yomon so'z, ov qilish taqiqlanadi."
    },
    {
        "title": "🏃 Tavof haqida",
        "text": "Tavof — Ka'ba atrofini 7 marta aylanish. "
                "Hajarul-Asvaddan boshlanadi, soat miliga teskari yo'nalishda. "
                "Har aylanishda Hajarul-Asvadni o'pish yoki qo'l siltash sunnat."
    },
    {
        "title": "🚶 Sa'y haqida",
        "text": "Sa'y — Safa va Marva tepaliklari orasida 7 marta yurish. "
                "Bu Hazrati Hojарning suv izlab yugurganini eslatadi. "
                "Safadan boshlanadi, Marvada tugaydi."
    },
    {
        "title": "💧 Zamzam suvi",
        "text": "Zamzam suvi dunyodagi eng muborak suv hisoblanadi. "
                "Ichishdan oldin qiblaga yuzlanib, bismillah deyiladi va niyat qilinadi. "
                "«Allohumma inni as'aluka ilman nafi'an...» duosi o'qiladi."
    },
    {
        "title": "🤲 Umra duolari",
        "text": "Tavofda maxsus dua yo'q — istalgan dua o'qiladi. "
                "Rukni Yamaniydан Hajarul-Asvadga: «Rabbana atina fid-dunya hasanatan...» "
                "Ko'p istig'for va salavot aytish tavsiya etiladi."
    },
]

knowledge_index = 0

# ===================== YORDAMCHI =====================
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

# ===================== LINK BLOKLASH =====================
URL_PATTERN = re.compile(r'(https?://|www\.|t\.me/|@\w[\w.]+\.\w+)', re.IGNORECASE)

async def delete_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return
    if is_admin(message.from_user.id):
        return
    if URL_PATTERN.search(message.text):
        try:
            await message.delete()
            warning = await context.bot.send_message(
                chat_id=message.chat_id,
                text=f"⚠️ {message.from_user.first_name}, guruhga link tashlash taqiqlangan!"
            )
            context.job_queue.run_once(
                delete_temp_message, 10,
                data={"chat_id": message.chat_id, "message_id": warning.message_id}
            )
        except Exception as e:
            logger.error(f"Link o'chirishda xato: {e}")

async def delete_temp_message(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    try:
        await context.bot.delete_message(data["chat_id"], data["message_id"])
    except:
        pass

# ===================== A'ZO HISOBLAGICH =====================
async def track_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global joined_count, left_count, member_count
    result = update.chat_member
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    user = result.new_chat_member.user
    user_name = user.full_name
    username = f" (@{user.username})" if user.username else ""

    if old_status in ["left", "kicked"] and new_status == "member":
        joined_count += 1
        member_count += 1
        joined_users.append(f"{user_name}{username}")
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"➕ *Yangi a'zo qo'shildi*\n\n👤 {user_name}{username}\n👥 Jami: {member_count} kishi",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Admin xabarda xato: {e}")

    elif old_status == "member" and new_status in ["left", "kicked"]:
        left_count += 1
        member_count = max(0, member_count - 1)
        left_users.append(f"{user_name}{username}")
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"➖ *A'zo chiqib ketdi*\n\n👤 {user_name}{username}\n👥 Qoldi: {member_count} kishi",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Admin xabarda xato: {e}")

        pending_leave[user.id] = {"name": user_name, "time": datetime.now()}
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✈️ Safarga bormayman", callback_data="leave_safar_yoq")],
            [InlineKeyboardButton("💰 Narx munosib emas", callback_data="leave_narx")],
            [InlineKeyboardButton("👥 Boshqa guruhga o'tdim", callback_data="leave_boshqa")],
            [InlineKeyboardButton("⏳ Hozircha vaqtim yo'q", callback_data="leave_vaqt")],
            [InlineKeyboardButton("📝 Boshqa sabab", callback_data="leave_other")],
        ])
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text=f"Assalomu alaykum, {user.first_name}! 🤝\n\n"
                     f"Guruhdan chiqqaningizni ko'rdik. "
                     f"Bizni tark etishingizga sabab nima edi?\n\n"
                     f"Javobingiz bizga yaxshilanish uchun juda muhim 🙏",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.info(f"Chiqgan odamga xabar yuborib bo'lmadi ({user_name}): {e}")

# ===================== CHIQISH SABABI =====================
async def leave_reason_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data
    if not data.startswith("leave_"):
        return
    reason_key = data.replace("leave_", "")
    if reason_key in leave_reasons:
        leave_reasons[reason_key]["count"] += 1
        reason_label = leave_reasons[reason_key]["label"]
    else:
        reason_label = "Noma'lum"
    await query.edit_message_text(
        f"Rahmat javobingiz uchun! 🙏\n\n"
        f"Siz tanlagan sabab: *{reason_label}*\n\n"
        f"Agar qaytib kelmoqchi bo'lsangiz — doim guruhimiz siz uchun ochiq! 🤝\n"
        f"@Madinaga_oshiq_qalblar  guruhida qayta ko'rishamiz degan umiddamiz\n"
        f"Alloh safarlaringizni oson qilsin! 🕌",
        parse_mode="Markdown"
    )
    user_name = user.full_name
    username = f" (@{user.username})" if user.username else ""
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📋 *Chiqish sababi keldi*\n\n👤 {user_name}{username}\n❓ Sabab: *{reason_label}*",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Sabab adminga yuborishda xato: {e}")

async def leave_stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    total = sum(v["count"] for v in leave_reasons.values())
    lines = ["📊 *Chiqish Sabablari Statistikasi*\n"]
    for val in leave_reasons.values():
        count = val["count"]
        label = val["label"]
        if total > 0:
            percent = round(count / total * 100)
            bar = "█" * (percent // 10) + "░" * (10 - percent // 10)
            lines.append(f"{label}\n{bar} {count} ta ({percent}%)\n")
        else:
            lines.append(f"{label}: 0 ta\n")
    lines.append(f"\n_Jami javob berdi: {total} kishi_")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ===================== KUNLIK HISOBOT =====================
async def send_daily_report(context: ContextTypes.DEFAULT_TYPE):
    global joined_count, left_count, joined_users, left_users
    joined_list = "\n".join([f"  • {u}" for u in joined_users]) if joined_users else "  — yo'q"
    left_list = "\n".join([f"  • {u}" for u in left_users]) if left_users else "  — yo'q"
    text = (
        f"📊 *Kunlik Hisobot* — {datetime.now().strftime('%d.%m.%Y')}\n\n"
        f"➕ Qo'shildi: *{joined_count}* kishi\n{joined_list}\n\n"
        f"➖ Chiqib ketdi: *{left_count}* kishi\n{left_list}\n\n"
        f"👥 Jami: *{member_count}* kishi\n"
        f"📈 Sof o'sish: *{joined_count - left_count:+d}* kishi"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Hisobot yuborishda xato: {e}")
    joined_count = 0
    left_count = 0
    joined_users.clear()
    left_users.clear()

# ===================== FOYDALI ILM =====================
async def send_daily_knowledge_to_group(context, chat_id):
    global knowledge_index
    knowledge = daily_knowledge[knowledge_index % len(daily_knowledge)]
    knowledge_index += 1
    text = (
        f"📖 *Bugungi Foydali Ilm*\n\n"
        f"{knowledge['title']}\n\n"
        f"{knowledge['text']}\n\n"
        f"_Alloh umralaringizni qabul qilsin!_ 🤲"
    )
    try:
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Foydali ilm yuborishda xato: {e}")

async def daily_knowledge_job(context: ContextTypes.DEFAULT_TYPE):
    group_id = context.bot_data.get("group_id")
    if group_id:
        await send_daily_knowledge_to_group(context, group_id)

# ===================== ADMIN BUYRUQLARI =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "✅ *Bot ishga tushdi!*\n\n"
        "📋 *Admin buyruqlari:*\n"
        "/setinfo — Firma ma'lumotini yangilash\n"
        "/addstyle — Javob uslubi o'rgatish\n"
        "/clearstyle — Uslublarni tozalash\n"
        "/setgroup — Guruh ID ni belgilash\n"
        "/addilm — Yangi foydali ilm qo'shish\n"
        "/ilm — Hozir foydali ilm yuborish\n"
        "/elon <matn> — Guruhga e'lon yuborish\n"
        "/stats — Statistika\n"
        "/sabablar — Chiqish sabablari\n"
        "/report — Hozir hisobot olish",
        parse_mode="Markdown"
    )

async def set_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if context.args:
        try:
            group_id = int(context.args[0])
            context.bot_data["group_id"] = group_id
            await update.message.reply_text(f"✅ Guruh ID saqlandi: `{group_id}`", parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("❌ Noto'g'ri ID.")
    else:
        current = context.bot_data.get("group_id", "Belgilanmagan")
        await update.message.reply_text(f"📌 Joriy guruh ID: `{current}`", parse_mode="Markdown")

async def set_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if context.args:
        company_info["info"] = " ".join(context.args)
        await update.message.reply_text(f"✅ Ma'lumot yangilandi!\n\n📝 {company_info['info']}")
    else:
        await update.message.reply_text("📌 Ishlatish: `/setinfo <matn>`", parse_mode="Markdown")

async def add_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    text = " ".join(context.args)
    if "|" in text:
        parts = text.split("|", 1)
        your_style_examples.append({"question": parts[0].strip(), "answer": parts[1].strip()})
        await update.message.reply_text(f"✅ Namuna qo'shildi! Jami: {len(your_style_examples)} ta")
    else:
        await update.message.reply_text("📌 Ishlatish: `/addstyle savol | javob`", parse_mode="Markdown")

async def clear_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    your_style_examples.clear()
    await update.message.reply_text("✅ Barcha uslub namunalari tozalandi.")

async def add_ilm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    text = " ".join(context.args)
    if "|" in text:
        parts = text.split("|", 1)
        daily_knowledge.append({"title": parts[0].strip(), "text": parts[1].strip()})
        await update.message.reply_text(f"✅ Yangi ilm qo'shildi! Jami: {len(daily_knowledge)} ta")
    else:
        await update.message.reply_text("📌 Ishlatish: `/addilm Sarlavha | Matn`", parse_mode="Markdown")

async def send_ilm_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    group_id = context.bot_data.get("group_id")
    if not group_id:
        await update.message.reply_text("❌ Avval /setgroup bilan guruh ID ni kiriting!")
        return
    await send_daily_knowledge_to_group(context, group_id)
    await update.message.reply_text("✅ Foydali ilm guruhga yuborildi!")

async def elon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    group_id = context.bot_data.get("group_id")
    if not group_id:
        await update.message.reply_text("❌ Avval /setgroup bilan guruh ID ni kiriting!")
        return
    if context.args:
        text = "📢 *E'lon*\n\n" + " ".join(context.args)
        try:
            await context.bot.send_message(chat_id=group_id, text=text, parse_mode="Markdown")
            await update.message.reply_text("✅ E'lon guruhga yuborildi!")
        except Exception as e:
            await update.message.reply_text(f"❌ Xato: {e}")
    else:
        await update.message.reply_text("📌 Ishlatish: `/elon <matn>`", parse_mode="Markdown")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    group_id = context.bot_data.get("group_id", "Belgilanmagan")
    text = (
        f"📊 *Joriy Statistika*\n\n"
        f"➕ Bugun qo'shildi: {joined_count} kishi\n"
        f"➖ Bugun chiqdi: {left_count} kishi\n"
        f"👥 Jami (sessiyada): {member_count} kishi\n"
        f"🤖 Uslub namunalari: {len(your_style_examples)} ta\n"
        f"📖 Foydali ilmlar: {len(daily_knowledge)} ta\n"
        f"🔗 Guruh ID: {group_id}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def report_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await send_daily_report(context)

# ===================== AI JAVOB — GROQ =====================
TOUR_KEYWORDS_LATIN = [
    "umra", "haj", "ihrom", "tavof", "say", "zamzam", "makka", "madina",
    "reys", "narx", "bron", "joy", "chipta", "safar", "tur", "qachon",
    "soat", "bormi", "qancha", "necha", "mavjud", "bugun", "ertaga",
    "hafta", "kun", "vaqt", "band", "chegirma", "visa", "pasport",
    "hujjat", "tayyorgarlik", "niyat", "dua", "namoz", "masjid", "ziyorat"
]
TOUR_KEYWORDS_CYRILLIC = [
    "умра", "ҳаж", "иҳром", "тавоф", "саъй", "замзам", "макка", "мадина",
    "рейс", "нарх", "брон", "жой", "чипта", "сафар", "тур", "қачон",
    "соат", "борми", "қанча", "неча", "мавжуд", "бугун", "эртага",
    "ҳафта", "кун", "вақт", "банд", "чегирма", "виза", "паспорт",
    "ҳужжат", "тайёргарлик", "ният", "дуо", "намоз", "масжид", "зиёрат"
]

def is_relevant_question(text: str) -> bool:
    text_lower = text.lower()
    for kw in TOUR_KEYWORDS_LATIN + TOUR_KEYWORDS_CYRILLIC:
        if kw in text_lower:
            return True
    return False

async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return
    if is_admin(message.from_user.id):
        return

    text = message.text.strip()
    if not is_relevant_question(text):
        return

    style_prompt = ""
    if your_style_examples:
        style_prompt = "\n\nEllikboshi javob uslubi namunalari:\n"
        for ex in your_style_examples:
            style_prompt += f"Savol: {ex['question']}\nJavob: {ex['answer']}\n\n"

    system_prompt = f"""Siz umra safari firmasi ellikboshisining Telegram guruh botisiz.
Siz ellikboshi nomidan javob berasiz — xuddi u o'zi yozayotgandek.
Bu guruh maxfiy — a'zolar oshkor bo'lishni xohlamaydi, shuning uchun shaxsiy ma'lumot so'ramaysiz.
Foydalanuvchilar lotin yoki kril alifbosida yozishi mumkin — qaysi alifboda savol bo'lsa, o'sha alifboda javob bering.

Firma va guruh haqida:
{company_info['info']}
{style_prompt}

Muhim qoidalar:
- Qisqa, samimiy va aniq javob (2-3 jumla)
- Hech qachon bot yoki AI ekanligingizni aytmang
- Umra, safar, hujjatlar, narx, bron haqida savollar — javob bering
- Diniy savollarga — to'g'ri, ilmiy asoslangan javob bering
- Ma'lumot bo'lmasa: "Aniqroq ma'lumot uchun menga shaxsiy yozing"
- Savol kril alifbosida bo'lsa — kril alifbosida javob bering
- Savol lotin alifbosida bo'lsa — lotin alifbosida javob bering
- Har doim hurmatli va mehribon uslubda"""

    try:
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            max_tokens=300
        )
        answer = response.choices[0].message.content.strip()
        await message.reply_text(answer)
    except Exception as e:
        logger.error(f"Groq API xatosi: {e}")

# ===================== ASOSIY =====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setinfo", set_info))
    app.add_handler(CommandHandler("addstyle", add_style))
    app.add_handler(CommandHandler("clearstyle", clear_style))
    app.add_handler(CommandHandler("setgroup", set_group))
    app.add_handler(CommandHandler("addilm", add_ilm))
    app.add_handler(CommandHandler("ilm", send_ilm_now))
    app.add_handler(CommandHandler("elon", elon))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("report", report_now))
    app.add_handler(CommandHandler("sabablar", leave_stats_cmd))

    app.add_handler(CallbackQueryHandler(leave_reason_callback, pattern="^leave_"))
    app.add_handler(ChatMemberHandler(track_members, ChatMemberHandler.CHAT_MEMBER))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, delete_links), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_reply), group=2)

    app.job_queue.run_daily(send_daily_report, time=time(hour=20, minute=0), days=(0,1,2,3,4,5,6))
    app.job_queue.run_daily(daily_knowledge_job, time=time(hour=8, minute=0), days=(0,1,2,3,4,5,6))

    logger.info("✅ Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
