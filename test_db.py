import sqlite3

conn = sqlite3.connect('database.db')
conn.row_factory = sqlite3.Row
users = conn.execute("SELECT * FROM users ORDER BY id ASC").fetchall()
print(f"Total users: {len(users)}")
for user in users:
    print(f"ID: {user[0]}, Username: {user[1]}, Full Name: {user[4]}")
conn.close()
