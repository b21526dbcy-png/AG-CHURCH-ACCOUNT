import os
import sqlite3
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database.db')
if os.path.exists(DB_PATH):
    print('database.db already exists')
else:
    conn = sqlite3.connect(DB_PATH)
    conn.execute('CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL, full_name TEXT NOT NULL, location TEXT NOT NULL DEFAULT "")')
    conn.execute('CREATE TABLE bills (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, bill_number TEXT NOT NULL, created_at TEXT NOT NULL, department TEXT NOT NULL, amount REAL NOT NULL, description TEXT, file_name TEXT, status TEXT NOT NULL, remarks TEXT, FOREIGN KEY(user_id) REFERENCES users(id))')
    conn.execute('CREATE TABLE offerings (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, offering_date TEXT NOT NULL, amount REAL NOT NULL, description TEXT, FOREIGN KEY(user_id) REFERENCES users(id))')
    conn.execute('INSERT INTO users (username, password, role, full_name, location) VALUES (?,?,?,?,?)', ('admin', generate_password_hash('admin123'), 'ADMIN', 'Church Administrator', 'Head Office'))
    conn.execute('INSERT INTO users (username, password, role, full_name, location) VALUES (?,?,?,?,?)', ('user', generate_password_hash('user123'), 'USER', 'Grace Member', 'Main Branch'))
    conn.commit()
    conn.close()
    print('database.db created')
