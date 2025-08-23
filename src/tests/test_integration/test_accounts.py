from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, Mock, patch, ANY
from asgi_lifespan import LifespanManager
from sqlalchemy.sql.functions import user

from src.config.dependencies import get_email_sender
from src.main import app
from src.database.models.accounts import User
from src.security.password import get_password_hash


@pytest.fixture
def mock_db_session():
    mock_session = AsyncMock()

    async def execute(stmt):
        scalars_mock = Mock()
        scalars_mock.first.return_value = None
        result_mock = Mock()
        result_mock.scalars.return_value = scalars_mock
        return result_mock

    mock_session.execute.side_effect = execute
    mock_session.get = AsyncMock(return_value=None)
    mock_session.add = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.delete = AsyncMock()
    return mock_session


@pytest.fixture
def override_dependencies(mock_db_session):
    from src.router.accounts import get_async_session, get_email_sender

    app.dependency_overrides[get_async_session] = lambda: mock_db_session
    app.dependency_overrides[get_email_sender] = lambda: AsyncMock(
        send_account_activation=AsyncMock()
    )
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def hash_password():
    return get_password_hash

@pytest.fixture
def test_password(hash_password):
    plain_password = "Password123!"
    hashed_password = hash_password(plain_password)
    return plain_password, hashed_password

@pytest.fixture
def set_jwt_secrets(monkeypatch):
    monkeypatch.setenv("SECRET_KEY_ACCESS", "secret_access_key")
    monkeypatch.setenv("SECRET_KEY_REFRESH", "secret_refresh_key")


@pytest.fixture
def mock_user_with_hashed_password(mock_db_session, test_password):
    plain_password, hashed_password = test_password

    user = Mock(spec=User)
    user.email = "email@example.com"
    user.is_active = True
    user.hashed_password = hashed_password

    scalars_mock = Mock()
    scalars_mock.first.return_value = user
    result_mock = Mock()
    result_mock.scalars.return_value = scalars_mock

    async def execute(stmt):
        return result_mock

    mock_db_session.execute.side_effect = execute
    return user, plain_password


@patch("src.router.accounts.send_activation_email_task.delay")
@pytest.mark.asyncio
async def test_register_user_success(mock_send_task, override_dependencies):
    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/register/",
                json={"email": "test@example.com", "password": "Password123!"}
            )
            assert response.status_code == 201
            mock_send_task.assert_called_once()


@pytest.mark.asyncio
async def test_register_user_existing_email(override_dependencies, mock_db_session):
    mock_user = Mock(spec=User)
    mock_user.email = "test@example.com"
    mock_user.is_active = True

    scalars_mock = Mock()
    scalars_mock.first.return_value = mock_user
    result_mock = Mock()
    result_mock.scalars.return_value = scalars_mock

    async def execute(stmt):
        return result_mock

    mock_db_session.execute.side_effect = execute

    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/register/",
                json={"email": "test@example.com", "password": "Password123"}
            )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_register_user_weak_password(override_dependencies):
    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/register/",
                json={"email": "email@example.com", "password": "1234"}
            )

    assert response.status_code == 400
    assert "Password must be at least" in response.json()["detail"]


@pytest.mark.asyncio
@patch("src.security.jwt.create_access_token", return_value="fake_token")
@patch("src.security.jwt.create_refresh_token", return_value="fake_refresh_token")
async def test_login_success(mock_create_refresh, mock_create_access, set_jwt_secrets, override_dependencies, mock_user_with_hashed_password):
    user, plain_password = mock_user_with_hashed_password

    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/login/",
                json={"email": user.email, "password": plain_password}
            )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_password_wrong(override_dependencies, mock_user_with_hashed_password):
    user, test_password = mock_user_with_hashed_password

    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/login/",
                json={"email": user.email, "password": "WrongPassword123!"}
            )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password."


@pytest.mark.asyncio
async def test_activate_user_invalid_token(override_dependencies, mock_db_session):
    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/accounts/activate/invalid-token")

    assert response.status_code == 400
    assert "Invalid activation token or expired" in response.json()["detail"]

