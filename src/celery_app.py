from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    "online_cinema",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
    include=["src.tasks.accounts"]
)

celery_app.conf.task_modules = [
    "src.tasks.accounts"
]

celery_app.conf.timezone = 'UTC'

celery_app.conf.beat_schedule = {
    "delete-expired-activation-tokens-daily": {
        "task": "src.tasks.accounts.delete_expired_activation_tokens",
        "schedule": crontab(hour=0, minute=0),
    },
}
