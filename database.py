import sqlite3

DATABASE_NAME = 'university.db'

def get_db_connection():
    """Establishes and returns a connection to the database."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database and creates necessary tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            is_banned INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS years (
            year_id INTEGER PRIMARY KEY,
            name TEXT UNIQUE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS courses (
            course_id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            year_id INTEGER,
            FOREIGN KEY(year_id) REFERENCES years(year_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stats (
            stat_name TEXT PRIMARY KEY,
            value INTEGER
        )
    ''')

    # Initialize stats if they don't exist
    cursor.execute("INSERT OR IGNORE INTO stats (stat_name, value) VALUES ('total_users', 0)")
    cursor.execute("INSERT OR IGNORE INTO stats (stat_name, value) VALUES ('bot_enabled', 1)")

    conn.commit()
    conn.close()

def manage_courses(course_id=None, course_name=None, year_id=None, action="add"):
    """Manages adding or removing courses."""
    conn = get_db_connection()
    if action == "add" and course_name and year_id:
        try:
            conn.execute("INSERT INTO courses (name, year_id) VALUES (?, ?)", (course_name, year_id))
            conn.commit()
        except sqlite3.IntegrityError:
            print(f"Course '{course_name}' already exists.")
    elif action == "remove" and course_id:
        conn.execute("DELETE FROM courses WHERE course_id = ?", (course_id,))
        conn.commit()
    conn.close()

def manage_years(year_id=None, year_name=None, action="add"):
    """Manages adding or removing years."""
    conn = get_db_connection()
    if action == "add" and year_name:
        try:
            conn.execute("INSERT INTO years (name) VALUES (?)", (year_name,))
            conn.commit()
        except sqlite3.IntegrityError:
            print(f"Year '{year_name}' already exists.")
    elif action == "remove" and year_id:
        conn.execute("DELETE FROM years WHERE year_id = ?", (year_id,))
        conn.commit()
    conn.close()

def manage_users(user_id, action):
    """Manages user-related actions like banning."""
    conn = get_db_connection()
    if action == "ban":
        conn.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
    elif action == "unban":
        conn.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    # You can run this file directly to initialize the database.
    init_db()
    print("Database initialized.")

