from __future__ import annotations

import json
import os

from werkzeug.utils import secure_filename

from core.db import db_session
from services.geofence_service import default_boundary


def get_plot_images(db_path: str, plot_id=None):
    with db_session(db_path) as conn:
        if plot_id:
            rows = conn.execute(
                """
                SELECT plot_id, year, image_path
                FROM images
                WHERE plot_id = ?
                ORDER BY year
                """,
                (plot_id,),
            ).fetchall()
            return [dict(row) for row in rows]

        rows = conn.execute(
            """
            SELECT plot_id, year, image_path
            FROM images
            ORDER BY plot_id, year
            """
        ).fetchall()

    grouped = {}
    for row in rows:
        grouped.setdefault(row["plot_id"], []).append(dict(row))
    return grouped


def get_all_plot_image_groups(settings):
    grouped = get_plot_images(settings.db_path) or {}
    plots = {
        plot_id: sorted(items, key=lambda item: item["year"])
        for plot_id, items in grouped.items()
    }

    for file_name in os.listdir(settings.data_folder):
        ext = os.path.splitext(file_name)[1].lower()
        if ext not in settings.allowed_image_extensions:
            continue

        name = os.path.splitext(file_name)[0]
        parts = name.split("_")
        if len(parts) != 2:
            continue

        plot_id, year = parts
        if not year.isdigit():
            continue

        normalized_plot_id = plot_id.replace("_", " ")
        candidate_ids = [plot_id, normalized_plot_id]

        matched_plot_id = None
        for candidate in candidate_ids:
            if candidate in plots:
                matched_plot_id = candidate
                break

        if matched_plot_id is None:
            matched_plot_id = plot_id
            plots.setdefault(matched_plot_id, [])

        already_present = any(
            int(item["year"]) == int(year) for item in plots[matched_plot_id]
        )
        if not already_present:
            plots[matched_plot_id].append(
                {
                    "plot_id": matched_plot_id,
                    "year": int(year),
                    "image_path": file_name,
                }
            )

    for plot_id in plots:
        plots[plot_id] = sorted(plots[plot_id], key=lambda item: item["year"])

    return plots


def serialize_plot(db_path: str, row):
    image_rows = []
    with db_session(db_path) as conn:
        image_rows = conn.execute(
            """
            SELECT year, image_path
            FROM images
            WHERE plot_id = ?
            ORDER BY year
            """,
            (row["id"],),
        ).fetchall()
        boundary_row = conn.execute(
            """
            SELECT boundary_geojson
            FROM plot_boundaries
            WHERE plot_id = ?
            """,
            (row["id"],),
        ).fetchone()

    boundary_geojson = (
        json.loads(boundary_row["boundary_geojson"])
        if boundary_row and boundary_row["boundary_geojson"]
        else default_boundary(row)
    )

    image_years = [image_row["year"] for image_row in image_rows]
    if not image_years:
        base_dir = os.path.dirname(db_path)
        data_folder = os.path.join(base_dir, "static", "data")
        for file_name in os.listdir(data_folder):
            ext = os.path.splitext(file_name)[1].lower()
            if ext not in {".png", ".jpg", ".jpeg"}:
                continue
            stem = os.path.splitext(file_name)[0]
            parts = stem.split("_")
            if len(parts) != 2 or not parts[1].isdigit():
                continue
            file_plot_id = parts[0].replace("_", " ")
            if file_plot_id == row["id"] or parts[0] == row["id"]:
                image_years.append(int(parts[1]))

        image_years = sorted(set(image_years))

    return {
        "id": row["id"],
        "lat": row["lat"],
        "lng": row["lng"],
        "location_name": row["location_name"],
        "status": row["status"] or "Low",
        "last_change": row["last_change"] or 0,
        "area": row["area"],
        "survey_no": row["survey_no"],
        "owner_name": row["owner_name"],
        "village": row["village"],
        "district": row["district"],
        "operator_note": row["operator_note"],
        "image_years": image_years,
        "boundary_geojson": boundary_geojson,
    }


def save_uploaded_image(settings, plot_id: str, year: str, file_storage):
    original_name = secure_filename(file_storage.filename or "")
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in settings.allowed_image_extensions:
        raise ValueError(f"Unsupported file type for year {year}")

    safe_plot_id = secure_filename(plot_id).replace("-", "_")
    final_name = f"{safe_plot_id}_{year}{ext}"
    file_storage.save(os.path.join(settings.data_folder, final_name))
    return final_name


def upsert_plot_bundle(settings, metadata: dict, uploaded_images: dict[int, str]):
    with db_session(settings.db_path) as conn:
        conn.execute(
            """
            INSERT INTO plots (
                id, lat, lng, location_name, area, survey_no, owner_name,
                village, district, operator_note, status, last_change
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, 'Low'), COALESCE(?, 0))
            ON CONFLICT(id) DO UPDATE SET
                lat = excluded.lat,
                lng = excluded.lng,
                location_name = excluded.location_name,
                area = excluded.area,
                survey_no = excluded.survey_no,
                owner_name = excluded.owner_name,
                village = excluded.village,
                district = excluded.district,
                operator_note = excluded.operator_note
            """,
            (
                metadata["plot_id"],
                metadata["lat"],
                metadata["lng"],
                metadata["location_name"],
                metadata["area"],
                metadata["survey_no"],
                metadata["owner_name"],
                metadata["village"],
                metadata["district"],
                metadata["operator_note"],
                metadata.get("status"),
                metadata.get("last_change"),
            ),
        )

        for year, image_path in uploaded_images.items():
            conn.execute(
                """
                INSERT INTO images (plot_id, year, image_path)
                VALUES (?, ?, ?)
                ON CONFLICT(plot_id, year) DO UPDATE SET
                    image_path = excluded.image_path
                """,
                (metadata["plot_id"], int(year), image_path),
            )

        boundary_geojson = metadata.get("boundary_geojson")
        if not boundary_geojson:
            plot_row = conn.execute(
                "SELECT * FROM plots WHERE id = ?",
                (metadata["plot_id"],),
            ).fetchone()
            boundary_geojson = default_boundary(plot_row)

        conn.execute(
            """
            INSERT INTO plot_boundaries (plot_id, boundary_geojson, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(plot_id) DO UPDATE SET
                boundary_geojson = excluded.boundary_geojson,
                updated_at = CURRENT_TIMESTAMP
            """,
            (metadata["plot_id"], json.dumps(boundary_geojson)),
        )
