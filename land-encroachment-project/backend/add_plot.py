import sqlite3

conn = sqlite3.connect("land.db")
cursor = conn.cursor()

cursor.execute("INSERT INTO plots VALUES (?, ?, ?)", ("plot8", 13.11, 80.31))

conn.commit()
conn.close()

print("Plot added!")

