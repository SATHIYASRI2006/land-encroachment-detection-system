from __future__ import annotations

import os

from core.db import db_session
from services.alert_case_service import (
    create_alert_if_needed,
    create_case_if_needed,
    send_alert_email,
    store_plot_history,
)
from services.geofence_service import (
    detect_boundary_violation,
    elevate_risk,
    get_boundary_geojson,
    has_custom_boundary,
)
from services.monitoring_service import (
    analyze_satellite,
    draw_changes,
    get_risk_level,
    validate_plot_id,
)
from services.plot_service import get_all_plot_image_groups


def select_analysis_pair(images):
    supported_images = [
        item for item in images if 2021 <= int(item["year"]) <= 2024
    ]

    if len(supported_images) >= 2:
        images = supported_images

    if len(images) < 2:
        raise ValueError("Not enough images")

    # Prefer the most recent consecutive year pair. This avoids overstating
    # change when there is a large gap such as 2024 -> 2026 with no 2025 image.
    for index in range(len(images) - 1, 0, -1):
        current = images[index]
        previous = images[index - 1]
        if int(current["year"]) - int(previous["year"]) == 1:
            return previous, current

    # Fall back to the latest two images if no consecutive pair exists.
    return images[-2], images[-1]


def analyze_plot(settings, logger, socketio, plot_id: str, emit_socket=True):
    if not validate_plot_id(plot_id):
        raise ValueError("Invalid plot id")

    plot_images = get_all_plot_image_groups(settings)
    if plot_id not in plot_images or len(plot_images[plot_id]) < 2:
        raise ValueError("Not enough images")

    images = plot_images[plot_id]
    before_image, after_image = select_analysis_pair(images)
    before = before_image["image_path"]
    after = after_image["image_path"]

    before_path = os.path.join(settings.data_folder, before)
    after_path = os.path.join(settings.data_folder, after)
    change, confidence, thresh = analyze_satellite(
        before_path,
        after_path,
        settings.img_size,
    )

    with db_session(settings.db_path) as conn:
        plot_row = conn.execute(
            "SELECT * FROM plots WHERE id = ?",
            (plot_id,),
        ).fetchone()
        if not plot_row:
            raise ValueError(f"Plot not found in database: {plot_id}")

        risk = get_risk_level(change)
        boundary_geojson = get_boundary_geojson(conn, plot_row)
        custom_boundary = has_custom_boundary(conn, plot_row)
        boundary_violation = (
            detect_boundary_violation(plot_row, thresh, boundary_geojson)
            if custom_boundary
            else False
        )
        if boundary_violation:
            risk = elevate_risk(risk)

        output_file = draw_changes(
            after_path,
            thresh,
            plot_id,
            settings.data_folder,
            settings.img_size,
        )
        conn.execute(
            """
            UPDATE plots
            SET status = ?, last_change = ?
            WHERE id = ?
            """,
            (risk, change, plot_id),
        )

    store_plot_history(
        settings.db_path,
        plot_id,
        change,
        risk,
        confidence,
        boundary_violation,
    )

    message = (
        f"High-risk encroachment detected for plot {plot_id}."
        if risk == "High"
        else f"Encroachment update recorded for plot {plot_id}."
    )

    alert_row = create_alert_if_needed(settings.db_path, plot_id, risk, message)
    case_row = create_case_if_needed(
        settings.db_path,
        plot_id,
        risk,
        f"Auto-generated from analysis: {change:.2f}% change, confidence {confidence:.2f}%",
    )

    if alert_row:
        send_alert_email(
            settings,
            plot_id,
            change,
            risk,
            message,
            logger,
            alert_id=alert_row["id"],
        )

    with db_session(settings.db_path) as conn:
        plot_row = conn.execute(
            "SELECT * FROM plots WHERE id = ?",
            (plot_id,),
        ).fetchone()

    result = {
        "plot_id": plot_id,
        "change": change,
        "risk": risk,
        "confidence": confidence,
        "before_image": before,
        "after_image": after,
        "output_image": output_file,
        "boundary_violation": boundary_violation,
        "image_years": [item["year"] for item in images],
        "lat": plot_row["lat"],
        "lng": plot_row["lng"],
        "location_name": plot_row["location_name"],
        "area": plot_row["area"],
        "survey_no": plot_row["survey_no"],
        "owner_name": plot_row["owner_name"],
        "village": plot_row["village"],
        "district": plot_row["district"],
        "operator_note": plot_row["operator_note"],
        "boundary_geojson": boundary_geojson,
    }

    if case_row:
        result["case_id"] = case_row["id"]
    if alert_row:
        result["alert_id"] = alert_row["id"]

    if emit_socket:
        try:
            socketio.emit("plot_update", result)
        except Exception as exc:
            logger.exception("Socket emit error for plot %s: %s", plot_id, exc)

    return result
