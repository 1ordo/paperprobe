from celery import Celery

from app.config import settings

celery_app = Celery(
    "cosmin_checker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.parse_document",
        "app.workers.embed_document",
        "app.workers.run_analysis",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    task_soft_time_limit=900,   # 15 min soft limit — raises SoftTimeLimitExceeded
    task_time_limit=1200,       # 20 min hard kill
)
