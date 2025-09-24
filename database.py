import sqlite3

def init_db():
    conn = sqlite3.connect('university.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_banned INTEGER DEFAULT 0,
        completed_channels INTEGER DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS years (
        year_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS terms (
        term_id INTEGER PRIMARY KEY AUTOINCREMENT,
        year_id INTEGER,
        name TEXT NOT NULL, -- "ترم أول", "ترم ثاني", "مواد ممتدة"
        FOREIGN KEY(year_id) REFERENCES years(year_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS courses (
        course_id INTEGER PRIMARY KEY AUTOINCREMENT,
        term_id INTEGER,
        name TEXT NOT NULL,
        FOREIGN KEY(term_id) REFERENCES terms(term_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS files (
        file_id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER,
        name TEXT,
        telegram_file_id TEXT,
        FOREIGN KEY(course_id) REFERENCES courses(course_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS stats (
        stat_name TEXT PRIMARY KEY,
        value INTEGER
    )''')

    # تهيئة حالة البوت (مشغل/معطل)
    c.execute("INSERT OR IGNORE INTO stats (stat_name, value) VALUES ('bot_enabled', 1)")
    c.execute("INSERT OR IGNORE INTO stats (stat_name, value) VALUES ('total_users', 0)")

    conn.commit()
    conn.close()
