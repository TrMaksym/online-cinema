from datetime import datetime
from sqlalchemy import delete
from src.database.models.accounts import ActivationToken
from src.database.session_postgresql import async_session_maker
from src.celery_app import celery_app

@celery_app.task
async def delete_expired_activation_tokens():
    async with async_session_maker() as session:
        await session.execute(
            delete(ActivationToken).where(ActivationToken.expires_at < datetime.utcnow())
        )
        await session.commit()
