from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from shapely.geometry import GeometryCollection, Polygon, mapping, shape

from core.db import db_session
from services.report_service import generate_registration_report


SURVEY_REGEX = re.compile(
    r"(?:survey(?:\s*number)?|s\.?no\.?)\s*[:#-]?\s*([A-Za-z0-9./-]+)",
    re.IGNORECASE,
)
AREA_REGEX = re.compile(
    r"(?:area|extent|total\s+land\s+area)\s*[:#-]?\s*([\d,.]+)",
    re.IGNORECASE,
)
COORD_SECTION_REGEX = re.compile(
    r"(?:coordinates?|boundary)\s*[:#-]?\s*(.+)",
    re.IGNORECASE | re.DOTALL,
)
PAIR_REGEX = re.compile(r"(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)")


@dataclass(frozen=True)
class VerificationOutcome:
    risk_score: int
    risk_level: str
    verification_status: str
    recommendation: str


def verify_registration_request(settings, payload: dict, file_storage=None) -> dict:
    extracted = extract_registration_document(payload, file_storage=file_storage)
    survey_number = extracted.get("survey_number")
    if not survey_number:
        raise ValueError("Survey number is required for registration verification")

    document_geojson = extracted.get("boundary_geojson")
    if not document_geojson:
        raise ValueError("Boundary coordinates are required for registration verification")

    document_polygon = shape(document_geojson)
    if document_polygon.is_empty or not document_polygon.is_valid:
        raise ValueError("Extracted document polygon is invalid")

    with db_session(settings.db_path) as conn:
        official_parcel = fetch_official_parcel(conn, survey_number)
        if not official_parcel:
            raise ValueError("Official parcel not found for the extracted survey number")

        government_layers = list_government_land_layers(conn)
        validation = validate_polygons(
            document_polygon=document_polygon,
            official_parcel=official_parcel,
            government_layers=government_layers,
            extracted_area=extracted.get("area"),
        )
        outcome = compute_risk_score(validation)
        request_reference = build_request_reference(payload, survey_number)
        generated_pdf_path = generate_registration_report(
            settings,
            request_reference=request_reference,
            payload=payload,
            extracted=extracted,
            official_parcel=official_parcel,
            validation=validation,
            outcome=outcome,
        )
        request_record = persist_registration_request(
            conn,
            payload=payload,
            extracted=extracted,
            outcome=outcome,
            validation=validation,
            file_storage=file_storage,
            generated_pdf_path=generated_pdf_path,
        )

    return build_verification_response(
        request_record=request_record,
        extracted=extracted,
        official_parcel=official_parcel,
        government_layers=government_layers,
        validation=validation,
        outcome=outcome,
    )


def extract_registration_document(payload: dict, file_storage=None) -> dict:
    if file_storage is not None and (file_storage.filename or "").strip():
        raw_text = run_ocr(file_storage)
        survey_number = parse_survey_number(raw_text)
        area = parse_area(raw_text)
        coordinates = parse_coordinates(raw_text)
        boundary_geojson = coordinates_to_geojson(coordinates) if coordinates else None
        return {
            "survey_number": survey_number,
            "area": area,
            "coordinates": coordinates or [],
            "boundary_geojson": boundary_geojson,
            "ocr_text_excerpt": raw_text[:1000],
        }

    survey_number = (payload.get("survey_number") or "").strip()
    area = _safe_float(payload.get("area"))
    coordinates = payload.get("boundary_coordinates") or []
    if isinstance(coordinates, str):
        coordinates = json.loads(coordinates)
    boundary_geojson = coordinates_to_geojson(coordinates) if coordinates else None

    return {
        "survey_number": survey_number,
        "area": area,
        "coordinates": coordinates or [],
        "boundary_geojson": boundary_geojson,
        "ocr_text_excerpt": "",
    }


def run_ocr(file_storage) -> str:
    raise ValueError(
        "Document OCR upload is no longer the primary workflow. Submit the structured registration fields."
    )


def parse_survey_number(raw_text: str) -> str:
    match = SURVEY_REGEX.search(raw_text or "")
    return match.group(1).strip() if match else ""


def parse_area(raw_text: str) -> float | None:
    match = AREA_REGEX.search(raw_text or "")
    if not match:
        return None
    return _safe_float(match.group(1))


def parse_coordinates(raw_text: str) -> list[list[float]]:
    if not raw_text:
        return []

    section_match = COORD_SECTION_REGEX.search(raw_text)
    coordinate_text = section_match.group(1) if section_match else raw_text
    pairs = []
    for first, second in PAIR_REGEX.findall(coordinate_text):
        pairs.append([float(first), float(second)])
    return pairs


