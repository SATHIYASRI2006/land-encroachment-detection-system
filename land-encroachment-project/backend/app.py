from __future__ import annotations

import json

from dotenv import load_dotenv
from flask import Flask, render_template, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO
from sqlite3 import IntegrityError

from core.auth import authenticate_user, create_token, require_auth
from core.config import load_settings
from core.db import create_user, db_session, ensure_directories, ensure_schema
from core.logging_config import configure_logging
from core.responses import error_response, success_response
from services.analysis_service import analyze_plot as run_analysis
from services.location_service import (
    coordinate_validation_message,
    is_valid_chennai_coordinate,
)
from services.ownership_service import (
    create_ownership_claim,
    list_ownership_claims,
    update_ownership_claim,
)
from services.plot_service import save_uploaded_image, serialize_plot, upsert_plot_bundle
from services.realtime_ingest_service import get_realtime_status, start_realtime_ingestion
from services.registration_validation_service import (
    extract_registration_preview,
    get_official_parcel_by_survey,
    list_registration_requests,
    list_sample_registration_requests,
    verify_registration_request,
)
from services.report_service import generate_report
from services.scheduler_service import start_auto_monitor

load_dotenv()

settings = load_settings()
logger = configure_logging()
ensure_directories(settings.data_folder, settings.reports_folder)
ensure_directories(
    settings.realtime_inbox_folder,
    settings.realtime_archive_folder,
    settings.realtime_failed_folder,
)
ensure_schema(settings.db_path)

app = Flask(__name__)
app.config["SECRET_KEY"] = settings.secret_key
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")


def analyze_plot_data(plot_id: str, emit_socket=True):
    return run_analysis(settings, logger, socketio, plot_id, emit_socket=emit_socket)


def _serialize_case(row):
    return {
        "id": row["id"],
        "plot_id": row["plot_id"],
        "risk_level": row["risk_level"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "notes": row["notes"],
    }


def _serialize_alert(row):
    return {
        "id": row["id"],
        "plot_id": row["plot_id"],
        "risk_level": row["risk_level"],
        "message": row["message"],
        "created_at": row["created_at"],
        "is_read": bool(row["is_read"]),
    }


def _claim_payload_from_request(payload):
    required = {"claimant_name", "claimed_plot_label", "claim_boundary_geojson"}
    missing = [field for field in required if not payload.get(field)]
    if missing:
        return None, missing

    return {
        "claimant_name": (payload.get("claimant_name") or "").strip(),
        "claimed_plot_label": (payload.get("claimed_plot_label") or "").strip(),
        "claimed_owner_name": (payload.get("claimed_owner_name") or "").strip(),
        "claim_reference": (payload.get("claim_reference") or "").strip(),
        "survey_no": (payload.get("survey_no") or "").strip(),
        "adjacent_plot_id": (payload.get("adjacent_plot_id") or "").strip(),
        "claim_boundary_geojson": payload.get("claim_boundary_geojson"),
        "notes": (payload.get("notes") or "").strip(),
    }, []


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/v1/login", methods=["POST"])
def login():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    user = authenticate_user(settings.db_path, username, password)
    if not user:
        return error_response("Invalid username or password", 401)

    token = create_token(settings.secret_key, settings.jwt_exp_minutes, user)
    return success_response(
        {
            "token": token,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "full_name": user["full_name"],
            },
        }
    )


@app.route("/api/v1/register", methods=["POST"])
def register():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip().lower()
    password = payload.get("password") or ""
    full_name = (payload.get("full_name") or "").strip()

    if len(full_name) < 3:
        return error_response("Full name must contain at least 3 characters")
    if len(username) < 4 or not username.replace("_", "").replace(".", "").isalnum():
        return error_response(
            "Username must be at least 4 characters and use letters, numbers, dots, or underscores"
        )
    if len(password) < 8:
        return error_response("Password must contain at least 8 characters")

    try:
        with db_session(settings.db_path) as conn:
            user_row = create_user(
                conn,
                username=username,
                password=password,
                role="viewer",
                full_name=full_name,
            )
    except IntegrityError:
        return error_response("Username already exists", 409)

    user = {
        "id": user_row["id"],
        "username": user_row["username"],
        "role": user_row["role"],
        "full_name": user_row["full_name"] or user_row["username"],
    }
    token = create_token(settings.secret_key, settings.jwt_exp_minutes, user)
    return success_response({"token": token, "user": user}, 201)


