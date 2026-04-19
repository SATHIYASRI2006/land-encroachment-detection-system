from __future__ import annotations

import json
import os
import re
from io import BytesIO
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
SELLER_PATTERNS = [
    re.compile(r"(?:seller|vendor|executant|transferor)\s*[:#-]?\s*([^\n,;]+)", re.IGNORECASE),
]
BUYER_PATTERNS = [
    re.compile(r"(?:buyer|purchaser|claimant|transferee)\s*[:#-]?\s*([^\n,;]+)", re.IGNORECASE),
]
VILLAGE_REGEX = re.compile(r"(?:village)\s*[:#-]?\s*([^\n,;]+)", re.IGNORECASE)
DISTRICT_REGEX = re.compile(r"(?:district)\s*[:#-]?\s*([^\n,;]+)", re.IGNORECASE)
PARTY_LABEL_WORDS = {
    "seller",
    "buyer",
    "vendor",
    "purchaser",
    "executant",
    "claimant",
    "transferee",
    "transferor",
}
NAME_STOP_WORDS = {
    "son",
    "daughter",
    "wife",
    "husband",
    "aged",
    "residing",
    "resident",
    "address",
    "survey",
    "plot",
    "area",
    "village",
    "district",
    "boundary",
    "coordinates",
    "extent",
}


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
    document_values = _extract_document_values(file_storage)

    survey_number = (payload.get("survey_number") or document_values.get("survey_number") or "").strip()
    area = _safe_float(payload.get("area"))
    if area is None:
        area = document_values.get("area")
    coordinates = payload.get("boundary_coordinates") or document_values.get("coordinates") or []
    if isinstance(coordinates, str):
        coordinates = json.loads(coordinates)
    boundary_geojson = coordinates_to_geojson(coordinates) if coordinates else None

    seller_name = (payload.get("seller_name") or document_values.get("seller_name") or "").strip()
    buyer_name = (payload.get("buyer_name") or document_values.get("buyer_name") or "").strip()
    village = (payload.get("village") or document_values.get("village") or "").strip()
    district = (payload.get("district") or document_values.get("district") or "").strip()

    return {
        "seller_name": seller_name,
        "buyer_name": buyer_name,
        "survey_number": survey_number,
        "area": area,
        "village": village,
        "district": district,
        "coordinates": coordinates or [],
        "boundary_geojson": boundary_geojson,
        "ocr_text_excerpt": document_values.get("ocr_text_excerpt", ""),
        "field_confidence": _build_field_confidence(
            payload=payload,
            document_values=document_values,
            coordinates=coordinates or [],
        ),
        "missing_fields": _collect_missing_fields(
            seller_name=seller_name,
            buyer_name=buyer_name,
            survey_number=survey_number,
            coordinates=coordinates or [],
        ),
    }


def run_ocr(file_storage) -> str:
    file_name = (file_storage.filename or "").strip()
    if not file_name:
        return ""

    extension = os.path.splitext(file_name)[1].lower()
    file_storage.stream.seek(0)
    raw_bytes = file_storage.read()
    file_storage.stream.seek(0)

    if extension == ".pdf":
        return _extract_text_from_pdf(raw_bytes)
    if extension in {".txt", ".md"}:
        return raw_bytes.decode("utf-8", errors="ignore")
    if extension in {".png", ".jpg", ".jpeg"}:
        return _extract_text_from_image(raw_bytes)

    raise ValueError("Upload a PDF, text file, or image deed for extraction")


def parse_survey_number(raw_text: str) -> str:
    match = SURVEY_REGEX.search(raw_text or "")
    return match.group(1).strip() if match else ""


def parse_area(raw_text: str) -> float | None:
    match = AREA_REGEX.search(raw_text or "")
    if not match:
        return None
    return _safe_float(match.group(1))


def parse_party_name(raw_text: str, patterns: list[re.Pattern[str]]) -> str:
    for pattern in patterns:
        match = pattern.search(raw_text or "")
        if match:
            candidate = _sanitize_party_candidate(match.group(1))
            if candidate:
                return candidate
    line_candidate = _parse_party_name_from_lines(raw_text, patterns)
    if line_candidate:
        return line_candidate
    return ""