def coordinates_to_geojson(coordinates: list[list[float]]) -> dict:
    if len(coordinates) < 3:
        raise ValueError("At least three coordinate pairs are required")

    normalized = [_normalize_coordinate_pair(pair) for pair in coordinates]
    if normalized[0] != normalized[-1]:
        normalized.append(normalized[0])

    polygon = Polygon(normalized)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.is_empty:
        raise ValueError("Unable to construct a valid polygon from the provided coordinates")

    return mapping(polygon)


def _normalize_coordinate_pair(pair: list[float] | tuple[float, float]) -> tuple[float, float]:
    first = float(pair[0])
    second = float(pair[1])
    if abs(first) > 40 and abs(second) < 40:
        lng, lat = first, second
    else:
        lat, lng = first, second
    return (lng, lat)


def fetch_official_parcel(conn, survey_number: str) -> dict | None:
    normalized_survey = normalize_survey_number(survey_number)
    row = conn.execute(
        """
        SELECT *
        FROM official_parcels
        WHERE survey_number = ?
        """,
        (survey_number,),
    ).fetchone()
    if row:
        record = dict(row)
        record["geometry_geojson"] = json.loads(record["geometry_geojson"])
        record["geometry"] = shape(record["geometry_geojson"])
        return record

    rows = conn.execute("SELECT * FROM official_parcels").fetchall()
    for candidate in rows:
        if normalize_survey_number(candidate["survey_number"]) != normalized_survey:
            continue
        record = dict(candidate)
        record["geometry_geojson"] = json.loads(record["geometry_geojson"])
        record["geometry"] = shape(record["geometry_geojson"])
        return record

    return None


def list_government_land_layers(conn) -> list[dict]:
    rows = conn.execute(
        """
        SELECT *
        FROM government_land_layer
        ORDER BY layer_id
        """
    ).fetchall()

    layers = []
    for row in rows:
        record = dict(row)
        record["geometry_geojson"] = json.loads(record["geometry_geojson"])
        record["geometry"] = shape(record["geometry_geojson"])
        layers.append(record)
    return layers


def validate_polygons(
    *,
    document_polygon,
    official_parcel: dict,
    government_layers: list[dict],
    extracted_area: float | None,
) -> dict:
    official_polygon = official_parcel["geometry"]
    document_area_raw = document_polygon.area
    official_area_raw = official_polygon.area

    extracted_area_value = _safe_float(extracted_area)
    official_area_value = _safe_float(official_parcel.get("area"))
    area_mismatch_ratio = 0.0
    area_mismatch = False

    if extracted_area_value and official_area_value:
        area_mismatch_ratio = abs(extracted_area_value - official_area_value) / max(
            official_area_value, 1e-9
        )
        area_mismatch = area_mismatch_ratio > 0.05
    else:
        area_mismatch_ratio = abs(document_area_raw - official_area_raw) / max(
            official_area_raw, 1e-9
        )
        area_mismatch = area_mismatch_ratio > 0.05

    expansion_geometry = document_polygon.difference(official_polygon)
    expansion_area = 0.0 if expansion_geometry.is_empty else expansion_geometry.area
    boundary_expansion = expansion_area > max(official_area_raw * 0.02, 1e-9)

    overlap_geometries = []
    overlap_area = 0.0
    overlapped_layers = []
    for layer in government_layers:
        if not document_polygon.intersects(layer["geometry"]):
            continue
        intersection = document_polygon.intersection(layer["geometry"])
        if intersection.is_empty or intersection.area <= 0:
            continue
        overlap_area += intersection.area
        overlap_geometries.append(intersection)
        overlapped_layers.append(
            {
                "layer_id": layer["layer_id"],
                "layer_name": layer["layer_name"],
                "land_type": layer["land_type"],
                "survey_number": layer.get("survey_number"),
                "intersection_area": round(intersection.area, 10),
            }
        )

    overlap_union = _combine_geometries(overlap_geometries)
    document_overlap_ratio = overlap_area / max(document_area_raw, 1e-9)

    return {
        "area_mismatch": area_mismatch,
        "area_mismatch_ratio": round(area_mismatch_ratio, 4),
        "boundary_expansion": boundary_expansion,
        "boundary_expansion_area": round(expansion_area, 10),
        "government_land_overlap": overlap_area > 0,
        "encroachment_area": round(overlap_area, 10),
        "document_overlap_ratio": round(document_overlap_ratio, 4),
        "overlapped_government_layers": overlapped_layers,
        "official_parcel_intersection_ratio": round(
            document_polygon.intersection(official_polygon).area / max(document_area_raw, 1e-9),
            4,
        ),
        "overlap_geometry_geojson": mapping(overlap_union)
        if not overlap_union.is_empty
        else None,
        "document_polygon_geojson": mapping(document_polygon),
        "official_parcel_geojson": official_parcel["geometry_geojson"],
    }


