from decimal import Decimal
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, Mock
from asgi_lifespan import LifespanManager
from src.main import app
from src.database.models.accounts import User
from src.database.models.movies import Movie
from src.config.dependencies import get_async_session, get_current_user, get_current_admin_or_moderator


@pytest.fixture
def mock_db_session():
    mock_session = AsyncMock()

    async def refresh(instance):
        if hasattr(instance, "id"):
            instance.id = 1

    mock_session.add = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=refresh)
    mock_session.commit = AsyncMock()
    mock_session.execute = AsyncMock()
    return mock_session


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer token-user"}


@pytest.fixture
def admin_headers():
    return {"Authorization": "Bearer token-admin"}


@pytest.fixture
def mock_movies_db_session(mock_db_session):
    mock_db_session.cart_items_ids = []

    async def execute_side_effect(statement, *args, **kwargs):
        sql = str(statement)

        if "FROM movies" in sql:
            class Result:
                def scalars(inner_self):
                    class Scalar:
                        def all(self_inner):
                            return [
                                Movie(
                                    id=1,
                                    name="Inception",
                                    price=Decimal("10.0"),
                                    year=2010,
                                    time=148,
                                    imdb=8.8,
                                    votes=20000,
                                    meta_score=74,
                                    gross=829000,
                                    description="Mind-bending thriller",
                                    certification_id=1,
                                )
                            ]

                    return Scalar()

                def scalar_one_or_none(inner_self):
                    return Movie(
                        id=1,
                        name="Inception",
                        price=Decimal("10.0"),
                        year=2010,
                        time=148,
                        imdb=8.8,
                        votes=20000,
                        meta_score=74,
                        gross=829000,
                        description="Mind-bending thriller",
                        certification_id=1,
                    )

            return Result()

        if "FROM carts" in sql:
            class FakeCartItem:
                def __init__(self, movie_id):
                    self.movie_id = movie_id

            class FakeCart:
                id = 1
                user_id = 1
                items = [FakeCartItem(mid) for mid in mock_db_session.cart_items_ids]

            class Result:
                def scalar_one_or_none(inner_self):
                    return FakeCart()

                def all(inner_self):
                    return [FakeCart()]

            return Result()

        if "FROM order_items" in sql:
            class Result:
                def scalars(inner_self):
                    class Scalar:
                        def all(self_inner):
                            return []

                    return Scalar()

                def all(inner_self):
                    return []

                def scalar_one_or_none(inner_self):
                    return None

            return Result()

        class Result:
            def scalars(inner_self):
                class Scalar:
                    def all(self_inner):
                        return []

                return Scalar()

            def scalar_one_or_none(inner_self):
                return None

            def all(inner_self):
                return []

        return Result()

    mock_db_session.execute.side_effect = execute_side_effect
    return mock_db_session


@pytest_asyncio.fixture
async def client(mock_movies_db_session):
    async def mock_get_async_session():
        yield mock_movies_db_session

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

    app.dependency_overrides[get_async_session] = mock_get_async_session
    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[get_current_admin_or_moderator] = mock_get_current_admin

    async with LifespanManager(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_order_empty_movie_ids(client):
    response = await client.post("/api/v1/orders/", json={"movie_ids": []})
    assert response.status_code == 400
    assert response.json()["detail"] == "No movies selected."


@pytest.mark.asyncio
async def test_create_order_success(client):
    response = await client.post("/api/v1/orders/", json={"movie_ids": [1]})
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 1
    assert data["total_price"] == 10.0
    assert data["status"].lower() == "pending"
    assert len(data["movies"]) == 1
    assert data["movies"][0]["name"] == "Inception"
    assert data["movies"][0]["price"] == 10.0


@pytest.mark.asyncio
async def test_create_order_from_cart_empty(client):
    response = await client.post("/api/v1/orders/from-cart")
    assert response.status_code == 400
    assert response.json()["detail"] == "Cart is empty"


@pytest.mark.asyncio
async def test_get_orders(client):
    response = await client.get("/api/v1/orders/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_cancel_nonexistent_order(client):
    response = await client.delete("/api/v1/orders/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found"


@pytest.mark.asyncio
async def test_admin_get_all_orders(client):
    response = await client.get("/api/v1/orders/admin")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

@pytest.mark.asyncio
async def test_create_order_all_already_purchased(client, mock_movies_db_session):
    async def execute_side_effect(statement, *args, **kwargs):
        sql = str(statement)
        if "FROM order_items" in sql:
            class Result:
                def scalars(inner_self):
                    class Scalar:
                        def all(self_inner):
                            return [1]
                    return Scalar()
            return Result()
        return await mock_movies_db_session.execute(statement)
    mock_movies_db_session.execute.side_effect = execute_side_effect

    response = await client.post("/api/v1/orders/", json={"movie_ids": [1]})
    assert response.status_code == 400
    assert response.json()["detail"] == "All movies already purchased."

@pytest.mark.asyncio
async def test_cancel_order_pending(client, mock_movies_db_session):
    class FakeOrder:
        id = 1
        user_id = 1
        status = "pending"
    async def execute_side_effect(statement, *args, **kwargs):
        class Result:
            def scalar_one_or_none(inner_self):
                return FakeOrder()
        return Result()
    mock_movies_db_session.execute.side_effect = execute_side_effect

    response = await client.delete("/api/v1/orders/1")
    assert response.status_code == 204

@pytest.mark.asyncio
async def test_cancel_order_paid(client, mock_movies_db_session):
    class FakeOrder:
        id = 1
        user_id = 1
        status = "paid"
    async def execute_side_effect(statement, *args, **kwargs):
        class Result:
            def scalar_one_or_none(inner_self):
                return FakeOrder()
        return Result()
    mock_movies_db_session.execute.side_effect = execute_side_effect

    response = await client.delete("/api/v1/orders/1")
    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot cancel paid/canceled order"

@pytest.mark.asyncio
async def test_admin_get_all_orders_filter(client, mock_movies_db_session):
    response = await client.get("/api/v1/orders/admin?user_id=1&status_filter=paid")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        assert all(order["status"].lower() == "paid" for order in data)


@pytest.mark.asyncio
async def test_create_order_from_cart_all_ready_purchased(client, mock_movies_db_session):
    mock_movies_db_session.cart_items_ids.clear()
    mock_movies_db_session.cart_items_ids.append(1)

    async def execute_side_effect(statement, *args, **kwargs):
        sql = str(statement)

        if "FROM order_items" in sql:
            class Result:
                def all(inner_self):
                    return [(1,)]
            return Result()

        if "FROM carts" in sql:
            class FakeCartItem:
                def __init__(self, movie_id):
                    self.movie_id = movie_id

            class FakeCart:
                id = 1
                user_id = 1
                items = [FakeCartItem(mid) for mid in mock_movies_db_session.cart_items_ids]

            class Result:
                def scalar_one_or_none(inner_self):
                    return FakeCart()

                def all(inner_self):
                    return [FakeCart()]

            return Result()

        class Result:
            def all(inner_self):
                return []

            def scalar_one_or_none(inner_self):
                return None

            def scalars(inner_self):
                class Scalar:
                    def all(inner_self2):
                        return []
                return Scalar()
        return Result()

    mock_movies_db_session.execute.side_effect = execute_side_effect

    response = await client.post("/api/v1/orders/from-cart")

    assert response.status_code == 400
    assert response.json()["detail"] == "All movies already purchased"

