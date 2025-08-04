import os
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError, ExpiredSignatureError


class JWTAuthManager:
    _ACCESS_TOKEN_EXPIRE_MINUTES = 45
    _REFRESH_TOKEN_EXPIRE_DAYS = 7
    _ALGORITHM = "HS256"

    def __init__(self):
        self._secret_key_access = os.getenv("SECRET_KEY_ACCESS")
        self._secret_key_refresh = os.getenv("SECRET_KEY_REFRESH")
        if not self._secret_key_access or not self._secret_key_refresh:
            raise ValueError(
                "SECRET_KEY_ACCESS and SECRET_KEY_REFRESH must be set in environment variables"
            )

    def _create_token(
        self, user_id: int, secret_key: str, expires_delta: timedelta
    ) -> str:
        expire = datetime.now(timezone.utc) + expires_delta
        payload = {"sub": str(user_id), "exp": expire}
        return jwt.encode(payload, secret_key, algorithm=self._ALGORITHM)

    def create_access_token(self, user_id: int) -> str:
        return self._create_token(
            user_id,
            self._secret_key_access,
            timedelta(minutes=self._ACCESS_TOKEN_EXPIRE_MINUTES),
        )

    def create_refresh_token(self, user_id: int) -> str:
        return self._create_token(
            user_id,
            self._secret_key_refresh,
            timedelta(days=self._REFRESH_TOKEN_EXPIRE_DAYS),
        )

    def decode_token(self, token: str, secret_key: str) -> dict:
        try:
            return jwt.decode(token, secret_key, algorithms=[self._ALGORITHM])
        except ExpiredSignatureError:
            raise Exception("Token expired")
        except JWTError:
            raise Exception("Invalid token")

    def decode_access_token(self, token: str) -> dict:
        return self.decode_token(token, self._secret_key_access)

    def decode_refresh_token(self, token: str) -> dict:
        return self.decode_token(token, self._secret_key_refresh)

    def verify_access_token(self, token: str) -> None:
        self.decode_access_token(token)

    def verify_refresh_token(self, token: str) -> None:
        self.decode_refresh_token(token)


_jwt_manager = None


def get_jwt_manager() -> JWTAuthManager:
    global _jwt_manager
    if _jwt_manager is None:
        _jwt_manager = JWTAuthManager()
    return _jwt_manager


def create_access_token(user_id: int) -> str:
    return get_jwt_manager().create_access_token(user_id)


def create_refresh_token(user_id: int) -> str:
    return get_jwt_manager().create_refresh_token(user_id)
