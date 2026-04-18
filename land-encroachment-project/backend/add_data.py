import sqlite3

conn = sqlite3.connect("land.db")
cursor = conn.cursor()

# Insert plots
plots = [
    ("plot1", 13.0827, 80.2707, "Chennai A"),
    ("plot2", 13.0900, 80.2500, "Chennai B"),
    ("plot3", 13.0850, 80.2600, "Chennai C"),
    ("plot4", 13.0950, 80.2700, "Chennai D"),
    ("plot5", 13.0300, 80.2200, "Chennai E"),
    ("plot6", 13.1200, 80.2600, "Chennai F"),
    ("plot7", 13.1100, 80.3000, "Chennai G")
]

cursor.executemany(
    "INSERT OR REPLACE INTO plots (id, lat, lng, location_name) VALUES (?, ?, ?, ?)",
    plots
)

conn.commit()
conn.close()

print("Data inserted!")