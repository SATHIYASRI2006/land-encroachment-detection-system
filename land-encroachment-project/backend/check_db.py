import sqlite3

conn = sqlite3.connect("land.db")
cursor = conn.cursor()

cursor.execute("SELECT id, status, last_change FROM plots")
rows = cursor.fetchall()

for r in rows:
    print(r)

conn.close()