import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from database import init_db
import config
import sqlite3

# === إعدادات ===
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# === دوال مساعدة ===
def get_db_connection():
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
    # تحديث العدد الكلي
    conn.execute("UPDATE stats SET value = (SELECT COUNT(*) FROM users) WHERE stat_name = 'total_users'")
    conn.commit()
    conn.close()

def check_all_channels(user_id, context: ContextTypes.DEFAULT_TYPE):
    for ch in config.REQUIRED_CHANNELS:
        try:
            member = context.bot.get_chat_member(ch, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except:
            return False
    return True

# === معالجات ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username

    if not is_bot_enabled():
        await update.message.reply_text("البوت معطل حاليًا من قبل الإدارة.")
        return

    if is_user_banned(user_id):
        await update.message.reply_text("لقد تم حظرك من استخدام هذا البوت.")
        return

    register_user(user_id, username)

    # التحقق من القنوات
    if not check_all_channels(user_id, context):
        buttons = []
        for ch in config.REQUIRED_CHANNELS:
            chat = await context.bot.get_chat(ch)
            buttons.append([InlineKeyboardButton(f"الانضمام إلى {chat.title}", url=f"https://t.me/{chat.username}")])
        buttons.append([InlineKeyboardButton("✅ تحققت من الانضمام", callback_data="check_channels")])
        await update.message.reply_text(
            "يرجى الانضمام إلى جميع القنوات التالية لتفعيل البوت:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    # تحديث حالة المستخدم
    conn = get_db_connection()
    conn.execute("UPDATE users SET completed_channels = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

    # عرض السنوات
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

    if not is_bot_enabled():
        await query.message.reply_text("البوت معطل.")
        return

    if is_user_banned(user_id):
        await query.message.reply_text("لقد تم حظرك.")
        return

    # التحقق من القنوات عند النقر على "تحقق"
    if data == "check_channels":
        if check_all_channels(user_id, context):
            conn = get_db_connection()
            conn.execute("UPDATE users SET completed_channels = 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            await query.message.edit_text("شكرًا! يمكنك الآن استخدام البوت.")
            await start(update, context)  # إعادة عرض الواجهة
        else:
            await query.message.reply_text("لم تنضم إلى جميع القنوات بعد!")
        return

    # --- باقي المعالجات ---
    if data.startswith("year_"):
        year_id = int(data.split("_")[1])
        conn = get_db_connection()
        terms = conn.execute("SELECT * FROM terms WHERE year_id = ?", (year_id,)).fetchall()
        conn.close()
        if not terms:
            await query.message.reply_text("لا توجد ترمات مضافة لهذه السنة.")
            return
        keyboard = [[InlineKeyboardButton(t['name'], callback_data=f"term_{t['term_id']}")] for t in terms]
        keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="back_to_years")])
        await query.message.edit_text("اختر الترم:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("term_"):
        term_id = int(data.split("_")[1])
        conn = get_db_connection()
        courses = conn.execute("SELECT * FROM courses WHERE term_id = ?", (term_id,)).fetchall()
        conn.close()
        if not courses:
            await query.message.reply_text("لا توجد مواد مضافة لهذا الترم.")
            return
        keyboard = [[InlineKeyboardButton(c['name'], callback_data=f"course_{c['course_id']}")] for c in courses]
        keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="back_to_terms")])
        await query.message.edit_text("اختر المادة:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("course_"):
        course_id = int(data.split("_")[1])
        conn = get_db_connection()
        files = conn.execute("SELECT * FROM files WHERE course_id = ?", (course_id,)).fetchall()
        conn.close()
        if not files:
            await query.message.reply_text("لا توجد ملفات لهذه المادة بعد.")
            return
        for f in files:
            await context.bot.send_document(chat_id=query.message.chat_id, document=f['telegram_file_id'], caption=f['name'])

    elif data == "back_to_years":
        await start(update, context)

    elif data == "stats":
        conn = get_db_connection()
        total = conn.execute("SELECT value FROM stats WHERE stat_name = 'total_users'").fetchone()
        courses_stats = conn.execute("""
            SELECT c.name, COUNT(f.file_id) as file_count
            FROM courses c
            LEFT JOIN files f ON c.course_id = f.course_id
            GROUP BY c.course_id
            ORDER BY file_count DESC
            LIMIT 5
        """).fetchall()
        conn.close()

        stats_text = f"📊 **الإحصائيات**:\n\n"
        stats_text += f"👥 عدد المستخدمين: {total['value'] if total else 0}\n\n"
        stats_text += "أكثر المواد احتواءً على ملفات:\n"
        for cs in courses_stats:
            stats_text += f"• {cs['name']}: {cs['file_count']} ملفات\n"

        await query.message.edit_text(stats_text, parse_mode="Markdown")

    # === لوحة التحكم الإدارية ===
    elif data == "admin_panel":
        if user_id not in config.ADMIN_IDS:
            await query.message.reply_text("غير مصرح لك!")
            return
        enabled = "🟢 مشغل" if is_bot_enabled() else "🔴 معطل"
        keyboard = [
            [InlineKeyboardButton(f"تبديل حالة البوت ({enabled})", callback_data="toggle_bot")],
            [InlineKeyboardButton("عرض المستخدمين", callback_data="list_users")],
            [InlineKeyboardButton("إدارة المحتوى", callback_data="manage_content")],
        ]
        await query.message.edit_text("لوحة التحكم الإدارية:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "toggle_bot":
        conn = get_db_connection()
        current = conn.execute("SELECT value FROM stats WHERE stat_name = 'bot_enabled'").fetchone()
        new_val = 0 if current['value'] == 1 else 1
        conn.execute("UPDATE stats SET value = ? WHERE stat_name = 'bot_enabled'", (new_val,))
        conn.commit()
        conn.close()
        await query.message.edit_text(f"تم {'تشغيل' if new_val else 'إيقاف'} البوت بنجاح!")

# === أوامر إدارية ===
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in config.ADMIN_IDS:
        await update.message.reply_text("غير مصرح لك!")
        return

    if context.args and context.args[0] == "ban":
        try:
            target = int(context.args[1])
            conn = get_db_connection()
            conn.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target,))
            conn.commit()
            conn.close()
            await update.message.reply_text(f"تم حظر المستخدم {target}")
        except:
            await update.message.reply_text("استخدام: /admin ban <user_id>")
        return

    if context.args and context.args[0] == "unban":
        try:
            target = int(context.args[1])
            conn = get_db_connection()
            conn.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (target,))
            conn.commit()
            conn.close()
            await update.message.reply_text(f"تم رفع الحظر عن {target}")
        except:
            await update.message.reply_text("استخدام: /admin unban <user_id>")
        return

    # عرض لوحة التحكم
    keyboard = [[InlineKeyboardButton("فتح لوحة التحكم", callback_data="admin_panel")]]
    await update.message.reply_text("مرحباً أيها المدير!", reply_markup=InlineKeyboardMarkup(keyboard))

# === رفع ملفات (للإداريين فقط) ===
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in config.ADMIN_IDS:
        return

    if not context.user_data.get('awaiting_file_for_course'):
        return

    course_id = context.user_data['awaiting_file_for_course']
    file = update.message.document
    file_name = file.file_name or "ملف غير معنون"

    new_file = await file.get_file()
    telegram_file_id = new_file.file_id

    conn = get_db_connection()
    conn.execute("INSERT INTO files (course_id, name, telegram_file_id) VALUES (?, ?, ?)",
                 (course_id, file_name, telegram_file_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"تم رفع الملف '{file_name}' للمادة بنجاح!")
    del context.user_data['awaiting_file_for_course']

# === الدالة الرئيسية ===
def main():
    init_db()
    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("✅ البوت يعمل بأمان! لا خطر على الحساب.")
    app.run_polling()

if __name__ == "__main__":
    main()
