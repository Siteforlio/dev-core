# backend/app/core/celery_app.py
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "job_hunter",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.scraper_worker",
        "app.workers.board_scrape_worker",
        "app.workers.tailor_worker",
        "app.workers.apply_worker",
        "app.workers.email_worker",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    beat_schedule={
        "email-poll-every-60s": {
            "task": "app.workers.email_worker.poll_all_campaigns",
            "schedule": 60.0,
        },
        "scrape-every-6h": {
            "task": "app.workers.scraper_worker.scrape_all_active_campaigns",
            "schedule": 21600.0,
        },
    },
)
