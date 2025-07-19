from datetime import datetime

from sqlalchemy import delete


from src.database.models.accounts import ActivationToken
from src.database.session_postgresql import async_session_maker
from src.celery_app import celery_app
from celery import shared_task
from src.notifications.email import AsyncEmailService

@celery_app.task
async def delete_expired_activation_tokens():
    async with async_session_maker() as session:
        await session.execute(
            delete(ActivationToken).where(ActivationToken.expires_at < datetime.utcnow())
        )
        await session.commit()


@shared_task
def send_reset_email_async(email: str, token: str):
    email_service = AsyncEmailService()
    reset_link = f"http://127.0.0.1:8000/reset-password/{token}"
    email_service.send_password_reset(email, reset_link)
