from __future__ import annotations

import os
from dataclasses import dataclass


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    base_dir: str
    data_folder: str
    reports_folder: str
    db_path: str
    realtime_inbox_folder: str
    realtime_archive_folder: str
    realtime_failed_folder: str
    img_size: tuple[int, int]
    smtp_server: str
    smtp_port: int
    email_user: str | None
    email_pass: str | None
    email_to: str | None
    secret_key: str
    jwt_exp_minutes: int
    allow_legacy_anonymous: bool
    auto_monitor_interval_minutes: int
    alert_email_cooldown_minutes: int
    realtime_ingest_enabled: bool
    realtime_ingest_interval_seconds: int
    allowed_image_extensions: tuple[str, ...]


def load_settings() -> Settings:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return Settings(
        base_dir=base_dir,
        data_folder=os.path.join(base_dir, "static", "data"),
        reports_folder=os.path.join(base_dir, "reports"),
        db_path=os.path.join(base_dir, "land.db"),
        realtime_inbox_folder=os.path.join(base_dir, "live_feed", "inbox"),
        realtime_archive_folder=os.path.join(base_dir, "live_feed", "archive"),
        realtime_failed_folder=os.path.join(base_dir, "live_feed", "failed"),
        img_size=(512, 512),
        smtp_server=os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        email_user=os.getenv("EMAIL_USER"),
        email_pass=os.getenv("EMAIL_PASS"),
        email_to=os.getenv("EMAIL_TO"),
        secret_key=os.getenv(
            "JWT_SECRET",
            "change-this-secret-to-a-long-random-string-for-production",
        ),
        jwt_exp_minutes=int(os.getenv("JWT_EXP_MINUTES", "120")),
        allow_legacy_anonymous=_to_bool(
            os.getenv("ALLOW_LEGACY_ANONYMOUS"), True
        ),
        auto_monitor_interval_minutes=int(
            os.getenv("AUTO_MONITOR_INTERVAL_MINUTES", "10")
        ),
        alert_email_cooldown_minutes=int(
            os.getenv("ALERT_EMAIL_COOLDOWN_MINUTES", "120")
        ),
        realtime_ingest_enabled=_to_bool(
            os.getenv("REALTIME_INGEST_ENABLED"), True
        ),
        realtime_ingest_interval_seconds=int(
            os.getenv("REALTIME_INGEST_INTERVAL_SECONDS", "30")
        ),
        allowed_image_extensions=(".png", ".jpg", ".jpeg"),
    )