def parse_location_field(raw_text: str, pattern: re.Pattern[str]) -> str:
    match = pattern.search(raw_text or "")
    return _clean_extracted_text(match.group(1)) if match else ""


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
    compact_survey = compact_survey_number(survey_number)
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
        candidate_normalized = normalize_survey_number(candidate["survey_number"])
        candidate_compact = compact_survey_number(candidate["survey_number"])
        if (
            candidate_normalized != normalized_survey
            and candidate_compact != compact_survey
        ):
            continue
        record = dict(candidate)
        record["geometry_geojson"] = json.loads(record["geometry_geojson"])
        record["geometry"] = shape(record["geometry_geojson"])
        return record

    return None


def get_official_parcel_by_survey(settings, survey_number: str) -> dict | None:
    with db_session(settings.db_path) as conn:
        record = fetch_official_parcel(conn, survey_number)
    if not record:
        return None

    coordinates = extract_boundary_coordinates(record["geometry_geojson"])
    return {
        "parcel_id": record["parcel_id"],
        "survey_number": record["survey_number"],
        "owner_name": record["owner_name"],
        "area": record["area"],
        "boundary_coordinates": coordinates,
        "geometry_geojson": record["geometry_geojson"],
    }


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
    intersection_geometry = document_polygon.intersection(official_polygon)
    intersection_area = (
        0.0 if intersection_geometry.is_empty or intersection_geometry.area <= 0 else intersection_geometry.area
    )
    union_area = document_polygon.union(official_polygon).area

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
    expansion_ratio = expansion_area / max(official_area_raw, 1e-9)
    boundary_expansion = expansion_ratio > 0.02
    missing_geometry = official_polygon.difference(document_polygon)
    missing_area = 0.0 if missing_geometry.is_empty else missing_geometry.area
    official_coverage_ratio = intersection_area / max(official_area_raw, 1e-9)
    claimed_coverage_ratio = intersection_area / max(document_area_raw, 1e-9)
    geometry_similarity_ratio = intersection_area / max(union_area, 1e-9)

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
    review_reasons = build_review_reasons(
        area_mismatch_ratio=area_mismatch_ratio,
        claimed_coverage_ratio=claimed_coverage_ratio,
        official_coverage_ratio=official_coverage_ratio,
        geometry_similarity_ratio=geometry_similarity_ratio,
        boundary_expansion_ratio=expansion_ratio,
        government_land_overlap=overlap_area > 0,
    )

    return {
        "area_mismatch": area_mismatch,
        "area_mismatch_ratio": round(area_mismatch_ratio, 4),
        "boundary_expansion": boundary_expansion,
        "boundary_expansion_area": round(expansion_area, 10),
        "boundary_expansion_ratio": round(expansion_ratio, 4),
        "government_land_overlap": overlap_area > 0,
        "encroachment_area": round(overlap_area, 10),
        "document_overlap_ratio": round(document_overlap_ratio, 4),
        "overlapped_government_layers": overlapped_layers,
        "official_parcel_intersection_ratio": round(claimed_coverage_ratio, 4),
        "official_coverage_ratio": round(official_coverage_ratio, 4),
        "geometry_similarity_ratio": round(geometry_similarity_ratio, 4),
        "missing_official_area": round(missing_area, 10),
        "overlap_geometry_geojson": mapping(overlap_union)
        if not overlap_union.is_empty
        else None,
        "document_polygon_geojson": mapping(document_polygon),
        "official_parcel_geojson": official_parcel["geometry_geojson"],
        "review_reasons": review_reasons,
    }


