import pytest
from httpx import AsyncClient
from fastapi import status

from src.main import app


@pytest.fixture
async def async_client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_register_user(async_client):
    payload = {"email": "testuser@example.com", "password": "Pass123456"}
    response = await async_client.post("/register/", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["email"] == payload["email"]


@pytest.mark.asyncio
async def test_register_existing_user(async_client):
    payload = {"email": "existuser@example.com", "password": "Pass123456"}

    resp1 = await async_client.post("/register/", json=payload)
    assert resp1.status_code == status.HTTP_201_CREATED

    resp2 = await async_client.post("/register/", json=payload)
    assert resp2.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_register_weak_password(async_client):
    payload = {"email": "weakpass@example.com", "password": "123"}
    response = await async_client.post("/register/", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_login_and_logout(async_client):
    reg = {"email": "loginuser@example.com", "password": "Pass123456"}
    await async_client.post("/register/", json=reg)
    login_resp = await async_client.post("/login/", json=reg)
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    logout_resp = await async_client.post(
        "/logout/", params={"refresh_token": tokens["refresh_token"]}
    )
    assert logout_resp.status_code == 200


@pytest.mark.asyncio
async def test_forgot_password(async_client):
    reg = {"email": "forgotme@example.com", "password": "Pass123456"}
    await async_client.post("/register/", json=reg)
    resp = await async_client.post("/forgot-password/", json={"email": reg["email"]})
    assert resp.status_code == 200
    assert "Password reset" in resp.json()["message"]


@pytest.mark.asyncio
async def test_forgot_password_no_user(async_client):
    resp = await async_client.post(
        "/forgot-password/", json={"email": "nope@example.com"}
    )
    assert resp.status_code == 404
    assert "does not exist" in resp.json()["detail"]
