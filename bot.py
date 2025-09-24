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
# تأكد من وجود ملف database.py في نفس المسار
from database import init_db, manage_courses, manage_years, manage_users
# تأكد من وجود ملف config.py معدّل
import config 

# --- حذف استيراد Streamlit ---
# import streamlit as st # تم الحذف

# === إعداد التسجيل ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === دوال مساعدة ===
def get_db_connection():
    import sqlite3
    # ملاحظة: عند استخدام Koyeb، قد تحتاج إلى تثبيت قاعدة بيانات خارجية (PostgreSQL/MySQL) 
    # واستبدال SQLite لتجنب فقدان البيانات عند إعادة تشغيل الحاوية.
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

# دالة للتحقق من انضمام المستخدم للقنوات
async def check_all_channels(user_id, bot):
    # تبقى وظيفة مؤقتة
    return True 

# دالة للتعامل مع المستندات
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # تبقى وظيفة مؤقتة
    await update.message.reply_text("تم استلام المستند.") 

async def get_invite_link(bot, chat_id):
    try:
        chat = await bot.get_chat(chat_id)
        if chat.username:
            return f"https://t.me/{chat.username}"
        else:
            invite_link_obj = await bot.create_chat_invite_link(chat_id)
            return invite_link_obj.invite_link
    except Exception as e:
        logger.error(f"Failed to get invite link for {chat_id}: {e}")
        return None

# === حالات المحادثة ===
ADD_COURSE_STATE, REMOVE_COURSE_STATE, ADD_YEAR_STATE, REMOVE_YEAR_STATE, BAN_USER_STATE = range(5)
waiting_for_input = {}