def compute_risk_score(validation: dict) -> VerificationOutcome:
    risk_score = 0
    if validation["government_land_overlap"]:
        overlap_ratio = validation.get("document_overlap_ratio", 0)
        risk_score += 75 + min(int(overlap_ratio * 40), 20)
    if validation["boundary_expansion"]:
        expansion_ratio = validation.get("boundary_expansion_area", 0)
        risk_score += 35 if expansion_ratio > 0 else 20
    if validation["area_mismatch"]:
        mismatch_ratio = validation.get("area_mismatch_ratio", 0)
        risk_score += 20 + min(int(mismatch_ratio * 100), 15)

    risk_score = min(risk_score, 100)

    if risk_score >= 70:
        risk_level = "HIGH"
        verification_status = "REJECTED"
        recommendation = "Reject registration"
    elif risk_score >= 40:
        risk_level = "MEDIUM"
        verification_status = "MANUAL_REVIEW"
        recommendation = "Send for manual survey verification"
    else:
        risk_level = "LOW"
        verification_status = "APPROVED"
        recommendation = "Approve registration"

    return VerificationOutcome(
        risk_score=risk_score,
        risk_level=risk_level,
        verification_status=verification_status,
        recommendation=recommendation,
    )


def persist_registration_request(
    conn,
    *,
    payload,
    extracted,
    outcome,
    validation,
    file_storage,
    generated_pdf_path,
):
    deed_name = None
    if file_storage is not None:
        deed_name = os.path.basename(file_storage.filename or "")
    deed_name = deed_name or (payload.get("uploaded_sale_deed") or "").strip() or None

    result_payload = {
        "validation": validation,
        "risk_score": outcome.risk_score,
        "risk_level": outcome.risk_level,
        "verification_status": outcome.verification_status,
        "recommendation": outcome.recommendation,
    }

    cursor = conn.execute(
        """
        INSERT INTO registration_requests (
            seller_name, buyer_name, uploaded_sale_deed, source_mode, extracted_survey_number,
            extracted_area, extracted_boundary_geojson, generated_deed_pdf, input_payload,
            risk_score, risk_level,
            verification_status, recommendation, encroachment_area,
            government_land_overlap, result_payload, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            (payload.get("seller_name") or "").strip() or "Unknown Seller",
            (payload.get("buyer_name") or "").strip() or "Unknown Buyer",
            deed_name,
            "structured_entry" if deed_name is None else "document_upload",
            extracted.get("survey_number"),
            extracted.get("area"),
            json.dumps(extracted.get("boundary_geojson")),
            os.path.basename(generated_pdf_path or "") or None,
            json.dumps(
                {
                    "survey_number": extracted.get("survey_number"),
                    "area": extracted.get("area"),
                    "coordinates": extracted.get("coordinates"),
                    "village": (payload.get("village") or "").strip(),
                    "district": (payload.get("district") or "").strip(),
                    "officer_notes": (payload.get("officer_notes") or "").strip(),
                }
            ),
            outcome.risk_score,
            outcome.risk_level,
            outcome.verification_status,
            outcome.recommendation,
            validation["encroachment_area"],
            int(validation["government_land_overlap"]),
            json.dumps(result_payload),
        ),
    )
    row = conn.execute(
        "SELECT * FROM registration_requests WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return dict(row)


def build_verification_response(
    *,
    request_record: dict,
    extracted: dict,
    official_parcel: dict,
    government_layers: list[dict],
    validation: dict,
    outcome: VerificationOutcome,
) -> dict:
    overlapped_layer_ids = {
        layer.get("layer_id") for layer in validation.get("overlapped_government_layers", [])
    }
    overlap_feature_collection = _feature_collection(
        [
            {
                "type": "Feature",
                "properties": {
                    "layer": "overlap",
                    "highlight": "red",
                    "encroachment_area": validation["encroachment_area"],
                },
                "geometry": validation["overlap_geometry_geojson"],
            }
        ]
        if validation["overlap_geometry_geojson"]
        else []
    )

    return {
        "registration_request": serialize_registration_request(request_record),
        "generated_pdf": {
            "filename": request_record.get("generated_deed_pdf"),
            "download_url": f"/reports/{request_record['generated_deed_pdf']}"
            if request_record.get("generated_deed_pdf")
            else None,
        },
        "ocr_extraction": {
            "survey_number": extracted.get("survey_number"),
            "area": extracted.get("area"),
            "coordinates": extracted.get("coordinates"),
            "ocr_text_excerpt": extracted.get("ocr_text_excerpt"),
        },
        "official_parcel": {
            "parcel_id": official_parcel["parcel_id"],
            "survey_number": official_parcel["survey_number"],
            "owner_name": official_parcel["owner_name"],
            "area": official_parcel["area"],
        },
        "validation": {
            "area_mismatch": validation["area_mismatch"],
            "area_mismatch_ratio": validation["area_mismatch_ratio"],
            "boundary_expansion": validation["boundary_expansion"],
            "boundary_expansion_area": validation["boundary_expansion_area"],
            "government_land_overlap": validation["government_land_overlap"],
            "encroachment_area": validation["encroachment_area"],
            "official_parcel_intersection_ratio": validation["official_parcel_intersection_ratio"],
            "overlapped_government_layers": validation["overlapped_government_layers"],
        },
        "result": {
            "risk_score": outcome.risk_score,
            "risk_level": outcome.risk_level,
            "verification_status": outcome.verification_status,
            "government_land_overlap": validation["government_land_overlap"],
            "encroachment_area": validation["encroachment_area"],
            "recommendation": outcome.recommendation,
        },
        "map_layers": {
            "official_parcel": _feature_collection(
                [
                    {
                        "type": "Feature",
                        "properties": {
                            "layer": "official_parcel",
                            "survey_number": official_parcel["survey_number"],
                            "owner_name": official_parcel["owner_name"],
                            "style": {"color": "#2563eb"},
                        },
                        "geometry": official_parcel["geometry_geojson"],
                    }
                ]
            ),
            "claimed_boundary": _feature_collection(
                [
                    {
                        "type": "Feature",
                        "properties": {
                            "layer": "claimed_boundary",
                            "survey_number": extracted.get("survey_number"),
                            "style": {"color": "#f59e0b"},
                        },
                        "geometry": validation["document_polygon_geojson"],
                    }
                ]
            ),
            "government_land": _feature_collection(
                [
                    {
                        "type": "Feature",
                        "properties": {
                            "layer": "government_land",
                            "layer_id": layer["layer_id"],
                            "layer_name": layer["layer_name"],
                            "land_type": layer["land_type"],
                            "style": {"color": "#dc2626"},
                        },
                        "geometry": layer["geometry_geojson"],
                    }
                    for layer in government_layers
                    if layer["layer_id"] in overlapped_layer_ids
                ]
            ),
            "overlap_highlight": overlap_feature_collection,
        },
    }


def serialize_registration_request(row: dict) -> dict:
    record = dict(row)
    if record.get("extracted_boundary_geojson"):
        record["extracted_boundary_geojson"] = json.loads(record["extracted_boundary_geojson"])
    if record.get("input_payload"):
        record["input_payload"] = json.loads(record["input_payload"])
    if record.get("result_payload"):
        record["result_payload"] = json.loads(record["result_payload"])
    record["government_land_overlap"] = bool(record.get("government_land_overlap"))
    return record


def list_sample_registration_requests(settings) -> list[dict]:
    dataset_path = os.path.join(settings.base_dir, "sample_registration_dataset.json")
    if not os.path.exists(dataset_path):
        return []
    with open(dataset_path, "r", encoding="utf-8") as handle:
        dataset = json.load(handle)
    return dataset.get("sample_registration_requests", [])


def list_registration_requests(settings, limit: int = 50) -> list[dict]:
    with db_session(settings.db_path) as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM registration_requests
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [serialize_registration_request(dict(row)) for row in rows]


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def normalize_survey_number(value: str) -> str:
    return re.sub(r"[^A-Z0-9/-]", "", (value or "").upper())


def build_request_reference(payload: dict, survey_number: str) -> str:
    buyer = re.sub(r"[^A-Z0-9]", "", (payload.get("buyer_name") or "").upper())[:8] or "BUYER"
    survey = normalize_survey_number(survey_number).replace("/", "-")[:20] or "SURVEY"
    return f"{survey}_{buyer}"


def _combine_geometries(geometries: list) -> GeometryCollection | Polygon:
    if not geometries:
        return GeometryCollection()

    merged = geometries[0]
    for geometry in geometries[1:]:
        merged = merged.union(geometry)
    return merged


def _feature_collection(features: list[dict]) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [feature for feature in features if feature.get("geometry")],
    }
