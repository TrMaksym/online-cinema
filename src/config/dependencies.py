import os

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select

from database.models.accounts import User, UserGroupEnum
from .settings import AppCoreSettings, DevSettings, TestSettings
from src.notifications.email import AsyncEmailService
from src.notifications.interfaces import EmailServiceProtocol
from src.security.token_manager import JWTAuthManager
from src.security.interfaces import JWTAuthManagerInterface
from sqlalchemy.ext.asyncio import AsyncSession
from storages import S3StorageClient, S3StorageInterface
from typing import AsyncGenerator

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


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

async def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_async_session),
):
    if not token.isdigit():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    user_id = int(token)
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.group.name != UserGroupEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user

def get_current_moderator(current_user: User = Depends(get_current_user)) -> User:
    if current_user.group.name not in [UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Moderator or admin access required",
        )
    return current_user