@pytest.mark.asyncio
async def test_logout_success(override_dependencies, mock_db_session):
    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/logout/",
                json={"refresh_token": "some_token"}
            )

    assert response.status_code == 200
    assert response.json()["message"] == "Successfully logged out."
    mock_db_session.execute.assert_called()


@pytest.mark.asyncio
@patch("src.router.accounts.send_reset_email_async", new_callable=AsyncMock)
async def test_forgot_password_success(mock_send_email, override_dependencies, mock_user_with_hashed_password,
                                       mock_db_session):
    user, _ = mock_user_with_hashed_password

    async def execute(stmt):
        scalars_mock = Mock()
        scalars_mock.first.return_value = user
        result_mock = Mock()
        result_mock.scalars.return_value = scalars_mock
        return result_mock

    mock_db_session.execute.side_effect = execute

    async with LifespanManager(app):
        async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/forgot-password/",
                json={"email": "email@example.com"}
            )

    assert response.status_code == 200
    mock_send_email.assert_called()

@pytest.mark.asyncio
async def test_forgot_password_invalid_email(override_dependencies, mock_db_session):
    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/forgot-password/",
                json={"email": "email@example.com"}
            )

    assert response.status_code == 404

@patch("src.router.accounts.send_reset_email_async", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_forgot_password_inactivate_user(mock_user_with_hashed_password ,override_dependencies, mock_db_session):
    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/forgot-password/",
                json={"email": "email@example.com"}
            )

    assert response.status_code == 404

@pytest.mark.asyncio
async def test_reset_password_invalid_token(override_dependencies, mock_db_session):
    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.put(
                "/api/v1/accounts/reset-password/",
                json={"token": "bad_token", "new_password": "SomeNewPass1!"}
            )
    assert response.status_code in (400, 403)

@pytest.mark.asyncio
async def test_reset_password_expired_token(override_dependencies, mock_db_session, mock_user_with_hashed_password):
    user, _ = mock_user_with_hashed_password
    fake_token = "expired_token"

    class FakeResetToken:
        token = fake_token
        user_id = user.id
        expires_at = datetime.utcnow() - timedelta(minutes=1)

    async def execute(stmt):
        if "FROM reset_tokens" in str(stmt):
            scalars_mock = Mock()
            scalars_mock.first.return_value = FakeResetToken()
            result_mock = Mock()
            result_mock.scalars.return_value = scalars_mock
            return result_mock
        elif "FROM users" in str(stmt):
            scalars_mock = Mock()
            scalars_mock.first.return_value = user
            result_mock = Mock()
            result_mock.scalars.return_value = scalars_mock
            return result_mock
        else:
            result_mock = Mock()
            scalars_mock = Mock()
            scalars_mock.first.return_value = None
            result_mock.scalars.return_value = scalars_mock
            return result_mock

    mock_db_session.execute.side_effect = execute

    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.put(
                "/api/v1/accounts/reset-password/",
                json={"token": fake_token, "new_password": "Password1234!"}
            )

    assert response.status_code == 400
    assert "Invalid or expired password reset token" in response.json()["detail"]

@pytest.mark.asyncio
async def test_resend_activation_success(override_dependencies, mock_db_session):
    user = Mock()
    user.id = 1
    user.email = "email@example.com"
    user.is_active = False

    scalars_mock = Mock()
    scalars_mock.first.return_value = user
    result_mock = Mock()
    result_mock.scalars.return_value = scalars_mock

    async def execute(stmt):
        return result_mock

    mock_db_session.execute.side_effect = execute

    mock_email_service = AsyncMock()

    app.dependency_overrides[get_email_sender] = lambda: mock_email_service

    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/reset-activation/",
                json={"email": user.email}
            )

    assert response.status_code == 200
    assert response.json()["message"] == "Registration successful. Please check your email to activate your account."
    mock_email_service.send_account_activation.assert_awaited_once_with(
        recipient_email=user.email,
        activation_link=ANY
    )
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_resend_activation_user_not_found(override_dependencies, mock_db_session):
    async def execute(stmt):
        scalars_mock = Mock()
        scalars_mock.first.return_value = None
        result_mock = Mock()
        result_mock.scalars.return_value = scalars_mock
        return result_mock

    mock_db_session.execute.side_effect = execute

    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/reset-activation/",
                json={"email": "email@example.com"}
            )

    assert response.status_code == 404