# === المعالجات (تم الإبقاء عليها كما هي، تعتمد على الدوال المساعدة و config) ===
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
            for ch in config.REQUIRED_CHepos:
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

    if user_id in config.ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ لوحة تحكم المدير", callback_data="admin_panel")])
    
    await update.message.reply_text("اختر السنة الدراسية:", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in config.ADMIN_IDS:
        await update.message.reply_text("❌ ليس لديك صلاحية الوصول إلى هذا الأمر.")
        return
    
    if not is_bot_enabled():
        await update.message.reply_text("البوت معطل حاليًا من قبل الإدارة.")
        return
    
    if is_user_banned(user_id):
        await update.message.reply_text("لقد تم حظرك من استخدام هذا البوت.")
        return
    
    await update.message.reply_text(
        "مرحباً أيها المدير! اختر من القائمة:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📚 إضافة مادة", callback_data="admin_add_course"), 
             InlineKeyboardButton("🗑️ حذف مادة", callback_data="admin_remove_course")],
            [InlineKeyboardButton("📝 إضافة سنة دراسية", callback_data="admin_add_year"), 
             InlineKeyboardButton("🗑️ حذف سنة دراسية", callback_data="admin_remove_year")],
            [InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban_user"), 
             InlineKeyboardButton("👥 عرض المستخدمين", callback_data="admin_view_users")],
            [InlineKeyboardButton("🔄 تحديث الإحصائيات", callback_data="stats")]
        ])
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    
    if data.startswith("admin_") and user_id not in config.ADMIN_IDS:
        await query.message.edit_text("❌ ليس لديك صلاحية الوصول إلى هذه الوظيفة.")
        return
    
    if data == "check_channels":
        if await check_all_channels(user_id, context.bot):
            await query.message.edit_text("✅ شكرًا! يمكنك الآن استخدام البوت.")
            await start(update, context)
        else:
            await query.message.edit_text("❌ لم تنضم إلى جميع القنوات بعد!")
        return

    if data == "stats":
        conn = get_db_connection()
        total = conn.execute("SELECT value FROM stats WHERE stat_name = 'total_users'").fetchone()
        conn.close()
        text = f"📊 **الإحصائيات**:\n\n👥 عدد المستخدمين: {total['value'] if total else 0}"
        await query.message.edit_text(text, parse_mode="Markdown")
        return

    if data == "admin_panel":
        await query.message.edit_text(
            "مرحباً أيها المدير! اختر من القائمة:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📚 إضافة مادة", callback_data="admin_add_course"), 
                 InlineKeyboardButton("🗑️ حذف مادة", callback_data="admin_remove_course")],
                [InlineKeyboardButton("📝 إضافة سنة دراسية", callback_data="admin_add_year"), 
                 InlineKeyboardButton("🗑️ حذف سنة دراسية", callback_data="admin_remove_year")],
                [InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban_user"), 
                 InlineKeyboardButton("👥 عرض المستخدمين", callback_data="admin_view_users")],
                [InlineKeyboardButton("🔄 تحديث الإحصائيات", callback_data="stats")]
            ])
        )
        return

    if data == "admin_add_course":
        waiting_for_input[user_id] = "add_course"
        await query.message.edit_text("📝 أرسل اسم المادة التي تريد إضافتها:")
        return

    if data == "admin_remove_course":
        conn = get_db_connection()
        courses = conn.execute("SELECT * FROM courses").fetchall()
        conn.close()
        if not courses:
            await query.message.edit_text("❌ لا توجد مواد مضافة حالياً.")
            return
            
        buttons = [[InlineKeyboardButton(c['name'], callback_data=f"remove_course_{c['course_id']}")] for c in courses]
        buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
        await query.message.edit_text("اختر المادة التي تريد حذفها:", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if data == "admin_add_year":
        waiting_for_input[user_id] = "add_year"
        await query.message.edit_text("📝 أرسل اسم السنة الدراسية التي تريد إضافتها:")
        return

    if data == "admin_remove_year":
        conn = get_db_connection()
        years = conn.execute("SELECT * FROM years").fetchall()
        conn.close()
        if not years:
            await query.message.edit_text("❌ لا توجد سنوات دراسية مضافة حالياً.")
            return
            
        buttons = [[InlineKeyboardButton(y['name'], callback_data=f"remove_year_{y['year_id']}")] for y in years]
        buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
        await query.message.edit_text("اختر السنة الدراسية التي تريد حذفها:", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if data == "admin_ban_user":
        waiting_for_input[user_id] = "ban_user"
        await query.message.edit_text("🚫 أرسل معرف المستخدم الذي تريد حظره:")
        return

    if data == "admin_view_users":
        conn = get_db_connection()
        users = conn.execute("SELECT user_id, username, is_banned FROM users").fetchall()
        conn.close()
        if not users:
            await query.message.edit_text("❌ لا يوجد مستخدمون حالياً.")
            return

        user_list = "\n".join([f"@{u['username']} (ID: {u['user_id']}) - {'🚫 محظور' if u['is_banned'] else '✅ نشط'}" for u in users])
        await query.message.edit_text(f"👥 المستخدمون الحاليون:\n\n{user_list}")
        return

    if data.startswith("remove_course_"):
        course_id = int(data.split("_")[2])
        manage_courses(course_id=course_id, action="remove")
        await query.message.edit_text("✅ تم حذف المادة بنجاح.")
        return

    if data.startswith("remove_year_"):
        year_id = int(data.split("_")[2])
        manage_years(year_id=year_id, action="remove")
        await query.message.edit_text("✅ تم حذف السنة الدراسية بنجاح.")
        return
        
    if data == "cancel":
        waiting_for_input.pop(user_id, None)
        await query.message.edit_text("❌ تم إلغاء العملية.")
        return

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text
    
    if user_id not in config.ADMIN_IDS or user_id not in waiting_for_input:
        return
    
    action = waiting_for_input.pop(user_id)

    if action == "add_course":
        manage_courses(course_name=message_text, action="add")
        await update.message.reply_text(f"✅ تم إضافة المادة '{message_text}' بنجاح.")
    
    elif action == "add_year":
        manage_years(year_name=message_text, action="add")
        await update.message.reply_text(f"✅ تم إضافة السنة الدراسية '{message_text}' بنجاح.")

    elif action == "ban_user":
        try:
            user_to_ban_id = int(message_text)
            manage_users(user_id=user_to_ban_id, action="ban")
            await update.message.reply_text(f"✅ تم حظر المستخدم ذي المعرف '{user_to_ban_id}' بنجاح.")
        except ValueError:
            await update.message.reply_text("❌ معرف المستخدم يجب أن يكون رقماً. يرجى المحاولة مرة أخرى.")

# --- تم حذف متغير bot_thread_started لعدم الحاجة إليه ---

# === تشغيل البوت في event loop ===
def run_bot():
    # تأكد من أن قاعدة البيانات تبدأ
    init_db()

    # استخدام event loop جديد لأننا خارج بيئة Streamlit
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # استخدام config.BOT_TOKEN الذي سيتم قراءته من os.environ
    app = Application.builder().token(config.BOT_TOKEN).build()

    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))  
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_admin_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    logger.info("🚀 بدء البوت في وضع التشغيل المستمر (Polling)...")
    try:
        # تشغيل البوت في وضع Polling، وهو النموذج الأنسب للخوادم التي لا تستخدم Webhooks
        loop.run_until_complete(app.run_polling(stop_signals=None))
    except Exception as e:
        logger.error(f"خطأ في تشغيل البوت: {e}")

# === التشغيل الرئيسي (للتأكد من تشغيل البوت مباشرة على الخادم) ===
if __name__ == "__main__":
    # تم حذف كتلة if "streamlit" in sys.modules
    run_bot()

