import os

from fastapi import Depends

from config.settings import AppCoreSettings, DevSettings, TestSettings
from notifications.email import AsyncEmailService
from notifications.interfaces import EmailServiceProtocol
from security.token_manager import JWTAuthManager
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageClient, S3StorageInterface


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
