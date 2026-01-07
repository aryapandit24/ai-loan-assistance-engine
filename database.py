import sqlite3

DB_NAME = "loan_app.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            current_stage TEXT DEFAULT 'SALES',
            loan_type TEXT,
            age INTEGER DEFAULT 30,
            declared_income REAL,
            declared_emi REAL,
            loan_amount REAL,
            max_eligible REAL,
            verified_income REAL,
            check_a TEXT, 
            check_b TEXT, 
            check_c TEXT, 
            status TEXT DEFAULT 'PENDING',
            sanction_letter_text TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def update_user_data(user_id, **kwargs):
    if not kwargs: return
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    columns = ", ".join([f"{key} = ?" for key in kwargs.keys()])
    values = list(kwargs.values()) + [user_id]
    cursor.execute(f"UPDATE users SET {columns} WHERE user_id = ?", values)
    conn.commit()
    conn.close()