import sqlite3

conn = sqlite3.connect("land.db")

conn.execute("""
CREATE TABLE history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plot_id TEXT,
    risk TEXT,
    change REAL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
conn.close()

print("History table created")