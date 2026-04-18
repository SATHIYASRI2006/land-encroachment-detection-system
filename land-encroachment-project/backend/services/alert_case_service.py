from __future__ import annotations

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from threading import Thread

import smtplib

from core.db import db_session


def store_plot_history(db_path: str, plot_id: str, change_percent: float, risk_level: str, confidence: float, boundary_violation: bool):
    with db_session(db_path) as conn:
        conn.execute(
            """
            INSERT INTO plot_history (plot_id, change_percent, risk_level, confidence, boundary_violation)
            VALUES (?, ?, ?, ?, ?)
            """,
            (plot_id, change_percent, risk_level, confidence, int(boundary_violation)),
        )
        conn.execute(
            """
            INSERT INTO history (plot_id, risk, change)
            VALUES (?, ?, ?)
            """,
            (plot_id, risk_level, change_percent),
        )


def create_case_if_needed(db_path: str, plot_id: str, risk_level: str, notes: str):
    if risk_level != "High":
        return None

    with db_session(db_path) as conn:
        existing = conn.execute(
            """
            SELECT * FROM cases
            WHERE plot_id = ? AND status IN ('Open', 'Investigating')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (plot_id,),
        ).fetchone()
        if existing:
            return dict(existing)

        cursor = conn.execute(
            """
            INSERT INTO cases (plot_id, risk_level, status, notes)
            VALUES (?, ?, 'Open', ?)
            """,
            (plot_id, risk_level, notes),
        )
        case_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        return dict(row) if row else None


def create_alert_if_needed(db_path: str, plot_id: str, risk_level: str, message: str):
    if risk_level != "High":
        return None

    with db_session(db_path) as conn:
        existing = conn.execute(
            """
            SELECT *
            FROM alerts
            WHERE plot_id = ?
              AND risk_level = ?
              AND created_at >= datetime('now', '-10 minutes')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (plot_id, risk_level),
        ).fetchone()
        if existing:
            return dict(existing)

        cursor = conn.execute(
            """
            INSERT INTO alerts (plot_id, risk_level, message, is_read)
            VALUES (?, ?, ?, 0)
            """,
            (plot_id, risk_level, message),
        )
        alert_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        return dict(row) if row else None


def send_alert_email(
    settings,
    plot_id: str,
    percentage: float,
    risk_level: str,
    message: str,
    logger,
    alert_id: int | None = None,
):
    def _send():
        if not all([settings.email_user, settings.email_pass, settings.email_to]):
            logger.warning("Email config missing, skipping SMTP delivery")
            return

        cooldown_minutes = max(int(getattr(settings, "alert_email_cooldown_minutes", 120)), 1)
        with db_session(settings.db_path) as conn:
            recent_email_window = conn.execute(
                """
                SELECT created_at
                FROM alerts
                WHERE plot_id = ?
                  AND risk_level = ?
                  AND (? IS NULL OR id != ?)
                  AND created_at >= datetime('now', ?)
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (
                    plot_id,
                    risk_level,
                    alert_id,
                    alert_id,
                    f"-{cooldown_minutes} minutes",
                ),
            ).fetchone()

        if recent_email_window:
            logger.info(
                "Skipping alert email for plot %s; cooldown window of %s minutes is active",
                plot_id,
                cooldown_minutes,
            )
            return

        try:
            mail = MIMEMultipart()
            mail["Subject"] = f"Encroachment Alert - Plot {plot_id}"
            mail["From"] = settings.email_user
            mail["To"] = settings.email_to
            body = f"{message}\n\nPlot ID: {plot_id}\nRisk: {risk_level}\nChange: {percentage:.2f}%"
            mail.attach(MIMEText(body, "plain"))

            server = smtplib.SMTP(settings.smtp_server, settings.smtp_port)
            server.starttls()
            server.login(settings.email_user, settings.email_pass)
            server.send_message(mail)
            server.quit()
            logger.info("Alert email sent for plot %s", plot_id)
        except Exception as exc:
            logger.exception("Failed to send alert email for plot %s: %s", plot_id, exc)

    Thread(target=_send, daemon=True).start()
