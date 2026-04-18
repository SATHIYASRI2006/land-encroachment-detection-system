from sentinelhub import SHConfig, SentinelHubRequest, DataCollection, MimeType, CRS, BBox
import sqlite3
import os
from PIL import Image
import datetime
import time

# ---------------- API CONFIG ---------------- #
config = SHConfig()
config.sh_client_id = "YOUR_CLIENT_ID"
config.sh_client_secret = "YOUR_CLIENT_SECRET"

# ---------------- CONFIG ---------------- #
DATA_FOLDER = "static/data"
os.makedirs(DATA_FOLDER, exist_ok=True)

# Smaller area = better clarity
BBOX_SIZE = 0.0002   # 🔥 IMPORTANT FIX

# Image quality
IMAGE_SIZE = (1024, 1024)  # can increase to (2048, 2048)

# ---------------- GET PLOTS FROM DB ---------------- #
def get_plots():
    conn = sqlite3.connect("land.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id, lat, lng FROM plots")
    rows = cursor.fetchall()
    conn.close()

    return [{"id": str(r[0]), "lat": r[1], "lng": r[2]} for r in rows]


# ---------------- FETCH IMAGE ---------------- #
def fetch_image(plot):
    try:
        today = datetime.date.today()
        last_week = today - datetime.timedelta(days=7)

        filename = f"{plot['id']}_{today.year}.png"
        filepath = os.path.join(DATA_FOLDER, filename)

        # ❌ REMOVE OLD IMAGE (IMPORTANT FIX)
        if os.path.exists(filepath):
            os.remove(filepath)

        bbox = BBox(
            bbox=[
                plot["lng"] - BBOX_SIZE,
                plot["lat"] - BBOX_SIZE,
                plot["lng"] + BBOX_SIZE,
                plot["lat"] + BBOX_SIZE
            ],
            crs=CRS.WGS84
        )

        request = SentinelHubRequest(
            evalscript="""
            //VERSION=3
            function setup() {
              return {
                input: ["B04", "B03", "B02"],
                output: { bands: 3 }
              };
            }
            function evaluatePixel(sample) {
              return [sample.B04, sample.B03, sample.B02];
            }
            """,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.SENTINEL2_L2A,
                    time_interval=(str(last_week), str(today))
                )
            ],
            responses=[
                SentinelHubRequest.output_response("default", MimeType.PNG)
            ],
            bbox=bbox,
            size=IMAGE_SIZE,
            config=config
        )

        images = request.get_data()

        if images and len(images) > 0:
            img = images[0]

            # 🔥 FIX: Normalize image properly
            img = (img / img.max()) * 255
            img = img.astype("uint8")

            Image.fromarray(img).save(filepath)
            print(f"✅ Updated: {filename}")

        else:
            print(f"⚠️ No data: {plot['id']}")

    except Exception as e:
        print(f"❌ Error fetching {plot['id']}: {e}")


# ---------------- AUTO LOOP ---------------- #
def auto_fetch():
    while True:
        print("🌍 Fetching latest satellite data...")

        plots = get_plots()

        for plot in plots:
            fetch_image(plot)

        print("⏳ Waiting for next cycle...\n")

        # every 30 minutes (better than 1 hour)
        time.sleep(1800)


# ---------------- RUN ---------------- #
if __name__ == "__main__":
    auto_fetch()