@app.route("/api/v1/plots")
@require_auth(settings, roles={"admin", "officer", "viewer"})
def plots():
    with db_session(settings.db_path) as conn:
        rows = conn.execute("SELECT * FROM plots ORDER BY id").fetchall()
    return {"plots": [serialize_plot(settings.db_path, row) for row in rows]}


@app.route("/api/v1/analyze/<plot_id>")
@require_auth(settings, roles={"admin", "officer", "viewer"})
def analyze_plot(plot_id):
    try:
        return analyze_plot_data(plot_id)
    except ValueError as exc:
        return {"error": str(exc)}, 400
    except Exception as exc:
        logger.exception("Analyze failed for plot %s: %s", plot_id, exc)
        return {"error": str(exc)}, 500


@app.route("/api/v1/admin/upload-plot", methods=["POST"])
@require_auth(settings, roles={"admin", "officer"})
def upload_plot_bundle():
    plot_id = (request.form.get("plot_id") or "").strip()
    if not plot_id:
        return error_response("plot_id is required")

    try:
        metadata = {
            "plot_id": plot_id,
            "lat": float(request.form.get("lat") or 0),
            "lng": float(request.form.get("lng") or 0),
            "location_name": (request.form.get("location_name") or "").strip() or plot_id,
            "area": (request.form.get("area") or "").strip(),
            "survey_no": (request.form.get("survey_no") or "").strip(),
            "owner_name": (request.form.get("owner_name") or "").strip(),
            "village": (request.form.get("village") or "").strip(),
            "district": (request.form.get("district") or "").strip(),
            "operator_note": (request.form.get("operator_note") or "").strip(),
        }
    except ValueError:
        return error_response("Latitude and longitude must be valid numbers")

    if not is_valid_chennai_coordinate(metadata["lat"], metadata["lng"]):
        return error_response(coordinate_validation_message())

    boundary_geojson = request.form.get("boundary_geojson")
    if boundary_geojson:
        try:
            metadata["boundary_geojson"] = json.loads(boundary_geojson)
        except json.JSONDecodeError:
            return error_response("boundary_geojson must be valid JSON")

    allowed_years = {2021, 2022, 2023, 2024}
    uploaded_images = {}
    try:
        for key, file_storage in request.files.items():
            if not key.startswith("image_") or not file_storage.filename:
                continue
            year = key.split("_", 1)[1]
            if not year.isdigit():
                return error_response(f"Invalid image field: {key}")
            year_value = int(year)
            if year_value not in allowed_years:
                return error_response("Only 2021, 2022, 2023, and 2024 images are allowed")
            uploaded_images[year_value] = save_uploaded_image(
                settings, plot_id, year, file_storage
            )
    except ValueError as exc:
        return error_response(str(exc))

    if not uploaded_images:
        return error_response("Upload at least one yearly image")

    upsert_plot_bundle(settings, metadata, uploaded_images)

    analysis = None
    try:
        analysis = analyze_plot_data(plot_id)
    except ValueError:
        analysis = None

    with db_session(settings.db_path) as conn:
        row = conn.execute("SELECT * FROM plots WHERE id = ?", (plot_id,)).fetchone()

    return success_response(
        {
            "message": "Plot uploaded successfully",
            "plot": serialize_plot(settings.db_path, row) if row else None,
            "uploaded_years": sorted(uploaded_images.keys()),
            "analysis": analysis,
        }
    )


