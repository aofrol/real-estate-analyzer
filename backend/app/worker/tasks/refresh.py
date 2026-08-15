"""
Periodic background refresh task (stub — implemented in Task #5).

Celery Beat will call refresh_recent_locations() on schedule.
"""
from app.worker.celery_app import celery_app


@celery_app.task(name="refresh_recent_locations")
def refresh_recent_locations() -> dict:
    """
    Re-run the data collection pipeline for recently searched locations.
    Stub — full implementation in Task #5 (Data Pipeline).
    """
    return {"status": "stub", "message": "Implemented in Task #5"}
