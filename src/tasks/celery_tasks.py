from datetime import datetime
import asyncio

from sqlalchemy import delete

from src.celery_app import celery_app
from src.database.session_postgresql import async_session_maker
from src.database.models.accounts import ActivationToken, UserResetPassword


@celery_app.task
def cleanup_expired_tokens():
    asyncio.run(_cleanup_expired_tokens_async())


async def _cleanup_expired_tokens_async():
    async with async_session_maker() as session:
        now = datetime.utcnow()

        await session.execute(
            delete(ActivationToken).where(ActivationToken.expires_at < now)
        )
        await session.execute(
            delete(UserResetPassword).where(UserResetPassword.expires_at < now)
        )
        await session.commit()