@app.route("/api/v1/cases", methods=["POST"])
@require_auth(settings, roles={"admin", "officer"})
def create_case():
    payload = request.get_json(silent=True) or {}
    required = {"plot_id", "risk_level"}
    missing = [field for field in required if not payload.get(field)]
    if missing:
        return error_response("Missing required fields", details={"fields": missing})

    status = payload.get("status") or "Open"
    notes = payload.get("notes")
    with db_session(settings.db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO cases (plot_id, risk_level, status, notes)
            VALUES (?, ?, ?, ?)
            """,
            (payload["plot_id"], payload["risk_level"], status, notes),
        )
        row = conn.execute(
            "SELECT * FROM cases WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return success_response(_serialize_case(row), 201)


@app.route("/api/v1/cases", methods=["GET"])
@require_auth(settings, roles={"admin", "officer", "viewer"})
def list_cases():
    with db_session(settings.db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM cases ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return success_response([_serialize_case(row) for row in rows])


@app.route("/api/v1/cases/<int:case_id>", methods=["GET"])
@require_auth(settings, roles={"admin", "officer", "viewer"})
def get_case(case_id):
    with db_session(settings.db_path) as conn:
        row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    if not row:
        return error_response("Case not found", 404)
    return success_response(_serialize_case(row))


@app.route("/api/v1/cases/<int:case_id>", methods=["PATCH"])
@require_auth(settings, roles={"admin", "officer"})
def update_case(case_id):
    payload = request.get_json(silent=True) or {}
    updates = []
    values = []
    for field in ("risk_level", "status", "notes"):
        if field in payload:
            updates.append(f"{field} = ?")
            values.append(payload[field])

    if not updates:
        return error_response("No updates provided")

    updates.append("updated_at = CURRENT_TIMESTAMP")
    values.append(case_id)

    with db_session(settings.db_path) as conn:
        existing = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        if not existing:
            return error_response("Case not found", 404)
        conn.execute(
            f"UPDATE cases SET {', '.join(updates)} WHERE id = ?",
            values,
        )
        row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    return success_response(_serialize_case(row))


@app.route("/api/v1/alerts", methods=["GET"])
@require_auth(settings, roles={"admin", "officer", "viewer"})
def list_alerts():
    with db_session(settings.db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM alerts ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return success_response([_serialize_alert(row) for row in rows])


@app.route("/api/v1/alerts/<int:alert_id>", methods=["PATCH"])
@require_auth(settings, roles={"admin", "officer"})
def update_alert(alert_id):
    payload = request.get_json(silent=True) or {}
    is_read = payload.get("is_read")
    if is_read is None:
        return error_response("is_read is required")

    with db_session(settings.db_path) as conn:
        existing = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        if not existing:
            return error_response("Alert not found", 404)
        conn.execute(
            "UPDATE alerts SET is_read = ? WHERE id = ?",
            (int(bool(is_read)), alert_id),
        )
        row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
    return success_response(_serialize_alert(row))


@app.route("/api/v1/realtime/status", methods=["GET"])
@require_auth(settings, roles={"admin", "officer"})
def realtime_status():
    return success_response(get_realtime_status(settings))


@app.route("/api/v1/claims", methods=["GET"])
@require_auth(settings, roles={"admin", "officer"})
def claims():
    return success_response(list_ownership_claims(settings.db_path))


@app.route("/api/v1/claims", methods=["POST"])
@require_auth(settings, roles={"admin", "officer"})
def create_claim():
    payload = request.get_json(silent=True) or {}
    claim_payload, missing = _claim_payload_from_request(payload)
    if missing:
        return error_response("Missing required fields", details={"fields": missing})

    try:
        claim = create_ownership_claim(settings.db_path, claim_payload)
    except Exception as exc:
        logger.exception("Failed to create ownership claim: %s", exc)
        return error_response("Failed to evaluate ownership claim", 500)
    return success_response(claim, 201)


@app.route("/api/v1/claims/<int:claim_id>", methods=["PATCH"])
@require_auth(settings, roles={"admin", "officer"})
def patch_claim(claim_id):
    payload = request.get_json(silent=True) or {}
    claim = update_ownership_claim(settings.db_path, claim_id, payload)
    if not claim:
        return error_response("Claim not found", 404)
    return success_response(claim)


@app.route("/api/v1/verify-registration", methods=["POST"])
@require_auth(settings, roles={"admin", "officer"})
def verify_registration():
    payload = request.form.to_dict() if request.form else {}
    if not payload:
        payload = request.get_json(silent=True) or {}

    file_storage = request.files.get("uploaded_sale_deed")
    if "boundary_coordinates" in payload and isinstance(payload["boundary_coordinates"], str):
        try:
            payload["boundary_coordinates"] = json.loads(payload["boundary_coordinates"])
        except json.JSONDecodeError:
            return error_response("boundary_coordinates must be valid JSON")

    required = {"seller_name", "buyer_name", "survey_number", "boundary_coordinates"}
    missing = [field for field in required if not payload.get(field) and field != "boundary_coordinates"]
    if not payload.get("boundary_coordinates") and file_storage is None:
        missing.append("boundary_coordinates")
    if missing:
        return error_response("Missing required fields", details={"fields": missing})

    try:
        result = verify_registration_request(settings, payload, file_storage=file_storage)
    except ValueError as exc:
        return error_response(str(exc), 400)
    except Exception as exc:
        logger.exception("Registration verification failed: %s", exc)
        return error_response("Failed to verify registration", 500)
    return success_response(result, 201)


@app.route("/api/v1/verify-registration/extract", methods=["POST"])
@require_auth(settings, roles={"admin", "officer"})
def extract_registration():
    file_storage = request.files.get("uploaded_sale_deed")
    if file_storage is None or not (file_storage.filename or "").strip():
        return error_response("Upload a deed file to extract registration details", 400)

    try:
        result = extract_registration_preview(file_storage)
    except ValueError as exc:
        return error_response(str(exc), 400)
    except Exception as exc:
        logger.exception("Registration extraction failed: %s", exc)
        return error_response("Failed to extract registration details", 500)
    return success_response(result)


@app.route("/api/v1/official-parcels/<path:survey_number>", methods=["GET"])
@require_auth(settings, roles={"admin", "officer"})
def official_parcel_lookup(survey_number):
    record = get_official_parcel_by_survey(settings, survey_number)
    if not record:
        return error_response("Official parcel not found", 404)
    return success_response(record)


@app.route("/api/v1/verify-registration/sample-requests", methods=["GET"])
@require_auth(settings, roles={"admin", "officer"})
def registration_samples():
    return success_response(list_sample_registration_requests(settings))


@app.route("/api/v1/verify-registration/records", methods=["GET"])
@require_auth(settings, roles={"admin", "officer"})
def registration_records():
    return success_response(list_registration_requests(settings))


@app.route("/api/v1/plot/<plot_id>/history", methods=["GET"])
@require_auth(settings, roles={"admin", "officer", "viewer"})
def plot_history(plot_id):
    with db_session(settings.db_path) as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM plot_history
            WHERE plot_id = ?
            ORDER BY timestamp ASC, id ASC
            """,
            (plot_id,),
        ).fetchall()

    history_rows = [
        {
            "id": row["id"],
            "plot_id": row["plot_id"],
            "change_percent": row["change_percent"],
            "risk_level": row["risk_level"],
            "confidence": row["confidence"],
            "boundary_violation": bool(row["boundary_violation"]),
            "timestamp": row["timestamp"],
        }
        for row in rows
    ]
    average_change = (
        round(sum(item["change_percent"] for item in history_rows) / len(history_rows), 2)
        if history_rows
        else 0
    )
    high_risk_events = sum(1 for item in history_rows if item["risk_level"] == "High")

    return success_response(
        {
            "plot_id": plot_id,
            "history": history_rows,
            "aggregation": {
                "average_change": average_change,
                "high_risk_count": high_risk_events,
                "total_events": len(history_rows),
            },
        }
    )


