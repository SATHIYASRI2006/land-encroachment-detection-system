from __future__ import annotations

import json

from shapely.geometry import Point, shape


def default_boundary(plot_row) -> dict:
    lat = float(plot_row["lat"] or 0)
    lng = float(plot_row["lng"] or 0)
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [lng - 0.002, lat - 0.002],
                [lng + 0.002, lat - 0.002],
                [lng + 0.002, lat + 0.002],
                [lng - 0.002, lat + 0.002],
                [lng - 0.002, lat - 0.002],
            ]
        ],
    }


def get_boundary_geojson(conn, plot_row):
    boundary_row = conn.execute(
        "SELECT boundary_geojson FROM plot_boundaries WHERE plot_id = ?",
        (plot_row["id"],),
    ).fetchone()
    if boundary_row and boundary_row["boundary_geojson"]:
        return json.loads(boundary_row["boundary_geojson"])
    return default_boundary(plot_row)


def has_custom_boundary(conn, plot_row) -> bool:
    boundary_row = conn.execute(
        "SELECT boundary_geojson FROM plot_boundaries WHERE plot_id = ?",
        (plot_row["id"],),
    ).fetchone()
    if not boundary_row or not boundary_row["boundary_geojson"]:
        return False

    stored = json.loads(boundary_row["boundary_geojson"])
    return json.dumps(stored, sort_keys=True) != json.dumps(
        default_boundary(plot_row),
        sort_keys=True,
    )


def detect_boundary_violation(plot_row, thresh, boundary_geojson: dict) -> bool:
    if thresh is None:
        return False

    polygon = shape(json.loads(json.dumps(boundary_geojson)))
    rows, cols = thresh.shape[:2]
    changed_points = []

    for row_index in range(rows):
        for col_index in range(cols):
            if thresh[row_index, col_index] <= 0:
                continue
            lng = _scale(col_index, 0, cols - 1, plot_row["lng"] - 0.003, plot_row["lng"] + 0.003)
            lat = _scale(row_index, 0, rows - 1, plot_row["lat"] + 0.003, plot_row["lat"] - 0.003)
            changed_points.append(Point(lng, lat))

    if not changed_points:
        return False

    outside_count = sum(1 for point in changed_points if not polygon.contains(point))
    return outside_count > max(5, int(len(changed_points) * 0.15))


def _scale(value, min_value, max_value, out_min, out_max):
    if max_value == min_value:
        return out_min
    ratio = (value - min_value) / (max_value - min_value)
    return out_min + ratio * (out_max - out_min)


def elevate_risk(risk_level: str) -> str:
    order = ["Low", "Suspicious", "Medium", "High"]
    try:
        index = order.index(risk_level)
    except ValueError:
        return "High"
    return order[min(index + 1, len(order) - 1)]
