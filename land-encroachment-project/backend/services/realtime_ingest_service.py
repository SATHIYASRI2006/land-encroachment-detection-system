from __future__ import annotations

import json
import os
import shutil
import threading
import time

from core.db import db_session
from services.location_service import (
    coordinate_validation_message,
    is_valid_chennai_coordinate,
)
from services.plot_service import upsert_plot_bundle

ALLOWED_YEARS = {2021, 2022, 2023, 2024}


def record_realtime_log(db_path: str, file_name: str, plot_id: str | None, status: str, message: str):
    with db_session(db_path) as conn:
        conn.execute(
            """
            INSERT INTO realtime_ingestion_log (file_name, plot_id, status, message)
            VALUES (?, ?, ?, ?)
            """,
            (file_name, plot_id, status, message),
        )


def get_realtime_status(settings):
    with db_session(settings.db_path) as conn:
        recent_logs = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, file_name, plot_id, status, message, processed_at
                FROM realtime_ingestion_log
                ORDER BY processed_at DESC, id DESC
                LIMIT 10
                """
            ).fetchall()
        ]

    return {
        "enabled": settings.realtime_ingest_enabled,
        "poll_interval_seconds": settings.realtime_ingest_interval_seconds,
        "inbox_folder": settings.realtime_inbox_folder,
        "archive_folder": settings.realtime_archive_folder,
        "failed_folder": settings.realtime_failed_folder,
        "recent_logs": recent_logs,
    }


def _resolve_source_path(manifest_path: str, image_item: dict) -> str:
    source_path = image_item.get("source_path") or image_item.get("path") or image_item.get("filename")
    if not source_path:
        raise ValueError("Each image entry needs source_path, path, or filename")

    if os.path.isabs(source_path):
        return source_path

    manifest_dir = os.path.dirname(manifest_path)
    return os.path.normpath(os.path.join(manifest_dir, source_path))


def _copy_image_to_data_folder(settings, plot_id: str, year: int, source_path: str) -> str:
    ext = os.path.splitext(source_path)[1].lower()
    if ext not in settings.allowed_image_extensions:
        raise ValueError(f"Unsupported image type for year {year}")
    if not os.path.exists(source_path):
        raise ValueError(f"Image file not found: {source_path}")

    safe_plot_id = str(plot_id).strip().replace(" ", "_")
    final_name = f"{safe_plot_id}_{year}{ext}"
    shutil.copy2(source_path, os.path.join(settings.data_folder, final_name))
    return final_name


def process_realtime_manifest(settings, logger, analyze_callback, manifest_path: str):
    file_name = os.path.basename(manifest_path)
    payload = {}
    plot_id = None

    try:
        with open(manifest_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)

        plot_id = str(payload.get("plot_id") or "").strip()
        if not plot_id:
            raise ValueError("plot_id is required in the manifest")

        metadata = {
            "plot_id": plot_id,
            "lat": float(payload.get("lat")),
            "lng": float(payload.get("lng")),
            "location_name": (payload.get("location_name") or plot_id).strip(),
            "area": (payload.get("area") or "").strip(),
            "survey_no": (payload.get("survey_no") or "").strip(),
            "owner_name": (payload.get("owner_name") or "").strip(),
            "village": (payload.get("village") or "").strip(),
            "district": (payload.get("district") or "Chennai").strip(),
            "operator_note": (payload.get("operator_note") or "Realtime feed ingestion").strip(),
        }

        if not is_valid_chennai_coordinate(metadata["lat"], metadata["lng"]):
            raise ValueError(coordinate_validation_message())

        if payload.get("boundary_geojson"):
            metadata["boundary_geojson"] = payload["boundary_geojson"]

        images = payload.get("images") or []
        if not images:
            raise ValueError("Manifest must include an images array")

        uploaded_images = {}
        for image_item in images:
            year = int(image_item.get("year"))
            if year not in ALLOWED_YEARS:
                raise ValueError("Realtime ingestion accepts only 2021-2024 imagery")
            source_path = _resolve_source_path(manifest_path, image_item)
            uploaded_images[year] = _copy_image_to_data_folder(
                settings,
                plot_id,
                year,
                source_path,
            )

        upsert_plot_bundle(settings, metadata, uploaded_images)
        analyze_callback(plot_id, emit_socket=False)

        archived_manifest = os.path.join(settings.realtime_archive_folder, file_name)
        shutil.move(manifest_path, archived_manifest)
        record_realtime_log(
            settings.db_path,
            file_name,
            plot_id,
            "processed",
            f"Imported years: {', '.join(map(str, sorted(uploaded_images.keys())))}",
        )
        logger.info("Realtime manifest processed for plot %s from %s", plot_id, file_name)
    except Exception as exc:
        logger.exception("Realtime ingestion failed for %s: %s", file_name, exc)
        failed_manifest = os.path.join(settings.realtime_failed_folder, file_name)
        if os.path.exists(manifest_path):
            shutil.move(manifest_path, failed_manifest)
        record_realtime_log(
            settings.db_path,
            file_name,
            plot_id,
            "failed",
            str(exc),
        )


def start_realtime_ingestion(settings, logger, analyze_callback):
    if not settings.realtime_ingest_enabled:
        logger.info("Realtime ingestion is disabled")
        return None

    def run_cycle():
        manifest_files = sorted(
            file_name
            for file_name in os.listdir(settings.realtime_inbox_folder)
            if file_name.lower().endswith(".json")
        )

        for file_name in manifest_files:
            manifest_path = os.path.join(settings.realtime_inbox_folder, file_name)
            process_realtime_manifest(settings, logger, analyze_callback, manifest_path)

    def loop():
        while True:
            try:
                run_cycle()
            except Exception as exc:
                logger.exception("Realtime ingestion loop failed: %s", exc)
            time.sleep(max(settings.realtime_ingest_interval_seconds, 5))

    thread = threading.Thread(target=loop, daemon=True, name="realtime-ingest")
    thread.start()
    logger.info(
        "Started realtime ingestion watcher on %s every %s second(s)",
        settings.realtime_inbox_folder,
        settings.realtime_ingest_interval_seconds,
    )
    return thread
