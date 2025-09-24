import os
import sys
import threading
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from database import init_db, manage_courses, manage_years, manage_users
import config
import streamlit as st

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
    
# دالة جديدة للحصول على رابط الدعوة
async def get_invite_link(bot, chat_id):
    try:
        chat = await bot.get_chat(chat_id)
        if chat.username:
            # إذا كانت القناة عامة، استخدم اسم المستخدم
            return f"https://t.me/{chat.username}"
        else:
            # إذا كانت القناة خاصة، أنشئ رابط دعوة
            invite_link_obj = await bot.create_chat_invite_link(chat_id)
            return invite_link_obj.invite_link
    except Exception as e:
        logger.error(f"Failed to get invite link for {chat_id}: {e}")
        return None

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

    # تحقق من القنوات المطلوبة
    if config.REQUIRED_CHANNELS and user_id not in config.ADMIN_IDS:
        if not await check_all_channels(user_id, context.bot):
            buttons = []
            for ch in config.REQUIRED_CHANNELS:
                invite_url = await get_invite_link(context.bot, ch)
                if invite_url:
                    try:
                        chat = await context.bot.get_chat(ch)
                        buttons.append([InlineKeyboardButton(f"الانضمام إلى {chat.title}", url=invite_url)])
                    except:
                        buttons.append([InlineKeyboardButton("القناة", url=invite_url)])
                else:
                    buttons.append([InlineKeyboardButton("القناة (رابط غير متاح)", url="https://t.me/")])

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

    if data == "admin_panel":
        # عرض لوحة تحكم إدارية لأوامر مثل إضافة وحذف المواد
        await query.message.edit_text("إليك لوحة التحكم الإدارية.", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📚 إضافة مادة", callback_data="add_course")],
            [InlineKeyboardButton("🗑️ حذف مادة", callback_data="remove_course")],
            [InlineKeyboardButton("📝 إضافة سنة دراسية", callback_data="add_year")],
            [InlineKeyboardButton("🗑️ حذف سنة دراسية", callback_data="remove_year")],
            [InlineKeyboardButton("🚫 حظر مستخدم", callback_data="ban_user")],
            [InlineKeyboardButton("👥 عرض المستخدمين", callback_data="view_users")],
        ]))
        return

    if data == "add_course":
        await query.message.edit_text("أرسل اسم المادة التي تريد إضافتها.")
        return

    if data == "remove_course":
        conn = get_db_connection()
        courses = conn.execute("SELECT * FROM courses").fetchall()
        conn.close()
        buttons = [
            [InlineKeyboardButton(course['name'], callback_data=f"remove_course_{course['course_id']}")]
            for course in courses
        ]
        await query.message.edit_text("اختر المادة التي تريد حذفها:", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if data == "add_year":
        await query.message.edit_text("أرسل اسم السنة الدراسية التي تريد إضافتها.")
        return

    if data == "remove_year":
        conn = get_db_connection()
        years = conn.execute("SELECT * FROM years").fetchall()
        conn.close()
        buttons = [
            [InlineKeyboardButton(year['name'], callback_data=f"remove_year_{year['year_id']}")]
            for year in years
        ]
        await query.message.edit_text("اختر السنة الدراسية التي تريد حذفها:", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if data == "ban_user":
        await query.message.edit_text("أرسل معرف المستخدم الذي تريد حظره.")
        return

    if data == "view_users":
        conn = get_db_connection()
        users = conn.execute("SELECT * FROM users").fetchall()
        conn.close()
        text = "\n".join([f"@{user['username']}" for user in users])
        await query.message.edit_text(f"المستخدمون الحاليون:\n{text}")
        return

    # حذف مادة أو سنة دراسية
    if data.startswith("remove_course_"):
        course_id = int(data.split("_")[2])
        manage_courses(course_id, action="remove")
        await query.message.edit_text("تم حذف المادة بنجاح.")
        return

    if data.startswith("remove_year_"):
        year_id = int(data.split("_")[2])
        manage_years(year_id, action="remove")
        await query.message.edit_text("تم حذف السنة الدراسية بنجاح.")
        return

    # حظر المستخدم
    if data == "ban_user":
        user_id = int(data.split("_")[2])
        manage_users(user_id, action="ban")
        await query.message.edit_text(f"تم حظر المستخدم @ {user_id}.")
        return

# === تشغيل البوت في خيط منفصل مع إدارة event loop ===
def run_bot():
    init_db()

    # إعداد event loop يدويًا
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("🚀 بدء البوت في الخيط الخلفي...")
    try:
        loop.run_until_complete(app.run_polling(stop_signals=None))
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

