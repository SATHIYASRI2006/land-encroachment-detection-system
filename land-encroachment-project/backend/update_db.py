import sqlite3

conn = sqlite3.connect("land.db")
cursor = conn.cursor()

# Add new columns safely (ignore error if already exists)
try:
    cursor.execute("ALTER TABLE plots ADD COLUMN status TEXT")
except:
    print("status already exists")

try:
    cursor.execute("ALTER TABLE plots ADD COLUMN last_change REAL")
except:
    print("last_change already exists")

conn.commit()
conn.close()

print("Database updated successfully!")