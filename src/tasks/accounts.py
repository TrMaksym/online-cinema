import asyncio
from datetime import datetime

from aiobotocore.session import get_session
from sqlalchemy import delete


from src.database.models.accounts import ActivationToken, RefreshToken
from src.database.session_postgresql import async_session_maker
from src.celery_app import celery_app
from celery import shared_task
from src.notifications.email import AsyncEmailService
from src.schemas.accounts import PasswordResetToken


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


@shared_task
async def delete_expired_tokens():
    now = datetime.utcnow()
    async with async_session_maker() as session:
        await session.execute(
            delete(ActivationToken).where(ActivationToken.expires_at < now)
        )
        await session.execute(
            delete(PasswordResetToken).where(PasswordResetToken.expires_at < now)
        )
        await session.execute(
            delete(RefreshToken).where(RefreshToken.expires_at < now)
        )
        await session.commit()


@shared_task
def send_activation_email_task(email, activation_link):
    asyncio.run(_send_email(email, activation_link))

async def _send_email(email, activation_link):
    email_service = AsyncEmailService()
    await email_service.send_account_activation(email, activation_link)