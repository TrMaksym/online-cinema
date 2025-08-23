import contextlib
import uuid
from decimal import Decimal
import pytest
from unittest.mock import AsyncMock, Mock, MagicMock

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.movies import Movie, Purchase, Favorite
from src.main import app
from src.router.accounts import get_async_session
from src.router.movies import get_genres_by_ids, get_directors_by_ids, get_stars_by_ids, fake_likes_storage, \
    fake_ratings_storage
from src.tests.test_integration.test_accounts import test_resend_activation_success


@pytest.fixture
def mock_db_session():
    mock_session = AsyncMock()

    async def refresh(instance):
        instance.id = 1
        instance.uuid = "00000000-0000-0000-0000-000000000001"

    mock_session.add = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=refresh)
    mock_session.execute = AsyncMock()

    mock_result = AsyncMock()

    def mock_scalars():
        class MockScalarResult:
            def all(self_inner):
                return []
        return MockScalarResult()

    mock_result.scalars = mock_scalars
    mock_session.execute.return_value = mock_result

    return mock_session


@pytest.fixture
def mock_db_objects():
    class MockMovie:
        id = 1
        uuid = str(uuid.UUID("00000000-0000-0000-0000-000000000001"))
        name = "Inception"
        year = 2010
        time = 148
        imdb = 8.8
        votes = 20000
        meta_score = 74.0
        gross = 829000.0
        description = "Mind-bending thriller"
        price = Decimal("10.00")
        certification_id = 1
        genres = []
        directors = []
        stars = []

    class MockResult:
        def scalar_one_or_none(self):
            return MockMovie()

        def scalars(self):
            class Scalar:
                def all(self_inner):
                    return [MockMovie()]
            return Scalar()

    class MockSession:
        async def execute(self, *args, **kwargs):
            return MockResult()

        async def add(self, instance):
            pass

        async def commit(self):
            pass

        async def refresh(self, instance):
            pass

    return MockSession()

@pytest_asyncio.fixture
async def client(override_dependencies, mock_db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_movie_db_session():
    mock_session = AsyncMock()

    movie_instance = Movie(
        id=1,
        name="Inception",
        year=2010,
        time=148,
        imdb=8.8,
        votes=20000,
        meta_score=74,
        gross=829000,
        description="Mind-bending thriller",
        price=10.0,
        certification_id=1
    )

    async def refresh(instance):
        instance.id = movie_instance.id
        instance.uuid = "00000000-0000-0000-0000-000000000001"

    mock_session.add = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=refresh)

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none = Mock(return_value=movie_instance)

    mock_session.execute = AsyncMock(return_value=mock_result)

    return mock_session


@pytest.fixture
def mock_delete_db_session():
    mock_session = AsyncMock()

    movie_instance = Movie(
        id=1,
        name="Inception",
        year=2010,
        time=148,
        imdb=8.8,
        votes=20000,
        meta_score=74,
        gross=829000,
        description="Mind-bending thriller",
        price=10.0,
        certification_id=1
    )

    class MovieResult:
        async def scalar_one_or_none(self):
            return movie_instance

    movie_result = MovieResult()

    class PurchaseResult:
        async def scalar_one_or_none(self):
            return None

    purchase_result = PurchaseResult()

    async def execute_side_effect(statement, *args, **kwargs):
        if statement.column_descriptions[0]['entity'] == Purchase:
            return purchase_result
        if statement.column_descriptions[0]['entity'] == Movie:
            return movie_result
        return AsyncMock()

    mock_session.execute = AsyncMock(side_effect=execute_side_effect)
    mock_session.delete = AsyncMock(return_value=None)
    mock_session.commit = AsyncMock(return_value=None)

    return mock_session



@pytest.fixture
def override_dependencies(mock_db_session):
    async def mock_get_async_session():
        yield mock_db_session

    app.dependency_overrides[get_async_session] = mock_get_async_session

    async def mock_get_entities(ids, db):
        return []

    app.dependency_overrides[get_genres_by_ids] = mock_get_entities
    app.dependency_overrides[get_directors_by_ids] = mock_get_entities
    app.dependency_overrides[get_stars_by_ids] = mock_get_entities

    yield
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_create_movie(override_dependencies, mock_db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/movies/",
            json={
                "name": "Inception",
                "year": 2010,
                "time": 148,
                "imdb": 8.8,
                "votes": 20000,
                "meta_score": 74,
                "gross": 829000,
                "description": "Mind-bending thriller",
                "price": 10.0,
                "certification_id": 1,
                "genres": [],
                "directors": [],
                "stars": []
            }
        )

    assert response.status_code == 201
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once()
    mock_db_session.execute.assert_not_called()

@pytest.mark.asyncio
async def test_create_movie_with_empty_genres(override_dependencies, mock_db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/movies/",
            json={
                "name": "Inception",
                "year": "not_a_number",
                "time": 148,
                "imdb": 8.8,
                "votes": 20000,
                "meta_score": 74,
                "gross": 829000,
                "description": "Mind-bending thriller",
                "price": 10.0,
                "certification_id": 1,
                "genres": [],
                "directors": [],
                "stars": []
            }
        )

    assert response.status_code == 422
    mock_db_session.add.assert_not_called()

