from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from werkzeug.security import generate_password_hash


def create_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_session(db_path: str) -> Iterator[sqlite3.Connection]:
    conn = create_connection(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def ensure_directories(*directories: str) -> None:
    for directory in directories:
        os.makedirs(directory, exist_ok=True)


def ensure_schema(db_path: str) -> None:
    with db_session(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS plots (
                id TEXT PRIMARY KEY,
                lat REAL,
                lng REAL,
                location_name TEXT,
                status TEXT,
                last_change REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plot_id TEXT,
                risk TEXT,
                change REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plot_id TEXT,
                year INTEGER,
                image_path TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS plot_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plot_id TEXT NOT NULL,
                change_percent REAL NOT NULL,
                risk_level TEXT NOT NULL,
                confidence REAL NOT NULL,
                boundary_violation INTEGER DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plot_id TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_read INTEGER DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plot_id TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Open',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                notes TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                full_name TEXT,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS plot_boundaries (
                plot_id TEXT PRIMARY KEY,
                boundary_geojson TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS realtime_ingestion_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                plot_id TEXT,
                status TEXT NOT NULL,
                message TEXT,
                processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ownership_claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claimant_name TEXT NOT NULL,
                claimed_plot_label TEXT NOT NULL,
                claimed_owner_name TEXT,
                claim_reference TEXT,
                survey_no TEXT,
                adjacent_plot_id TEXT,
                claim_boundary_geojson TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Under Review',
                risk_flag TEXT NOT NULL DEFAULT 'Low',
                overlap_percent REAL DEFAULT 0,
                conflict_reason TEXT,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS official_parcels (
                parcel_id TEXT PRIMARY KEY,
                survey_number TEXT NOT NULL UNIQUE,
                owner_name TEXT NOT NULL,
                area REAL,
                geometry_geojson TEXT NOT NULL,
                source TEXT DEFAULT 'seed',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS government_land_layer (
                layer_id TEXT PRIMARY KEY,
                layer_name TEXT NOT NULL,
                land_type TEXT NOT NULL,
                survey_number TEXT,
                geometry_geojson TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS registration_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_name TEXT NOT NULL,
                buyer_name TEXT NOT NULL,
                uploaded_sale_deed TEXT,
                source_mode TEXT DEFAULT 'document_upload',
                extracted_survey_number TEXT,
                extracted_area REAL,
                extracted_boundary_geojson TEXT,
                generated_deed_pdf TEXT,
                input_payload TEXT,
                risk_score INTEGER DEFAULT 0,
                risk_level TEXT DEFAULT 'LOW',
                verification_status TEXT DEFAULT 'Approved',
                recommendation TEXT,
                encroachment_area REAL DEFAULT 0,
                government_land_overlap INTEGER DEFAULT 0,
                result_payload TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ensure_plot_columns(conn)
        _ensure_user_columns(conn)
        _ensure_registration_request_columns(conn)
        _ensure_indexes(conn)
        _seed_default_users(conn)
        _seed_default_boundaries(conn)
        _seed_registration_layers(conn, db_path)


def _ensure_plot_columns(conn: sqlite3.Connection) -> None:
    existing_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(plots)").fetchall()
    }
    extra_columns = {
        "area": "TEXT",
        "survey_no": "TEXT",
        "owner_name": "TEXT",
        "village": "TEXT",
        "district": "TEXT",
        "operator_note": "TEXT",
    }
    for column, column_type in extra_columns.items():
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE plots ADD COLUMN {column} {column_type}")


def _ensure_user_columns(conn: sqlite3.Connection) -> None:
    existing_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()
    }
    extra_columns = {
        "full_name": "TEXT",
        "created_at": "DATETIME",
    }
    for column, column_type in extra_columns.items():
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE users ADD COLUMN {column} {column_type}")


def _ensure_registration_request_columns(conn: sqlite3.Connection) -> None:
    existing_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(registration_requests)").fetchall()
    }
    extra_columns = {
        "source_mode": "TEXT DEFAULT 'document_upload'",
        "generated_deed_pdf": "TEXT",
        "input_payload": "TEXT",
    }
    for column, column_type in extra_columns.items():
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE registration_requests ADD COLUMN {column} {column_type}")


def _ensure_indexes(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_images_plot_year
        ON images(plot_id, year)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_history_plot
        ON history(plot_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_plot_history_plot
        ON plot_history(plot_id, timestamp)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_alerts_plot_time
        ON alerts(plot_id, created_at)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_cases_plot_status
        ON cases(plot_id, status)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_realtime_log_processed
        ON realtime_ingestion_log(processed_at DESC)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_claims_status_created
        ON ownership_claims(status, created_at DESC)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_official_parcels_survey
        ON official_parcels(survey_number)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_registration_requests_survey_time
        ON registration_requests(extracted_survey_number, created_at DESC)
        """
    )


def _seed_default_users(conn: sqlite3.Connection) -> None:
    defaults = [
        ("admin", "Command Center Admin", generate_password_hash("admin123"), "admin"),
        ("officer", "Revenue Inspector", generate_password_hash("officer123"), "officer"),
        ("viewer", "Citizen Access", generate_password_hash("viewer123"), "viewer"),
    ]
    for username, full_name, password, role in defaults:
        conn.execute(
            """
            INSERT INTO users (username, full_name, password, role, created_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(username) DO NOTHING
            """,
            (username, full_name, password, role),
        )
        conn.execute(
            """
            UPDATE users
            SET full_name = COALESCE(NULLIF(full_name, ''), ?)
            WHERE username = ?
            """,
            (full_name, username),
        )


def create_user(
    conn: sqlite3.Connection,
    *,
    username: str,
    password: str,
    role: str,
    full_name: str,
) -> sqlite3.Row:
    cursor = conn.execute(
        """
        INSERT INTO users (username, full_name, password, role, created_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (username, full_name, generate_password_hash(password), role),
    )
    return conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()


def _seed_default_boundaries(conn: sqlite3.Connection) -> None:
    rows = conn.execute("SELECT id, lat, lng FROM plots").fetchall()
    for row in rows:
        boundary = json.dumps(
            {
                "type": "Polygon",
                "coordinates": [
                    [
                        [row["lng"] - 0.002, row["lat"] - 0.002],
                        [row["lng"] + 0.002, row["lat"] - 0.002],
                        [row["lng"] + 0.002, row["lat"] + 0.002],
                        [row["lng"] - 0.002, row["lat"] + 0.002],
                        [row["lng"] - 0.002, row["lat"] - 0.002],
                    ]
                ],
            }
        )
        conn.execute(
            """
            INSERT INTO plot_boundaries (plot_id, boundary_geojson)
            VALUES (?, ?)
            ON CONFLICT(plot_id) DO NOTHING
            """,
            (row["id"], boundary),
        )


def _seed_registration_layers(conn: sqlite3.Connection, db_path: str) -> None:
    base_dir = os.path.dirname(db_path)
    dataset_path = os.path.join(base_dir, "sample_registration_dataset.json")
    if not os.path.exists(dataset_path):
        return

    with open(dataset_path, "r", encoding="utf-8") as handle:
        dataset = json.load(handle)

    for record in dataset.get("official_parcels", []):
        conn.execute(
            """
            INSERT INTO official_parcels (
                parcel_id, survey_number, owner_name, area, geometry_geojson, source, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(parcel_id) DO UPDATE SET
                survey_number = excluded.survey_number,
                owner_name = excluded.owner_name,
                area = excluded.area,
                geometry_geojson = excluded.geometry_geojson,
                source = excluded.source,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                record["parcel_id"],
                record["survey_number"],
                record["owner_name"],
                record["area"],
                json.dumps(record["geometry_geojson"]),
                record.get("source", "seed"),
            ),
        )

    for record in dataset.get("government_land_layer", []):
        conn.execute(
            """
            INSERT INTO government_land_layer (
                layer_id, layer_name, land_type, survey_number, geometry_geojson, updated_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(layer_id) DO UPDATE SET
                layer_name = excluded.layer_name,
                land_type = excluded.land_type,
                survey_number = excluded.survey_number,
                geometry_geojson = excluded.geometry_geojson,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                record["layer_id"],
                record["layer_name"],
                record["land_type"],
                record.get("survey_number"),
                json.dumps(record["geometry_geojson"]),
            ),
        )
