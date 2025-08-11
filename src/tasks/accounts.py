import asyncio
from datetime import datetime
from sqlalchemy import delete

from src.database.models.accounts import ActivationToken, RefreshToken, UserResetPassword
from src.database.session_postgresql import async_session_maker
from src.celery_app import celery_app
from src.notifications.email import AsyncEmailService


def get_email_service() -> AsyncEmailService:
    return AsyncEmailService(
        smtp_host="smtp.example.com",
        smtp_port=587,
        sender_email="maximuschampion2002@gmail.com",
        sender_password="mqyohjngeptgdpkv",
        use_tls=True,
    )


@celery_app.task
def delete_expired_activation_tokens():
    asyncio.run(_delete_expired_activation_tokens_async())


async def _delete_expired_activation_tokens_async():
    async with async_session_maker() as session:
        await session.execute(
            delete(ActivationToken).where(
                ActivationToken.expires_at < datetime.utcnow()
            )
        )
        await session.commit()


@celery_app.task
def delete_expired_tokens():
    asyncio.run(_delete_expired_tokens_async())


async def _delete_expired_tokens_async():
    now = datetime.utcnow()
    async with async_session_maker() as session:
        await session.execute(delete(ActivationToken).where(ActivationToken.expires_at < now))
        await session.execute(delete(UserResetPassword).where(UserResetPassword.expires_at < now))
        await session.execute(delete(RefreshToken).where(RefreshToken.expires_at < now))
        await session.commit()


@celery_app.task
def send_reset_email_async(email: str, token: str):
    asyncio.run(_send_reset_email(email, token))


async def _send_reset_email(email: str, token: str):
    email_service = get_email_service()
    reset_link = f"http://127.0.0.1:8000/reset-password/{token}"
    await email_service.send_password_reset_request(email, reset_link)


@celery_app.task
def send_activation_email_task(email, activation_link):
    asyncio.run(_send_email(email, activation_link))


async def _send_email(email, activation_link):
    email_service = get_email_service()
    await email_service.send_account_activation(email, activation_link)
