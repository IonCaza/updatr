from celery import Celery
from celery.schedules import crontab

from app.config import settings
from app.services.queue_service import FALLBACK_QUEUE

celery_app = Celery(
    "updatr",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.patch_task",
        "app.tasks.compliance_task",
        "app.tasks.discovery_task",
        "app.tasks.deployment_task",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_hijack_root_logger=False,
    # Any task dispatched without an explicit queue lands on the control
    # plane's queue.  This prevents "lost" tasks sitting on an unmonitored
    # "default" queue that no worker consumes.
    task_default_queue=FALLBACK_QUEUE,
    task_create_missing_queues=True,
    beat_schedule={
        # Beat tasks always target the control plane (FALLBACK_QUEUE).
        # compliance_fanout itself fans out to per-site queues.
        "nightly-compliance-fanout": {
            "task": "compliance_fanout",
            "schedule": crontab(hour=2, minute=0),
            "options": {"queue": FALLBACK_QUEUE},
        },
        "deployment-health-check": {
            "task": "check_deployment_health",
            "schedule": 60.0,
            "options": {"queue": FALLBACK_QUEUE},
        },
    },
)
