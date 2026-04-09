import pytest
from httpx import AsyncClient


async def test_register_and_login_flow(client: AsyncClient):
    reg = await client.post("/api/v1/auth/register", json={
        "name": "Sam", "email": "sam@example.com",
        "password": "secure123", "language_pref": "en", "consent_given": True
    })
    assert reg.status_code == 200
    data = reg.json()["data"]
    assert "access_token" in data
    assert data["name"] == "Sam"

    login = await client.post("/api/v1/auth/login", json={
        "email": "sam@example.com", "password": "secure123"
    })
    assert login.status_code == 200
    assert "access_token" in login.json()["data"]


async def test_login_wrong_password_returns_401(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "name": "Test", "email": "test2@example.com",
        "password": "correct", "language_pref": "en", "consent_given": True
    })
    res = await client.post("/api/v1/auth/login", json={
        "email": "test2@example.com", "password": "wrong"
    })
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_register_duplicate_email_returns_409(client: AsyncClient):
    payload = {
        "name": "Dup", "email": "dup@example.com",
        "password": "pass123", "language_pref": "en", "consent_given": True
    }
    await client.post("/api/v1/auth/register", json=payload)
    res = await client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "USER_ALREADY_EXISTS"