@app.route("/api/v1/report/<plot_id>", methods=["GET"])
@require_auth(settings, roles={"admin", "officer", "viewer"})
def report(plot_id):
    try:
        analysis = analyze_plot_data(plot_id, emit_socket=False)
        report_path = generate_report(settings, plot_id, analysis)
    except ValueError as exc:
        return error_response(str(exc), 400)
    except ModuleNotFoundError as exc:
        logger.warning("Report dependency missing: %s", exc)
        return error_response(
            "PDF reporting dependency is not installed",
            500,
            details={"missing_module": str(exc)},
        )
    except Exception as exc:
        logger.exception("Failed to generate report for plot %s: %s", plot_id, exc)
        return error_response("Failed to generate report", 500)

    return success_response(
        {
            "plot_id": plot_id,
            "report_path": report_path,
            "filename": f"{plot_id}_report.pdf",
            "download_url": f"/reports/{plot_id}_report.pdf",
        }
    )


@app.route("/static/data/<path:filename>")
def serve_image(filename):
    return send_from_directory(settings.data_folder, filename)


@app.route("/reports/<path:filename>")
def serve_report(filename):
    return send_from_directory(settings.reports_folder, filename, as_attachment=True)


auto_monitor = start_auto_monitor(
    settings,
    logger,
    lambda plot_id, emit_socket=False: analyze_plot_data(plot_id, emit_socket=emit_socket),
)
realtime_ingestion = start_realtime_ingestion(
    settings,
    logger,
    lambda plot_id, emit_socket=False: analyze_plot_data(plot_id, emit_socket=emit_socket),
)


if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
