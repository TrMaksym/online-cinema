import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

class AppCoreSettings(BaseSettings):
    ROOT_DIR: Path = Path(__file__).resolve().parent.parent
    DB_PATH: str = str(ROOT_DIR / "database" / "source" / "app.db")
    CSV_MOVIES_PATH: str = str(ROOT_DIR / "database" / "seed_data" / "movies.csv")

    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "localhost")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER: str = os.getenv("SMTP_USER", "noreply@example.com")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "secret")
    SMTP_TLS: bool = os.getenv("SMTP_TLS", "true").lower() == "true"

    STORAGE_HOST: str = os.getenv("S3_HOST", "localhost")
    STORAGE_PORT: int = int(os.getenv("S3_PORT", 9000))
    STORAGE_USER: str = os.getenv("S3_USER", "admin")
    STORAGE_PASSWORD: str = os.getenv("S3_PASSWORD", "adminpass")
    STORAGE_BUCKET: str = os.getenv("S3_BUCKET", "default-bucket")

    @property
    def STORAGE_ENDPOINT(self) -> str:
        return f"http://{self.STORAGE_HOST}:{self.STORAGE_PORT}"

    TOKEN_TTL_DAYS: int = 7
    JWT_SECRET_ACCESS: str = os.getenv("JWT_SECRET_ACCESS", os.urandom(32).hex())
    JWT_SECRET_REFRESH: str = os.getenv("JWT_SECRET_REFRESH", os.urandom(32).hex())
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")


class DevSettings(AppCoreSettings):
    DB_USER: str = os.getenv("POSTGRES_USER", "admin_movies")
    DB_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "password_cinema")
    DB_HOST: str = os.getenv("POSTGRES_HOST", "db")
    DB_PORT: int = int(os.getenv("DB_PORT", 5432))
    DB_NAME: str = os.getenv("POSTGRES_DB", "movies_password")

    @property
    def DATABASE_URL(self) -> str:
        env_url = os.getenv("DATABASE_URL")
        if env_url:
            return env_url
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


class TestSettings(AppCoreSettings):
    JWT_SECRET_ACCESS: str = "test-access"
    JWT_SECRET_REFRESH: str = "test-refresh"
    JWT_ALGORITHM: str = "HS256"

    def model_post_init(self, __context: dict[str, Any] | None = None) -> None:
        object.__setattr__(self, "DB_PATH", ":memory:")
        object.__setattr__(
            self,
            "CSV_MOVIES_PATH",
            str(self.ROOT_DIR / "database" / "seed_data" / "test_data.csv"),
        )

try:
    settings = DevSettings()
    print(settings.DATABASE_URL)
except Exception as e:
    import traceback
    print("Errors DevSettings!\n")
    traceback.print_exc()