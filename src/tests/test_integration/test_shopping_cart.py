import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.dependencies import get_async_session, get_current_user
from src.database.models.movies import Movie
from src.database.models.shopping_cart import Cart, CartItem
from src.main import app

@pytest.fixture
def mock_db_session():
    mock_session = AsyncMock(spec=AsyncSession)

    async def refresh(instance):
        if hasattr(instance, "id") and getattr(instance, "id") is None:
            instance.id = 1

    mock_session.add = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=refresh)
    mock_session.delete = AsyncMock()
    mock_session.execute = AsyncMock()
    return mock_session

@pytest_asyncio.fixture
async def client(mock_db_session):
    async def mock_get_async_session():
        yield mock_db_session

    async def mock_get_current_user():
        user = Mock()
        user.id = 1
        user.email ="email@example.com"
        user.role = "user"
        return user

    app.dependency_overrides[get_async_session] = mock_get_async_session
    app.dependency_overrides[get_current_user] = mock_get_current_user

    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as ac:

            yield ac, mock_db_session

    app.dependency_overrides.clear()



@pytest.mark.asyncio
async def test_add_to_cart_success(client):
    ac, mock_db_session = client
    purchased_result = Mock()
    purchased_result.scalar_one_or_none.return_value = None
    cart_result = Mock()
    cart_result.scalar_one_or_none.return_value = None

    mock_db_session.execute.side_effect = [purchased_result, cart_result]

    response = await ac.post("/api/v1/shopping-cart/add/42")


    assert response.status_code == 200
    assert response.json() == {"message": "Movie added to cart"}

@pytest.mark.asyncio
async def test_add_to_cart_already_purchased(client):
    ac, mock_db_session = client
    purchased_result = Mock()
    purchased_result.scalar_one_or_none.return_value = 42
    mock_db_session.execute.return_value = purchased_result

    response = await ac.post("/api/v1/shopping-cart/add/42")

    assert response.status_code == 400
    assert response.json()["detail"] == "Movie already purchased"

@pytest.mark.asyncio
async def test_add_to_cart_already_in_cart(client):
    ac, mock_db_session = client
    purchased_result = Mock()
    purchased_result.scalar_one_or_none.return_value = None

    fake_cart = Cart(id=1, user_id=1)
    fake_cart.items = [CartItem(id=1, cart_id=1, movie_id=42)]

    cart_result = Mock()
    cart_result.scalar_one_or_none.return_value = fake_cart

    mock_db_session.execute.side_effect = [purchased_result, cart_result]

    response = await ac.post("/api/v1/shopping-cart/add/42")


    assert response.status_code == 400
    assert response.json()["detail"] == "Movie already in cart"

@pytest.mark.asyncio
async def test_remove_from_cart_success(client):
    ac, mock_db_session = client
    fake_item = CartItem(id=1, cart_id=1, movie_id=42)
    result = Mock()
    result.scalar_one_or_none.return_value = fake_item
    mock_db_session.execute.return_value = result

    response = await ac.delete("/api/v1/shopping-cart/remove/1")
    assert response.status_code == 200
    assert response.json() == {"message": "Movie removed from cart"}

@pytest.mark.asyncio
async def test_remove_from_cart_not_found(client):
    ac, mock_db_session = client

    result = Mock()
    result.scalar_one_or_none.return_value = None
    mock_db_session.execute.return_value = result

    response = await ac.delete("/api/v1/shopping-cart/remove/1")

    assert response.status_code == 404
    assert response.json()["detail"] == "Movie not in cart"

@pytest.mark.asyncio
async def test_get_cart_success(client):
    ac, mock_db_session = client

    cart_items_scalars = Mock()
    cart_items_scalars.all.return_value = [CartItem(id=1, cart_id=1, movie_id=42),
                                           CartItem(id=2, cart_id=1, movie_id=43)]
    cart_items_result = Mock()
    cart_items_result.scalars.return_value = cart_items_scalars

    movies_scalars = Mock()
    movies_scalars.all.return_value = [
        SimpleNamespace(
            id=42,
            uuid=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            title="Movie 42",
            name="Movie 42",
            time=120,
            description="Description 42",
            imdb=8.5,
            votes=1000,
            meta_score=85,
            gross=1000000,
            price=10.0,
            certification_id=1,
            year=2024
        ),
        SimpleNamespace(
            id=43,
            uuid=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            title="Movie 43",
            name="Movie 43",
            time=130,
            description="Description 43",
            imdb=8.0,
            votes=800,
            meta_score=80,
            gross=900000,
            price=12.0,
            certification_id=1,
            year=2024
        ),
    ]
    movies_result = Mock()
    movies_result.scalars.return_value = movies_scalars

    mock_db_session.execute.side_effect = [cart_items_result, movies_result]

    response = await ac.get("/api/v1/shopping-cart/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] == 42
    assert data[1]["id"] == 43

@pytest.mark.asyncio
async def test_clear_cart_success(client):
    ac, mock_db_session = client

    cart_items_result = Mock()
    cart_items_result.scalars.return_value.all.return_value = [
        CartItem(id=1, cart_id=1, movie_id=42),
        CartItem(id=2, cart_id=1, movie_id=43)
    ]

    mock_db_session.execute.return_value = cart_items_result

    response = await ac.delete("/api/v1/shopping-cart/clear")


    assert response.status_code == 200
    assert response.json() == {"message": "Cart cleared"}

@pytest.mark.asyncio
async def test_clear_cart_empty(client):
    ac, mock_db_session = client
    cart_items_result = Mock()
    cart_items_result.scalars.return_value.all.return_value = []
    mock_db_session.execute.return_value = cart_items_result

    response = await ac.delete("/api/v1/shopping-cart/clear")
    assert response.status_code == 200
    assert response.json() == {"message": "Cart cleared"}

@pytest.mark.asyncio
async def test_get_cart_empty(client):
    ac, mock_db_session = client
    cart_items_scalars = Mock()
    cart_items_scalars.all.return_value = []
    cart_items_result = Mock()
    cart_items_result.scalars.return_value = cart_items_scalars
    mock_db_session.execute.return_value = cart_items_result

    response = await ac.get("/api/v1/shopping-cart/")
    assert response.status_code == 200
    assert response.json() == []

@pytest.mark.asyncio
async def test_add_to_cart_db_error(client):
    ac, mock_db_session = client
    mock_db_session.execute.side_effect = Exception("Internal Server Error")

    response = await ac.post("/api/v1/shopping-cart/add/42")
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal Server Error"