def compute_risk_score(validation: dict) -> VerificationOutcome:
    risk_score = 0
    if validation["government_land_overlap"]:
        overlap_ratio = validation.get("document_overlap_ratio", 0)
        risk_score += 75 + min(int(overlap_ratio * 40), 20)
    if validation["boundary_expansion"]:
        expansion_ratio = validation.get("boundary_expansion_ratio", 0)
        risk_score += 45 if expansion_ratio >= 0.1 else 28
    if validation["area_mismatch"]:
        mismatch_ratio = validation.get("area_mismatch_ratio", 0)
        risk_score += 20 + min(int(mismatch_ratio * 100), 15)
    geometry_similarity = validation.get("geometry_similarity_ratio", 0)
    if geometry_similarity < 0.85:
        risk_score += 20
    if geometry_similarity < 0.65:
        risk_score += 20
    if geometry_similarity < 0.45:
        risk_score += 20
    official_coverage = validation.get("official_coverage_ratio", 0)
    if official_coverage < 0.9:
        risk_score += 10
    if official_coverage < 0.7:
        risk_score += 15
    if official_coverage < 0.5:
        risk_score += 20

    risk_score = min(risk_score, 100)

    if risk_score >= 75:
        risk_level = "HIGH"
        verification_status = "REJECTED"
        recommendation = "Reject registration"
    elif risk_score >= 35:
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
                    "seller_name": extracted.get("seller_name"),
                    "buyer_name": extracted.get("buyer_name"),
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
            "seller_name": extracted.get("seller_name"),
            "buyer_name": extracted.get("buyer_name"),
            "survey_number": extracted.get("survey_number"),
            "area": extracted.get("area"),
            "village": extracted.get("village"),
            "district": extracted.get("district"),
            "coordinates": extracted.get("coordinates"),
            "ocr_text_excerpt": extracted.get("ocr_text_excerpt"),
            "field_confidence": extracted.get("field_confidence") or {},
            "missing_fields": extracted.get("missing_fields") or [],
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
            "official_coverage_ratio": validation["official_coverage_ratio"],
            "geometry_similarity_ratio": validation["geometry_similarity_ratio"],
            "overlapped_government_layers": validation["overlapped_government_layers"],
            "review_reasons": validation["review_reasons"],
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


def extract_registration_preview(file_storage) -> dict:
    extracted = extract_registration_document({}, file_storage=file_storage)
    return {
        "file_name": os.path.basename(file_storage.filename or ""),
        "extracted_fields": {
            "seller_name": extracted.get("seller_name"),
            "buyer_name": extracted.get("buyer_name"),
            "survey_number": extracted.get("survey_number"),
            "area": extracted.get("area"),
            "village": extracted.get("village"),
            "district": extracted.get("district"),
            "boundary_coordinates": extracted.get("coordinates") or [],
        },
        "field_confidence": extracted.get("field_confidence") or {},
        "missing_fields": extracted.get("missing_fields") or [],
        "ocr_text_excerpt": extracted.get("ocr_text_excerpt", ""),
    }


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def normalize_survey_number(value: str) -> str:
    raw = (value or "").strip().upper()
    raw = re.sub(
        r"^(?:SURVEY(?:\s+NUMBER)?|SURVEY\s*NO\.?|S\.?\s*NO\.?)\s*[:#-]?\s*",
        "",
        raw,
    )
    return re.sub(r"[^A-Z0-9/-]", "", raw)


def compact_survey_number(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", normalize_survey_number(value))


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


def extract_boundary_coordinates(geometry_geojson: dict) -> list[list[float]]:
    geometry_type = (geometry_geojson or {}).get("type")
    coordinates = (geometry_geojson or {}).get("coordinates") or []
    ring = []

    if geometry_type == "Polygon" and coordinates:
        ring = coordinates[0]
    elif geometry_type == "MultiPolygon" and coordinates and coordinates[0]:
        ring = coordinates[0][0]

    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]

    return [[round(point[1], 10), round(point[0], 10)] for point in ring]


def _extract_document_values(file_storage) -> dict:
    if file_storage is None or not (file_storage.filename or "").strip():
        return {}

    raw_text = run_ocr(file_storage)
    survey_number = parse_survey_number(raw_text)
    area = parse_area(raw_text)
    coordinates = parse_coordinates(raw_text)
    boundary_geojson = coordinates_to_geojson(coordinates) if coordinates else None
    seller_name = parse_party_name(raw_text, SELLER_PATTERNS)
    buyer_name = parse_party_name(raw_text, BUYER_PATTERNS)
    seller_name, buyer_name = _resolve_party_conflicts(raw_text, seller_name, buyer_name)
    return {
        "seller_name": seller_name,
        "buyer_name": buyer_name,
        "survey_number": survey_number,
        "area": area,
        "village": parse_location_field(raw_text, VILLAGE_REGEX),
        "district": parse_location_field(raw_text, DISTRICT_REGEX),
        "coordinates": coordinates or [],
        "boundary_geojson": boundary_geojson,
        "ocr_text_excerpt": raw_text[:1000],
    }


