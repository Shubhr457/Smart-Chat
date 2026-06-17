"""
Auth flow tests — register, login, refresh rotation, protected route, logout.
Each test registers its own unique user to avoid cross-test collisions.
"""

import pytest
from httpx import AsyncClient

# Run all tests in this module on the session-scoped event loop so Motor's
# async client (created in the session fixture) doesn't get a loop mismatch.
pytestmark = pytest.mark.asyncio(loop_scope="session")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def user_payload(n: int) -> dict:
    return {
        "username": f"testuser{n}",
        "email": f"testuser{n}@example.com",
        "password": "TestPass123!",
    }


async def register_and_login(client: AsyncClient, n: int) -> dict:
    """Register user n and return the login token response body."""
    await client.post("/auth/register", json=user_payload(n))
    resp = await client.post(
        "/auth/login",
        json={"email": f"testuser{n}@example.com", "password": "TestPass123!"},
    )
    return resp.json()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


async def test_register_success(test_client: AsyncClient):
    resp = await test_client.post("/auth/register", json=user_payload(1))
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "testuser1"
    assert body["email"] == "testuser1@example.com"
    assert "id" in body
    assert "password" not in body
    assert "hashed_password" not in body


async def test_register_duplicate_email(test_client: AsyncClient):
    await test_client.post("/auth/register", json=user_payload(2))
    # Same email, different username
    duplicate = {**user_payload(2), "username": "differentuser"}
    resp = await test_client.post("/auth/register", json=duplicate)
    assert resp.status_code == 409
    assert "email" in resp.json()["detail"].lower()


async def test_register_duplicate_username(test_client: AsyncClient):
    await test_client.post("/auth/register", json=user_payload(3))
    # Same username, different email
    duplicate = {**user_payload(3), "email": "other3@example.com"}
    resp = await test_client.post("/auth/register", json=duplicate)
    assert resp.status_code == 409
    assert "username" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


async def test_login_success(test_client: AsyncClient):
    await test_client.post("/auth/register", json=user_payload(4))
    resp = await test_client.post(
        "/auth/login",
        json={"email": "testuser4@example.com", "password": "TestPass123!"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


async def test_login_wrong_password(test_client: AsyncClient):
    await test_client.post("/auth/register", json=user_payload(5))
    resp = await test_client.post(
        "/auth/login",
        json={"email": "testuser5@example.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


async def test_login_unknown_email(test_client: AsyncClient):
    resp = await test_client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "TestPass123!"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Protected route
# ---------------------------------------------------------------------------


async def test_protected_me_with_token(test_client: AsyncClient):
    tokens = await register_and_login(test_client, 6)
    resp = await test_client.get(
        "/protected/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == "testuser6"


async def test_protected_me_no_token(test_client: AsyncClient):
    resp = await test_client.get("/protected/me")
    # HTTPBearer returns 401 when Authorization header is absent
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Refresh token rotation
# ---------------------------------------------------------------------------


async def test_refresh_issues_new_tokens(test_client: AsyncClient):
    tokens = await register_and_login(test_client, 7)
    resp = await test_client.post(
        "/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert resp.status_code == 200
    new_tokens = resp.json()
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens


async def test_refresh_token_rotation(test_client: AsyncClient):
    """Old refresh token must be rejected after it has been rotated."""
    tokens = await register_and_login(test_client, 8)
    old_refresh = tokens["refresh_token"]

    # Use the refresh token once — this should succeed and invalidate old_refresh
    resp = await test_client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 200

    # Replay the old refresh token — must be rejected
    resp = await test_client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


async def test_logout_single_device(test_client: AsyncClient):
    tokens = await register_and_login(test_client, 9)
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]

    # Logout this device
    resp = await test_client.post(
        "/auth/logout",
        json={"refresh_token": refresh},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp.status_code == 200

    # Revoked refresh token must now be rejected
    resp = await test_client.post("/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 401


async def test_logout_all_devices(test_client: AsyncClient):
    """Login twice (two devices), logout-all, both refresh tokens rejected."""
    # Device 1
    tokens1 = await register_and_login(test_client, 10)
    # Device 2 — login again with the same account
    resp = await test_client.post(
        "/auth/login",
        json={"email": "testuser10@example.com", "password": "TestPass123!"},
    )
    tokens2 = resp.json()

    # Logout all devices using device 1's access token
    resp = await test_client.post(
        "/auth/logout-all",
        headers={"Authorization": f"Bearer {tokens1['access_token']}"},
    )
    assert resp.status_code == 200

    # Both refresh tokens must now be rejected
    r1 = await test_client.post(
        "/auth/refresh", json={"refresh_token": tokens1["refresh_token"]}
    )
    r2 = await test_client.post(
        "/auth/refresh", json={"refresh_token": tokens2["refresh_token"]}
    )
    assert r1.status_code == 401
    assert r2.status_code == 401
