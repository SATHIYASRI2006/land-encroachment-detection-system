from __future__ import annotations

import json
from difflib import SequenceMatcher

from shapely.geometry import shape

from core.db import db_session


def _text_similarity(first: str | None, second: str | None) -> float:
    left = (first or "").strip().lower()
    right = (second or "").strip().lower()
    if not left or not right:
      return 0.0
    return SequenceMatcher(a=left, b=right).ratio()


def _normalize_survey(value: str | None) -> str:
    return "".join(char for char in (value or "").lower() if char.isalnum())


def _load_reference_layers(conn):
    boundaries = {
        row["plot_id"]: json.loads(row["boundary_geojson"])
        for row in conn.execute(
            "SELECT plot_id, boundary_geojson FROM plot_boundaries"
        ).fetchall()
    }

    monitored_plots = []
    for plot in conn.execute("SELECT * FROM plots ORDER BY id").fetchall():
        boundary_geojson = boundaries.get(plot["id"])
        if not boundary_geojson:
            continue
        monitored_plots.append(
            {
                "id": plot["id"],
                "source": "monitored_plot",
                "location_name": plot["location_name"],
                "survey_no": plot["survey_no"],
                "owner_name": plot["owner_name"],
                "land_type": "government" if "government" in (plot["owner_name"] or "").lower() else "plot",
                "boundary_geojson": boundary_geojson,
                "geometry": shape(boundary_geojson),
            }
        )

    official_parcels = []
    for parcel in conn.execute("SELECT * FROM official_parcels ORDER BY parcel_id").fetchall():
        geometry_geojson = json.loads(parcel["geometry_geojson"])
        official_parcels.append(
            {
                "id": parcel["parcel_id"],
                "source": "official_parcel",
                "location_name": parcel["survey_number"],
                "survey_no": parcel["survey_number"],
                "owner_name": parcel["owner_name"],
                "land_type": "private_parcel",
                "boundary_geojson": geometry_geojson,
                "geometry": shape(geometry_geojson),
            }
        )

    government_layers = []
    for layer in conn.execute(
        "SELECT * FROM government_land_layer ORDER BY layer_id"
    ).fetchall():
        geometry_geojson = json.loads(layer["geometry_geojson"])
        government_layers.append(
            {
                "id": layer["layer_id"],
                "source": "government_layer",
                "location_name": layer["layer_name"],
                "survey_no": layer["survey_number"],
                "owner_name": "Government",
                "land_type": layer["land_type"],
                "boundary_geojson": geometry_geojson,
                "geometry": shape(geometry_geojson),
            }
        )

    return monitored_plots + official_parcels + government_layers


def _build_reference_match(reference, claim_geometry):
    intersection_area = claim_geometry.intersection(reference["geometry"]).area
    overlap_percent = round(
        (intersection_area / max(claim_geometry.area, 1e-9)) * 100,
        2,
    )
    centroid_distance = claim_geometry.centroid.distance(reference["geometry"].centroid)
    return {
        "reference": reference,
        "intersection_area": intersection_area,
        "overlap_percent": overlap_percent,
        "centroid_distance": centroid_distance,
    }


def _risk_from_matches(claim_payload: dict, matches: list[dict]) -> dict:
    claimant_survey = claim_payload.get("survey_no")
    claimant_owner = claim_payload.get("claimed_owner_name")
    adjacent_plot_id = (claim_payload.get("adjacent_plot_id") or "").strip().lower()

    risk_score = 0
    conflict_reasons = []
    matched = matches[0] if matches else None
    nearest = matched["reference"] if matched else None

    if matched:
        reference = matched["reference"]
        overlap_percent = matched["overlap_percent"]
        risk_score += 30
        risk_score += min(int(overlap_percent * 0.6), 45)
        conflict_reasons.append(
            f"Claim overlaps {reference['source'].replace('_', ' ')} {reference['id']} ({reference['location_name']})."
        )

        if reference["source"] == "government_layer":
            risk_score += 25
            conflict_reasons.append("Protected government land layer is affected by the submitted boundary.")

        normalized_claim_survey = _normalize_survey(claimant_survey)
        normalized_reference_survey = _normalize_survey(reference.get("survey_no"))
        if normalized_claim_survey and normalized_reference_survey:
            if normalized_claim_survey != normalized_reference_survey:
                risk_score += 18
                conflict_reasons.append("Survey number differs from the closest official parcel record.")
        elif claimant_survey and not normalized_reference_survey:
            risk_score += 8

        owner_similarity = _text_similarity(claimant_owner, reference.get("owner_name"))
        if claimant_owner and reference.get("owner_name") and owner_similarity < 0.45:
            risk_score += 15
            conflict_reasons.append("Claimed owner name conflicts with the matched parcel owner.")

        if adjacent_plot_id:
            if adjacent_plot_id != str(reference["id"]).strip().lower():
                risk_score += 12
                conflict_reasons.append("Selected adjacent plot does not align with the strongest spatial match.")
    else:
        conflict_reasons.append("No direct overlap detected with protected or official parcel layers.")

    if matches:
        secondary_matches = matches[1:3]
        if secondary_matches:
            risk_score += 6 * len(secondary_matches)
            conflict_reasons.append("Multiple nearby parcel intersections increase conflict probability.")

    risk_score = min(risk_score, 100)
    top_overlap = matched["overlap_percent"] if matched else 0.0

    if risk_score >= 70 or top_overlap >= 35:
        risk_flag = "High"
    elif risk_score >= 35 or top_overlap > 0:
        risk_flag = "Medium"
    else:
        risk_flag = "Low"

    return {
        "risk_flag": risk_flag,
        "risk_score": risk_score,
        "overlap_percent": top_overlap,
        "conflict_reason": " ".join(conflict_reasons),
        "matched_plot_id": nearest["id"] if nearest else None,
        "matched_plot_name": nearest["location_name"] if nearest else None,
        "matched_source": nearest["source"] if nearest else None,
    }


