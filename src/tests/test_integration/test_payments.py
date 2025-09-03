from datetime import datetime
from types import SimpleNamespace

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, Mock
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.main import app
from src.database.models.accounts import User
from src.database.models.orders import Order, OrderStatusEnum
from src.database.models.payments import Payment, PaymentStatusEnum
from src.config.dependencies import get_async_session, get_current_user, get_current_admin_or_moderator
from src.tasks.accounts import send_reset_email_async


@pytest.fixture
def mock_db_session():
    mock_session = AsyncMock()

    async def refresh(instance):
        if hasattr(instance, "id"):
            instance.id = 1

    mock_session.add = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=refresh)
    mock_session.execute = AsyncMock()
    return mock_session


@pytest_asyncio.fixture
async def client(mock_db_session):
    async def mock_get_async_session():
        yield mock_db_session

    async def mock_get_current_user():
        user = Mock(spec=User)
        user.id = 1
        user.email = "user@example.com"
        user.role = "user"
        return user

    async def mock_get_current_admin():
        admin = Mock(spec=User)
        admin.id = 2
        admin.email = "admin@example.com"
        admin.role = "admin"
        return admin

    mock_email_service = AsyncMock()
    mock_email_service.send_email = AsyncMock()

    async def mock_send_reset_email_async():
        return mock_email_service

    app.dependency_overrides[get_async_session] = mock_get_async_session
    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[get_current_admin_or_moderator] = mock_get_current_admin
    app.dependency_overrides[send_reset_email_async] = mock_send_reset_email_async

    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as ac:
            yield ac, mock_email_service

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_initiate_payment_success(client, mock_db_session):
    client_instance, _ = client
    order = Order(id=1, user_id=1, status="pending")
    order.total_amount = Decimal("10.0")

    payment = Payment(
        id=1,
        order_id=1,
        user_id=1,
        amount=Decimal("10.0"),
        status=PaymentStatusEnum.pending,
        created_at=datetime.utcnow(),
        external_payment_id=None,
    )

    class FakeResult:
        def scalar_one_or_none(self):
            return order

    async def execute_side_effect(statement, *args, **kwargs):
        sql = str(statement)
        if "FROM orders" in sql:
            return FakeResult()
        if "FROM payments" in sql:
            class FakePaymentResult:
                def scalar_one_or_none(inner_self):
                    return None
            return FakePaymentResult()
        return FakeResult()

    async def fake_refresh(obj):
        obj.id = payment.id
        obj.created_at = payment.created_at
        obj.user_id = payment.user_id
        obj.order_id = payment.order_id
        obj.amount = payment.amount
        obj.status = payment.status
        obj.external_payment_id = payment.external_payment_id

    mock_db_session.execute.side_effect = execute_side_effect
    mock_db_session.add = AsyncMock()
    mock_db_session.commit = AsyncMock()
    mock_db_session.refresh = AsyncMock(side_effect=fake_refresh)

    response = await client_instance.post("/api/v1/payments/initiate", params={"order_id": 1})
    assert response.status_code == 200
    data = response.json()
    assert data["order_id"] == 1
    assert data["status"] == "pending"
    assert float(data["amount"]) == 10.0


@pytest.mark.asyncio
async def test_initiate_payment_order_not_found(client, mock_db_session):
    client_instance, _ = client
    class FakeResult:
        def scalar_one_or_none(self):
            return None

    mock_db_session.execute = AsyncMock(return_value=FakeResult())

    response = await client_instance.post("/api/v1/payments/initiate", params={"order_id": 999})
    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found"


@pytest.mark.asyncio
async def test_initiate_payment_already_paid(client, mock_db_session):
    client_instance, _ = client
    order = Order(id=1, user_id=1, status=OrderStatusEnum.pending)
    order.total_amount = Decimal("10.0")

    class FakeResult:
        def scalar_one_or_none(self):
            return order

    mock_db_session.execute = AsyncMock(return_value=FakeResult())

    response = await client_instance.post("/api/v1/payments/initiate", params={"order_id": 1})
    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot initiate payment for paid/canceled order"

