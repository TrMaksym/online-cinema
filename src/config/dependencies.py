import asyncio
import os

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
import asyncpg
from sqlalchemy.exc import DBAPIError

from src.database.models.accounts import User, UserGroupEnum
from .settings import AppCoreSettings, DevSettings, TestSettings
from src.notifications.email import AsyncEmailService
from src.notifications.interfaces import EmailServiceProtocol
from src.security.jwt import JWTAuthManager
from src.security.interfaces import JWTAuthManagerInterface
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator
from src.storage.interfaces import S3StorageInterface
from src.storage.s3 import S3StorageClient

from src.database.session_postgresql import async_session_maker

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_settings() -> AppCoreSettings:
    env = os.getenv("ENVIRONMENT", "developing")
    return TestSettings() if env == "testing" else DevSettings()


def get_jwt_auth_manager(
    settings: AppCoreSettings = Depends(get_settings),
) -> JWTAuthManagerInterface:
    return JWTAuthManager(
        secret_key_access=settings.JWT_SECRET_ACCESS,
        secret_key_refresh=settings.JWT_SECRET_REFRESH,
        algorithm=settings.JWT_ALGORITHM,
    )


def get_email_sender(
    settings: AppCoreSettings = Depends(get_settings),
) -> EmailServiceProtocol:
    return AsyncEmailService(
        smtp_host=settings.SMTP_SERVER,
        smtp_port=settings.SMTP_PORT,
        sender_email=settings.SMTP_USER,
        sender_password=settings.SMTP_PASSWORD,
        use_tls=settings.SMTP_TLS,
    )


def get_s3_storage_client(
    settings: AppCoreSettings = Depends(get_settings),
) -> S3StorageInterface:
    return S3StorageClient(
        endpoint_url=settings.STORAGE_ENDPOINT,
        access_key=settings.STORAGE_USER,
        secret_key=settings.STORAGE_PASSWORD,
        bucket_name=settings.STORAGE_BUCKET,
    )


async def get_session():
    async with async_session_maker() as session:
        yield session

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    for i in range(10):
        try:
            async with async_session_maker() as session:
                yield session
            return
        except (DBAPIError, asyncpg.exceptions.PostgresConnectionError, ConnectionRefusedError) as e:
            print(f"Error connecting to database: {e}")
            await asyncio.sleep(1)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Database is temporarily unavailable. Please try again later.",
    )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_async_session),
    jwt_auth: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
):
    try:
        payload = jwt_auth.decode_access_token(token)
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user


async def get_current_admin_or_moderator(
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("admin", "moderator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )
    return current_user
