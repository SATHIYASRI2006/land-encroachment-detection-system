from __future__ import annotations

import threading
import time

from services.plot_service import get_all_plot_image_groups

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except Exception:  # pragma: no cover - fallback for environments without APScheduler
    BackgroundScheduler = None


def start_auto_monitor(settings, logger, analyze_callback):
    def run_cycle():
        image_groups = get_all_plot_image_groups(settings)
        for plot_id, images in image_groups.items():
            if len(images) < 2:
                continue
            try:
                analyze_callback(plot_id, emit_socket=False)
            except Exception as exc:
                logger.exception("Auto-monitor error for plot %s: %s", plot_id, exc)

    if BackgroundScheduler:
        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(
            run_cycle,
            "interval",
            minutes=settings.auto_monitor_interval_minutes,
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()
        logger.info(
            "Started APScheduler auto-monitor every %s minute(s)",
            settings.auto_monitor_interval_minutes,
        )
        return scheduler

    def loop():
        while True:
            run_cycle()
            time.sleep(settings.auto_monitor_interval_minutes * 60)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    logger.info(
        "Started thread-based auto-monitor every %s minute(s)",
        settings.auto_monitor_interval_minutes,
    )
    return thread