from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_webhook_success(mock_db_session):
    class MockEmailService:
        def __init__(self):
            self.send_email = AsyncMock()

    mock_email_service = MockEmailService()

    async def mock_send_reset_email_async():
        return mock_email_service

    app.dependency_overrides[get_async_session] = lambda: mock_db_session
    app.dependency_overrides[send_reset_email_async] = mock_send_reset_email_async

    mock_user = MagicMock(spec=User)
    mock_user.email = "user@example.com"
    mock_user._sa_instance_state = MagicMock()

    payment = Payment(
        id=1,
        order_id=1,
        user_id=1,
        amount=Decimal("10.0"),
        status=PaymentStatusEnum.pending,
        created_at=datetime.utcnow()
    )
    payment.user = mock_user

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = payment
    mock_db_session.execute.return_value = mock_result

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        payload = {"payment_id": 1, "status": "successful"}
        response = await ac.post("/api/v1/payments/webhook", json=payload)

    assert response.status_code == 200
    assert response.json() == {"message": "Payment status updated"}
    assert payment.status == "successful"
    mock_email_service.send_email.assert_awaited_once()

    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_initiate_payment_already_initiated(client, mock_db_session):
    client_instance, _ = client
    order = Order(id=1, user_id=1, status="pending")
    order.total_amount = Decimal("10.0")

    existing_payment = Payment(
        id=1,
        order_id=1,
        user_id=1,
        amount=Decimal("10.0"),
        status=PaymentStatusEnum.pending,
        created_at=datetime.utcnow()
    )

    async def execute_side_effect(statement, *args, **kwargs):
        sql = str(statement)
        if "FROM orders" in sql:
            class FakeOrderResult:
                def scalar_one_or_none(inner_self):
                    return order
            return FakeOrderResult()
        if "FROM payments" in sql:
            class FakePaymentResult:
                def scalar_one_or_none(inner_self):
                    return existing_payment
            return FakePaymentResult()
        return AsyncMock()

    mock_db_session.execute.side_effect = execute_side_effect

    response = await client_instance.post("/api/v1/payments/initiate", params={"order_id": 1})
    assert response.status_code == 400
    assert response.json()["detail"] == "Payment already initiated"

@pytest.mark.asyncio
async def test_webhook_invalid_json(mock_db_session):
    app.dependency_overrides[get_async_session] = lambda: mock_db_session
    app.dependency_overrides[send_reset_email_async] = lambda: AsyncMock()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        response = await ac.post(
            "/api/v1/payments/webhook",
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )

        print(response.text)
        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid JSON"}

    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_admin_payments_filter_by_user_and_status(mock_db_session: AsyncSession):
    async def mock_get_current_admin():
        return SimpleNamespace(id=2, email="admin@example.com", role="admin")

    app.dependency_overrides[get_async_session] = lambda: mock_db_session
    app.dependency_overrides[get_current_admin_or_moderator] = mock_get_current_admin

    payment = Payment(
        id=1,
        order_id=1,
        user_id=1,
        amount=Decimal("10.0"),
        status=PaymentStatusEnum.successful,
        created_at=datetime.utcnow()
    )

    mock_scalars = AsyncMock()
    mock_scalars.all.return_value = [payment]
    mock_execute_result = Mock()
    mock_execute_result.scalars.return_value = mock_scalars
    mock_db_session.execute.return_value = mock_execute_result

    async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
    ) as client_instance:
        response = await client_instance.get(
            "/api/v1/payments/admin",
            params={"user_id": 1, "status": "successful"}
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == 1
    assert data[0]["user_id"] == 1
    assert data[0]["status"] == "successful"
    assert float(data[0]["amount"]) == 10.0

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_payments_no_results(mock_db_session: AsyncSession):
    async def mock_get_current_admin():
        return SimpleNamespace(id=2, email="admin@example.com", role="admin")

    app.dependency_overrides[get_async_session] = lambda: mock_db_session
    app.dependency_overrides[get_current_admin_or_moderator] = mock_get_current_admin

    mock_scalars = AsyncMock()
    mock_scalars.all.return_value = []
    mock_execute_result = Mock()
    mock_execute_result.scalars.return_value = mock_scalars
    mock_db_session.execute.return_value = mock_execute_result

    async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
    ) as client_instance:
        response = await client_instance.get(
            "/api/v1/payments/admin",
            params={"user_id": 1, "status": "successful"}
        )

    assert response.status_code == 200
    assert response.json() == []
    app.dependency_overrides.clear()