def _extract_text_from_pdf(raw_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(raw_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    extracted_text = "\n".join(pages).strip()
    if len(re.sub(r"\s+", "", extracted_text)) >= 40:
        return extracted_text

    image_text_chunks = []
    for page in reader.pages:
        try:
            for image in getattr(page, "images", []):
                image_bytes = image.data
                chunk = _extract_text_from_image(image_bytes)
                if chunk:
                    image_text_chunks.append(chunk)
        except Exception:
            continue

    merged_text = "\n".join([extracted_text, *image_text_chunks]).strip()
    return merged_text


def _extract_text_from_image(raw_bytes: bytes) -> str:
    from PIL import Image
    import pytesseract

    try:
        image = Image.open(BytesIO(raw_bytes))
        image = image.convert("RGB")
        processed_images = _build_ocr_variants(image)
        ocr_results = []
        for index, variant in enumerate(processed_images):
            config = "--oem 3 --psm 6" if index == 0 else "--oem 3 --psm 11"
            text = pytesseract.image_to_string(variant, config=config).strip()
            if text:
                ocr_results.append(text)
        return _pick_best_ocr_text(ocr_results)
    except Exception as exc:
        raise ValueError("Image OCR is unavailable on this machine") from exc


def _build_field_confidence(*, payload: dict, document_values: dict, coordinates: list[list[float]]) -> dict:
    return {
        "seller_name": _confidence_level(payload.get("seller_name"), document_values.get("seller_name")),
        "buyer_name": _confidence_level(payload.get("buyer_name"), document_values.get("buyer_name")),
        "survey_number": _confidence_level(payload.get("survey_number"), document_values.get("survey_number")),
        "area": _confidence_level(payload.get("area"), document_values.get("area")),
        "village": _confidence_level(payload.get("village"), document_values.get("village")),
        "district": _confidence_level(payload.get("district"), document_values.get("district")),
        "boundary_coordinates": "high" if len(coordinates) >= 3 and payload.get("boundary_coordinates") else (
            "medium" if len(coordinates) >= 3 else "missing"
        ),
    }


def _confidence_level(payload_value: Any, document_value: Any) -> str:
    if payload_value not in (None, ""):
        return "confirmed"
    if document_value not in (None, ""):
        return "extracted"
    return "missing"


def _collect_missing_fields(*, seller_name: str, buyer_name: str, survey_number: str, coordinates: list[list[float]]) -> list[str]:
    missing = []
    if not seller_name:
        missing.append("seller_name")
    if not buyer_name:
        missing.append("buyer_name")
    if not survey_number:
        missing.append("survey_number")
    if len(coordinates) < 3:
        missing.append("boundary_coordinates")
    return missing


def _clean_extracted_text(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", (value or "").strip())
    return cleaned.strip(" :;-")


def _sanitize_party_candidate(value: str) -> str:
    cleaned = _clean_extracted_text(value)
    if not cleaned:
        return ""

    cleaned = re.split(
        r"\b(?:seller|buyer|vendor|purchaser|executant|claimant|transferee|transferor)\b",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    cleaned = re.sub(r"\b(?:hereinafter|called|referred to as).*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.split(r"\b(?:son|daughter|wife|husband|aged|residing|resident|address)\b", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
    cleaned = _clean_extracted_text(cleaned)
    words = [word for word in re.split(r"\s+", cleaned) if word]
    if not words:
        return ""
    lowered = {re.sub(r"[^a-z]", "", word.lower()) for word in words}
    lowered.discard("")
    if lowered and lowered.issubset(PARTY_LABEL_WORDS):
        return ""
    if len(words) == 1 and re.sub(r"[^a-z]", "", words[0].lower()) in PARTY_LABEL_WORDS:
        return ""
    if any(token in NAME_STOP_WORDS for token in lowered):
        return ""
    return cleaned


def _parse_party_name_from_lines(raw_text: str, patterns: list[re.Pattern[str]]) -> str:
    labels = []
    for pattern in patterns:
        pattern_text = pattern.pattern.lower()
        for label in PARTY_LABEL_WORDS:
            if label in pattern_text and label not in labels:
                labels.append(label)

    for line in (raw_text or "").splitlines():
        normalized_line = _clean_extracted_text(line)
        if not normalized_line:
            continue
        lowered_line = normalized_line.lower()
        if not any(label in lowered_line for label in labels):
            continue
        parts = re.split(r"[:\-]", normalized_line, maxsplit=1)
        candidate = parts[1] if len(parts) == 2 else normalized_line
        for label in labels:
            candidate = re.sub(rf"\b{re.escape(label)}\b", "", candidate, flags=re.IGNORECASE)
        candidate = _sanitize_party_candidate(candidate)
        if candidate:
            return candidate
    return ""


def _resolve_party_conflicts(raw_text: str, seller_name: str, buyer_name: str) -> tuple[str, str]:
    seller = _sanitize_party_candidate(seller_name)
    buyer = _sanitize_party_candidate(buyer_name)

    if seller and buyer and seller.lower() == buyer.lower():
        seller = ""
        buyer = ""

    if not seller or not buyer:
        sentence_match = re.search(
            r"(?:between|among)\s+([A-Za-z .]+?)\s+(?:and|with)\s+([A-Za-z .]+?)(?:,|\n|who|bearing|residing|for\s+the\s+property)",
            raw_text or "",
            re.IGNORECASE,
        )
        if sentence_match:
            fallback_seller = _sanitize_party_candidate(sentence_match.group(1))
            fallback_buyer = _sanitize_party_candidate(sentence_match.group(2))
            seller = seller or fallback_seller
            buyer = buyer or fallback_buyer

    if not seller and buyer:
        split_seller, split_buyer = _split_combined_party_names(buyer)
        seller = seller or split_seller
        buyer = split_buyer or buyer

    return seller, buyer


def _split_combined_party_names(value: str) -> tuple[str, str]:
    cleaned = _clean_extracted_text(value)
    if not cleaned:
        return "", ""

    title_matches = list(re.finditer(r"\b(?:Mr|Mrs|Ms|Dr)\.?\b", cleaned, re.IGNORECASE))
    if len(title_matches) >= 2:
        split_index = title_matches[1].start()
        first = _sanitize_party_candidate(cleaned[:split_index])
        second = _sanitize_party_candidate(cleaned[split_index:])
        if first and second:
            return first, second

    words = cleaned.split()
    if len(words) >= 4:
        midpoint = len(words) // 2
        first = _sanitize_party_candidate(" ".join(words[:midpoint]))
        second = _sanitize_party_candidate(" ".join(words[midpoint:]))
        if first and second:
            return first, second

    return "", cleaned


def _build_ocr_variants(image):
    rgb_array = np.array(image)
    grayscale = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2GRAY)
    enlarged = cv2.resize(grayscale, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    denoised = cv2.GaussianBlur(enlarged, (3, 3), 0)
    adaptive = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        12,
    )
    otsu_threshold = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    from PIL import Image

    return [
        Image.fromarray(enlarged),
        Image.fromarray(adaptive),
        Image.fromarray(otsu_threshold),
    ]


def _pick_best_ocr_text(candidates: list[str]) -> str:
    if not candidates:
        return ""

    def score(text: str) -> tuple[int, int]:
        useful_chars = len(re.findall(r"[A-Za-z0-9]", text))
        keyword_hits = sum(
            1
            for keyword in ("seller", "buyer", "survey", "village", "district", "boundary")
            if keyword in text.lower()
        )
        return (keyword_hits, useful_chars)

    return max(candidates, key=score)


def build_review_reasons(
    *,
    area_mismatch_ratio: float,
    claimed_coverage_ratio: float,
    official_coverage_ratio: float,
    geometry_similarity_ratio: float,
    boundary_expansion_ratio: float,
    government_land_overlap: bool,
) -> list[str]:
    reasons = []
    if government_land_overlap:
        reasons.append("Claimed boundary overlaps protected government land.")
    if geometry_similarity_ratio < 0.65:
        reasons.append("Claimed shape differs significantly from the official parcel geometry.")
    elif geometry_similarity_ratio < 0.85:
        reasons.append("Claimed shape only partially matches the official parcel geometry.")
    if official_coverage_ratio < 0.7:
        reasons.append("Large parts of the official parcel are missing from the submitted boundary.")
    if claimed_coverage_ratio < 0.75:
        reasons.append("A substantial portion of the submitted boundary falls outside the official parcel.")
    if boundary_expansion_ratio >= 0.1:
        reasons.append("Submitted boundary expands well beyond the official parcel.")
    elif boundary_expansion_ratio >= 0.02:
        reasons.append("Submitted boundary extends beyond the official parcel.")
    if area_mismatch_ratio > 0.15:
        reasons.append("Declared area differs materially from the official record.")
    elif area_mismatch_ratio > 0.05:
        reasons.append("Declared area differs from the official record.")
    return reasons
