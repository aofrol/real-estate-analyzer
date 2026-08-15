"""
Celery application instance.

In MVP v1.0 Celery is used ONLY for periodic background refresh of listings.
The main POST /api/v1/valuate flow is fully synchronous (no Celery).
"""
import os
from celery import Celery

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "real_estate_worker",
    broker=redis_url,
    backend=redis_url,
    include=["app.worker.tasks.refresh"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)