@pytest.mark.asyncio
async def test_create_movie_with_relations(override_dependencies, mock_db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/movies/", json={
            "name": "Inception",
            "year": 2010,
            "time": 148,
            "imdb": 8.8,
            "votes": 20000,
            "meta_score": 74,
            "gross": 829000,
            "description": "Mind-bending thriller",
            "price": 10.0,
            "certification_id": 1,
            "genres": [1, 2],
            "directors": [1],
            "stars": [1, 2, 3]
        })

    assert response.status_code == 201
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once()

@pytest.mark.asyncio
async def test_get_movies_list(override_dependencies, mock_db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/movies/",
                                params={"search": "Inception"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)

@pytest.mark.asyncio
async def test_get_movie_by_id(mock_db_objects):
    app.dependency_overrides[get_async_session] = lambda: mock_db_objects

    async with LifespanManager(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/v1/movies/1")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["uuid"] == "00000000-0000-0000-0000-000000000001"
    assert data["name"] == "Inception"


@pytest.mark.asyncio
async def test_update_movie(mock_movie_db_session):
    async def mock_get_async_session():
        yield mock_movie_db_session

    app.dependency_overrides[get_async_session] = mock_get_async_session

    payload = {
        "name": "Inception Updated",
        "year": 2011,
        "time": 148,
        "imdb": 8.8,
        "votes": 20000,
        "meta_score": 74,
        "gross": 829000,
        "description": "Mind-bending thriller",
        "price": 10.0,
        "certification_id": 1,
        "genres": [],
        "directors": [],
        "stars": []
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.put("/api/v1/movies/1", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Inception Updated"
    assert data["year"] == 2011


@pytest.mark.asyncio
async def test_delete_movie(mock_delete_db_session):
    async def mock_get_async_session():
        yield mock_delete_db_session

    app.dependency_overrides[get_async_session] = mock_get_async_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.delete("/api/v1/movies/1")

    assert response.status_code == 204, f"Expected status code 204, got {response.status_code}: {response.text}"
    mock_delete_db_session.delete.assert_called_once()
    mock_delete_db_session.commit.assert_called_once()
    mock_delete_db_session.execute.assert_called()
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_get_movies_invalid_params(override_dependencies, mock_db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/movies/", params={"search": "Inception", "invalid_param": "some_value"})
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_add_to_favorites_success(override_dependencies, mock_db_session):
    user_id = 42
    movie_id = 100
    favorite_id = 1

    mock_db_session.add = AsyncMock()
    mock_db_session.commit = AsyncMock()

    fake_favorite = MagicMock()
    fake_favorite.id = favorite_id
    fake_favorite.user_id = user_id
    fake_favorite.movie_id = movie_id

    mock_db_session.refresh = AsyncMock()

    async def execute(stmt, *args, **kwargs):
        print("EXECUTE STMT:", stmt)
        stmt_str = str(stmt).lower()

        class FakeResult:
            async def scalar_one_or_none(inner_self):
                if "from users" in stmt_str:
                    fake_user = MagicMock()
                    fake_user.id = user_id
                    return fake_user
                if "from favorites" in stmt_str:
                    return None
                return None

        return FakeResult()

    mock_db_session.execute.side_effect = execute

    def refresh_patch(obj):
        obj.id = favorite_id
        obj.user_id = user_id
        obj.movie_id = movie_id
    mock_db_session.refresh.side_effect = refresh_patch

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/movies/favorites",
            json={"user_id": user_id, "movie_id": movie_id}
        )

    assert response.status_code == 201, f"Response body: {response.text}"
    data = response.json()
    assert data["id"] == favorite_id
    assert data["user_id"] == user_id
    assert data["movie_id"] == movie_id

    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once()
    mock_db_session.execute.assert_called()

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_add_to_favorites_duplicate(override_dependencies, mock_db_session):
    user_id = 42
    movie_id = 100
    favorite_id = 1

    async def execute(stmt, *args, **kwargs):
        result = AsyncMock()
        async def scalar_one_or_none():
            return favorite_id
        result.scalar_one_or_none = scalar_one_or_none
        return result

    mock_db_session.execute.side_effect = execute

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/movies/favorites",
            json={"user_id": user_id, "movie_id": movie_id}
        )

    assert response.status_code == 400, f"Response body: {response.text}"
    assert response.json()["detail"] == "Already in favorites"
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()

@pytest.mark.asyncio
async def test_add_to_favorites_missing_fields(override_dependencies, mock_db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/movies/favorites",
            json={"user_id": 42}
        )
    assert response.status_code == 422, f"Response body: {response.text}"
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()

@pytest.mark.asyncio
async def test_add_to_favorites_invalid_data(override_dependencies, mock_db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/movies/favorites",
            json={"user_id": "string", "movie_id": "not_int"}
        )
    assert response.status_code == 422, f"Response body: {response.text}"
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()

@pytest.mark.asyncio
async def test_add_to_favorites_nonexistent_user(override_dependencies, mock_db_session):
    user_id = 42
    movie_id = 9999

    async def execute(stmt, *args, **kwargs):
        result = AsyncMock()
        async def scalar_one_or_none():
            return None
        result.scalar_one_or_none = scalar_one_or_none
        return result

    mock_db_session.execute.side_effect = execute

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/movies/favorites",
            json={"user_id": user_id, "movie_id": movie_id}
        )
        assert response.status_code == 404, f"Response body: {response.text}"

@pytest.mark.asyncio
async def test_remove_nonexistent_favorite(override_dependencies, mock_db_session):
    user_id = 42
    movie_id = 999

    async def execute(statement, *args, **kwargs):
        class Result:
            def scalar_one_or_none(inner_self):
                return None
        return Result()

    mock_db_session.execute.side_effect = execute
    mock_db_session.delete = AsyncMock()
    mock_db_session.commit = AsyncMock()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.delete(
            f"/api/v1/movies/{movie_id}/favorite?user_id={user_id}"
        )
        assert response.status_code == 404
        assert "Favorite not found" in response.text

@pytest.mark.asyncio
async def test_list_genres(client):
    response = await client.get("/api/v1/movies/genres")
    print(response.status_code)
    print(response.json())

    assert response.status_code == 200
    genres = response.json()
    assert isinstance(genres, list)
    for genre in genres:
        assert "id" in genre
        assert "name" in genre
        assert "movie_count" in genre

@pytest.mark.asyncio
async def test_list_genres_empty(client, mock_db_session):
    await mock_db_session.execute("DELETE FROM genres")
    await mock_db_session.commit()

    response = await client.get("/api/v1/movies/genres")
    assert response.status_code == 200
    genres = response.json()
    assert genres == []

@pytest.mark.asyncio
async def test_like_movie(override_dependencies, mock_db_session):
    user_id = 42
    movie_id = 100

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(f"/api/v1/movies/{movie_id}/like?user_id={user_id}")

    assert response.status_code == 501
    key = f"{user_id}:{movie_id}"
    assert fake_likes_storage[key] is True
    assert f"User {user_id} liked movie {movie_id}" in response.json()["message"]

@pytest.mark.asyncio
async def test_dislike_movie(override_dependencies, mock_db_session):
    user_id = 42
    movie_id = 100

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(f"/api/v1/movies/{movie_id}/dislike?user_id={user_id}")
    assert response.status_code == 501
    key = f"{user_id}:{movie_id}"
    assert fake_likes_storage[key] is False
    assert f"User {user_id} disliked movie {movie_id}" in response.json()["message"]

@pytest.mark.asyncio
async def test_rate_movie(override_dependencies, mock_db_session):
    user_id = 42
    movie_id = 100
    rating_value = 5
    payload = {"user_id": user_id, "movie_id": movie_id, "rating": rating_value}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(f"/api/v1/movies/{movie_id}/rate", json=payload)

    key = f"{user_id}:{movie_id}"
    assert response.status_code == 501
    assert fake_ratings_storage[key] == rating_value
    assert f"User {user_id} rated movie {movie_id} with rating {rating_value}" in response.json()["message"]

@pytest.mark.asyncio
async def test_create_comment(override_dependencies, mock_db_session):
    user_id = 42
    movie_id = 100
    payload = {
        "user_id": user_id,
        "text": "Test comment",
        "parent_id": None
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(f"/api/v1/movies/{movie_id}/comments/", json=payload)

    assert response.status_code == 201
    mock_db_session.add.assert_called()
    mock_db_session.commit.assert_awaited()
    mock_db_session.refresh.assert_awaited()

@pytest.mark.asyncio
async def test_get_comments(override_dependencies, mock_db_session):
    movie_id = 1

    mock_comment = MagicMock()
    mock_comment.id = 1
    mock_comment.text = "Test comment"

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_comment]

    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value = mock_scalars

    mock_db_session.execute = AsyncMock(return_value=mock_execute_result)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/api/v1/movies/{movie_id}/comments/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == 1
    assert data[0]["text"] == "Test comment"


@pytest.mark.asyncio
async def test_delete_comment(override_dependencies, mock_db_session):
    comment_id = 1
    movie_id = 1
    mock_comment = MagicMock()
    mock_comment.id = 1

    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = mock_comment
    mock_db_session.execute = AsyncMock(return_value=mock_execute_result)

    mock_db_session.delete = AsyncMock()
    mock_db_session.commit = AsyncMock()

    print(f"Mock DB session: {mock_db_session}")
    print(f"Dependency overrides: {app.dependency_overrides}")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.delete(f"/api/v1/movies/{movie_id}/comments/{comment_id}")
        print(f"Response status: {response.status_code}, Response body: {response.text}")

    assert response.status_code == 200, f"Expected status 200, got {response.status_code}: {response.text}"
    mock_db_session.delete.assert_awaited_with(mock_comment)
    mock_db_session.commit.assert_awaited()