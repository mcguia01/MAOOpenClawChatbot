"""Nightly document sync scheduler.

Uses APScheduler's BackgroundScheduler to re-ingest all documents from
Google Drive every night at 2:00 AM local time.

Call `start_scheduler()` once during application startup (done in bot/app.py).
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import get_settings
from ingestion.pipeline import run_ingestion

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _nightly_sync() -> None:
    """Execute the full ingestion pipeline and log the result."""
    settings = get_settings()
    logger.info("=== Nightly sync job starting ===")
    try:
        summary = run_ingestion(folder_id=settings.google_drive_folder_id)
        logger.info(
            "=== Nightly sync complete: %d total, %d succeeded, %d failed ===",
            summary["total"],
            summary["succeeded"],
            summary["failed"],
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Nightly sync job failed with unhandled error: %s", exc, exc_info=True)


def start_scheduler() -> None:
    """Initialise and start the background scheduler.

    Schedules _nightly_sync() to run every day at 02:00 AM.
    Safe to call multiple times — will not create duplicate jobs.
    """
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        logger.debug("Scheduler already running, skipping start_scheduler()")
        return

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        func=_nightly_sync,
        trigger=CronTrigger(hour=2, minute=0),
        id="nightly_drive_sync",
        name="Nightly Google Drive → Pinecone sync",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started — nightly sync scheduled at 02:00 UTC")


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler (useful for tests and clean shutdown)."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    _scheduler = None