def evaluate_ownership_claim(conn, claim_payload: dict) -> dict:
    claim_geometry = shape(claim_payload["claim_boundary_geojson"])
    references = _load_reference_layers(conn)

    matches = []
    for reference in references:
        if not claim_geometry.intersects(reference["geometry"]):
            continue
        intersection_area = claim_geometry.intersection(reference["geometry"]).area
        if intersection_area <= 0:
            continue
        matches.append(_build_reference_match(reference, claim_geometry))

    matches.sort(
        key=lambda item: (
            -item["overlap_percent"],
            item["centroid_distance"],
        )
    )

    return _risk_from_matches(claim_payload, matches)


def _payload_from_row(row) -> dict:
    return {
        "claimant_name": row["claimant_name"],
        "claimed_plot_label": row["claimed_plot_label"],
        "claimed_owner_name": row["claimed_owner_name"],
        "claim_reference": row["claim_reference"],
        "survey_no": row["survey_no"],
        "adjacent_plot_id": row["adjacent_plot_id"],
        "claim_boundary_geojson": json.loads(row["claim_boundary_geojson"]),
        "notes": row["notes"],
    }


def create_ownership_claim(db_path: str, claim_payload: dict) -> dict:
    with db_session(db_path) as conn:
        evaluation = evaluate_ownership_claim(conn, claim_payload)
        cursor = conn.execute(
            """
            INSERT INTO ownership_claims (
                claimant_name, claimed_plot_label, claimed_owner_name, claim_reference,
                survey_no, adjacent_plot_id, claim_boundary_geojson, status, risk_flag,
                overlap_percent, conflict_reason, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Under Review', ?, ?, ?, ?)
            """,
            (
                claim_payload["claimant_name"],
                claim_payload["claimed_plot_label"],
                claim_payload.get("claimed_owner_name"),
                claim_payload.get("claim_reference"),
                claim_payload.get("survey_no"),
                claim_payload.get("adjacent_plot_id"),
                json.dumps(claim_payload["claim_boundary_geojson"]),
                evaluation["risk_flag"],
                evaluation["overlap_percent"],
                evaluation["conflict_reason"],
                claim_payload.get("notes"),
            ),
        )
        row = conn.execute(
            "SELECT * FROM ownership_claims WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()

    return serialize_claim(row, evaluation)


def list_ownership_claims(db_path: str) -> list[dict]:
    with db_session(db_path) as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM ownership_claims
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()
        serialized = []
        for row in rows:
            evaluation = evaluate_ownership_claim(conn, _payload_from_row(row))
            serialized.append(serialize_claim(row, evaluation))
    return serialized


def update_ownership_claim(db_path: str, claim_id: int, payload: dict) -> dict | None:
    updates = []
    values = []
    for field in ("status", "notes"):
        if field in payload:
            updates.append(f"{field} = ?")
            values.append(payload[field])

    if not updates:
        with db_session(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM ownership_claims WHERE id = ?",
                (claim_id,),
            ).fetchone()
            evaluation = evaluate_ownership_claim(conn, _payload_from_row(row)) if row else None
        return serialize_claim(row, evaluation) if row else None

    updates.append("updated_at = CURRENT_TIMESTAMP")
    values.append(claim_id)

    with db_session(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM ownership_claims WHERE id = ?",
            (claim_id,),
        ).fetchone()
        if not existing:
            return None
        conn.execute(
            f"UPDATE ownership_claims SET {', '.join(updates)} WHERE id = ?",
            values,
        )
        row = conn.execute(
            "SELECT * FROM ownership_claims WHERE id = ?",
            (claim_id,),
        ).fetchone()
        evaluation = evaluate_ownership_claim(conn, _payload_from_row(row))
    return serialize_claim(row, evaluation)


def serialize_claim(row, evaluation: dict | None = None) -> dict:
    if row is None:
        return {}

    claim = dict(row)
    claim["claim_boundary_geojson"] = json.loads(claim["claim_boundary_geojson"])
    if evaluation:
        claim["risk_flag"] = evaluation.get("risk_flag", claim.get("risk_flag"))
        claim["overlap_percent"] = evaluation.get(
            "overlap_percent",
            claim.get("overlap_percent"),
        )
        claim["conflict_reason"] = evaluation.get(
            "conflict_reason",
            claim.get("conflict_reason"),
        )
        claim["risk_score"] = evaluation.get("risk_score", 0)
        claim["matched_plot_id"] = evaluation.get("matched_plot_id")
        claim["matched_plot_name"] = evaluation.get("matched_plot_name")
        claim["matched_source"] = evaluation.get("matched_source")
    return claim
