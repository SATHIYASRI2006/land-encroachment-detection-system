import json
import random

# Chennai base coordinates (approx)
BASE_LAT = 13.05
BASE_LNG = 80.25

def generate_boundary():
    lat = BASE_LAT + random.uniform(-0.05, 0.05)
    lng = BASE_LNG + random.uniform(-0.05, 0.05)

    return [
        [lat, lng],
        [lat + 0.002, lng + 0.003],
        [lat + 0.004, lng + 0.001],
        [lat + 0.003, lng - 0.002]
    ]

def generate_data(n=50):
    data = []

    for i in range(1, n + 1):
        plot = {
            "plot_id": f"plot{i}",
            "name": f"Government Land Parcel {i}",
            "district": "Chennai",
            "state": "Tamil Nadu",
            "area_sqm": random.randint(5000, 50000),
            "boundary": generate_boundary(),
            "encroachment_level": round(random.uniform(0, 0.3), 2)
        }
        data.append(plot)

    return data

# Generate 50 records (you can increase later)
land_data = generate_data(50)

with open("land_data.json", "w") as f:
    json.dump(land_data, f, indent=2)

print("✅ Generated 50 realistic land records in land_data.json")