@pytest.mark.asyncio
async def test_login_inactive_user(override_dependencies, mock_db_session, test_password):
    plain, hashed = test_password
    user = Mock(spec=User)
    user.email = "email@example.com"
    user.is_active = False
    user.hashed_password = hashed

    scalars_mock = Mock()
    scalars_mock.first.return_value = user
    result_mock = Mock()
    result_mock.scalars.return_value = scalars_mock

    async def execute(stmt):
        return result_mock

    mock_db_session.execute.side_effect = execute

    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/login/",
                json={"email": user.email, "password": plain}
            )

    assert response.status_code == 403
    assert response.json()["detail"] == "Accounts not activated."

@pytest.mark.asyncio
async def test_activate_user_success(override_dependencies, mock_db_session):
    user = Mock()
    user.id = 1
    user.is_active = False

    activation_token = Mock()
    activation_token.token = "valid_token"
    activation_token.user_id = user.id
    activation_token.expires_at = datetime.utcnow() + timedelta(minutes=10)

    scalars_mock = Mock()
    scalars_mock.first.return_value = activation_token
    result_mock = Mock()
    result_mock.scalars.return_value = scalars_mock

    mock_db_session.execute = AsyncMock(return_value=result_mock)
    mock_db_session.get = AsyncMock(return_value=user)
    mock_db_session.delete = AsyncMock()
    mock_db_session.commit = AsyncMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/accounts/activate/valid_token")

    assert response.status_code == 200
    assert response.json()["message"] == "Account activated successfully"
    assert user.is_active is True
    mock_db_session.delete.assert_called_with(activation_token)
    mock_db_session.commit.assert_called()

@pytest.mark.asyncio
async def test_activate_user_already_active(override_dependencies, mock_db_session):
    user = Mock()
    user.id = 1
    user.is_active = True

    activation_token = Mock()
    activation_token.token = "valid_token"
    activation_token.user_id = user.id
    activation_token.expires_at = datetime.utcnow() + timedelta(minutes=10)

    scalars_mock = Mock()
    scalars_mock.first.return_value = activation_token
    result_mock = Mock()
    result_mock.scalars.return_value = scalars_mock

    mock_db_session.execute = AsyncMock(return_value=result_mock)
    mock_db_session.get = AsyncMock(return_value=user)
    mock_db_session.delete = AsyncMock()
    mock_db_session.commit = AsyncMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("api/v1/accounts/activate/valid_token")

    assert response.status_code == 200
    assert response.json()["message"] == "Account already activated"

@pytest.mark.asyncio
async def test_reset_password_success(override_dependencies, mock_db_session):
    user = Mock()
    user.id = 1
    user.is_active = True

    class FakeResetToken:
        token = "valid_token"
        user_id = user.id
        expires_at = datetime.utcnow() + timedelta(minutes=10)

    scalars_mock = Mock()
    scalars_mock.first.return_value = FakeResetToken()
    result_mock = Mock()
    result_mock.scalars.return_value = scalars_mock

    mock_db_session.execute = AsyncMock(return_value=result_mock)
    mock_db_session.get = AsyncMock(return_value=user)
    mock_db_session.delete = AsyncMock()
    mock_db_session.commit = AsyncMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.put(
            "/api/v1/accounts/reset-password/",
            json={"token": "valid_token", "new_password": "Password1234!"}
        )
    assert response.status_code == 200
    assert response.json()["message"] == "Password successfully reset"
    mock_db_session.commit.assert_called()

@pytest.mark.asyncio
async def test_forgot_password_inactive_user_no_email(override_dependencies, mock_db_session):
    user = Mock()
    user.id = 1
    user.is_active = False
    user.email = "email@example.com"

    scalars_mock = Mock()
    scalars_mock.first.return_value = None
    result_mock = Mock()
    result_mock.scalars.return_value = scalars_mock

    async def execute(stmt):
        return result_mock

    mock_db_session.execute.side_effect = execute

    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/forgot-password/",
                json={"email": "email@example.com"}
            )
    assert response.status_code == 404