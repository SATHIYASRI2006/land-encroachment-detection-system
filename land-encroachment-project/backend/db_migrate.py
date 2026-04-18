import sqlite3

conn = sqlite3.connect("land.db")

cursor = conn.cursor()

# 🔍 check if column exists
cursor.execute("PRAGMA table_info(history)")
columns = [col[1] for col in cursor.fetchall()]

# ➕ add column only if missing
if "timestamp" not in columns:
    conn.execute("""
    ALTER TABLE history
    ADD COLUMN timestamp DATETIME DEFAULT CURRENT_TIMESTAMP;
    """)
    print("Timestamp column added")
else:
    print("Timestamp already exists")

# 📈 index safely
conn.execute("""
CREATE INDEX IF NOT EXISTS idx_plot ON history(plot_id);
""")

conn.commit()
conn.close()

print("Migration completed safely")