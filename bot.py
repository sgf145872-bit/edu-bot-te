# bot.py
import os
import sys
import threading
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from database import init_db
import config

# === إعداد التسجيل ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === دوال مساعدة ===
def get_db_connection():
    import sqlite3
    conn = sqlite3.connect('university.db')
    conn.row_factory = sqlite3.Row
    return conn

def is_bot_enabled():
    conn = get_db_connection()
    enabled = conn.execute("SELECT value FROM stats WHERE stat_name = 'bot_enabled'").fetchone()
    conn.close()
    return enabled and enabled['value'] == 1

def is_user_banned(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return user and user['is_banned'] == 1

def register_user(user_id, username):
    conn = get_db_connection()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
        (user_id, username or "unknown")
    )
    conn.execute("UPDATE stats SET value = (SELECT COUNT(*) FROM users) WHERE stat_name = 'total_users'")
    conn.commit()
    conn.close()

async def check_all_channels(user_id, bot):
    for ch in config.REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(ch, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except:
            return False
    return True

# === المعالجات ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_bot_enabled():
        await update.message.reply_text("البوت معطل حاليًا من قبل الإدارة.")
        return
    if is_user_banned(user_id):
        await update.message.reply_text("لقد تم حظرك من استخدام هذا البوت.")
        return
    register_user(user_id, update.effective_user.username)
    if config.REQUIRED_CHANNELS and user_id not in config.ADMIN_IDS:
        if not await check_all_channels(user_id, context.bot):
            buttons = []
            for ch in config.REQUIRED_CHANNELS:
                try:
                    chat = await context.bot.get_chat(ch)
                    url = f"https://t.me/{chat.username}" if chat.username else f"https://t.me/c/{str(ch).lstrip('-100')}"
                    buttons.append([InlineKeyboardButton(f"الانضمام إلى {chat.title}", url=url)])
                except:
                    buttons.append([InlineKeyboardButton("القناة", url=f"https://t.me/c/{str(ch).lstrip('-100')}")])
            buttons.append([InlineKeyboardButton("✅ تحققت من الانضمام", callback_data="check_channels")])
            await update.message.reply_text(
                "يرجى الانضمام إلى جميع القنوات التالية لتفعيل البوت:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return
    conn = get_db_connection()
    years = conn.execute("SELECT * FROM years").fetchall()
    conn.close()
    if not years:
        await update.message.reply_text("لا توجد سنوات دراسية مضافة بعد.")
        return
    keyboard = [[InlineKeyboardButton(y['name'], callback_data=f"year_{y['year_id']}")] for y in years]
    keyboard.append([InlineKeyboardButton("📊 الإحصائيات", callback_data="stats")])
    await update.message.reply_text("اختر السنة الدراسية:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data == "check_channels":
        if await check_all_channels(user_id, context.bot):
            await query.message.edit_text("شكرًا! يمكنك الآن استخدام البوت.")
            await start(update, context)
        else:
            await query.message.reply_text("لم تنضم إلى جميع القنوات بعد!")
        return

    if data == "stats":
        conn = get_db_connection()
        total = conn.execute("SELECT value FROM stats WHERE stat_name = 'total_users'").fetchone()
        conn.close()
        text = f"📊 **الإحصائيات**:\n\n👥 عدد المستخدمين: {total['value'] if total else 0}"
        await query.message.edit_text(text, parse_mode="Markdown")
        return

    if data.startswith("year_"):
        year_id = int(data.split("_")[1])
        conn = get_db_connection()
        terms = conn.execute("SELECT * FROM terms WHERE year_id = ?", (year_id,)).fetchall()
        conn.close()
        if not terms:
            await query.message.reply_text("لا توجد ترمات لهذه السنة.")
            return
        keyboard = [[InlineKeyboardButton(t['name'], callback_data=f"term_{t['term_id']}")] for t in terms]
        keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="back_to_years")])
        await query.message.edit_text("اختر الترم:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("term_"):
        term_id = int(data.split("_")[1])
        conn = get_db_connection()
        courses = conn.execute("SELECT * FROM courses WHERE term_id = ?", (term_id,)).fetchall()
        conn.close()
        if not courses:
            await query.message.reply_text("لا توجد مواد لهذا الترم.")
            return
        keyboard = [[InlineKeyboardButton(c['name'], callback_data=f"course_{c['course_id']}")] for c in courses]
        keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="back_to_terms")])
        await query.message.edit_text("اختر المادة:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("course_"):
        course_id = int(data.split("_")[1])
        conn = get_db_connection()
        files = conn.execute("SELECT * FROM files WHERE course_id = ?", (course_id,)).fetchall()
        conn.close()
        if not files:
            await query.message.reply_text("لا توجد ملفات لهذه المادة.")
            return
        for f in files:
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=f['telegram_file_id'],
                caption=f['name']
            )
        return

    if data == "back_to_years":
        await start(update, context)
        return

# === أوامر إدارية بسيطة (للتوضيح) ===
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in config.ADMIN_IDS:
        await update.message.reply_text("غير مصرح لك!")
        return
    await update.message.reply_text("مرحباً أيها المدير! (الوظائف الكاملة تحتاج توسيع)")

# === رفع ملفات (للإداريين) ===
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in config.ADMIN_IDS:
        return
    # هنا يمكنك إضافة منطق ربط الملف بمادة معينة
    await update.message.reply_text("تم استلام الملف. (الربط بالمادة: قيد التطوير)")

# === تشغيل البوت في خيط منفصل ===
def run_bot():
    init_db()
    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("🚀 بدء البوت في الخيط الخلفي...")
    try:
        app.run_polling(stop_signals=None)
    except Exception as e:
        logger.error(f"خطأ في تشغيل البوت: {e}")

# === التشغيل التلقائي على Streamlit ===
if "streamlit" in sys.modules:
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logger.info("✅ البوت يعمل في الخلفية على Streamlit.")
else:
    if __name__ == "__main__":
        run_bot()
