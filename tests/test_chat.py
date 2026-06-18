import asyncio
import json
import pytest
from httpx import AsyncClient
from app.core.database import db_instance

pytestmark = pytest.mark.asyncio(loop_scope="session")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REGISTERED = {}

async def register_and_login(client: AsyncClient, email: str, username: str) -> dict:
    """Register and log in a user, returning token payload."""
    if email not in _REGISTERED:
        await client.post(
            "/auth/register",
            json={
                "username": username,
                "email": email,
                "password": "TestPass123!",
            },
        )
        _REGISTERED[email] = True
    
    resp = await client.post(
        "/auth/login",
        json={"email": email, "password": "TestPass123!"},
    )
    return resp.json()


def auth_headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# ---------------------------------------------------------------------------
# Standard Completion Tests
# ---------------------------------------------------------------------------

async def test_openai_completion_success(test_client: AsyncClient):
    tokens = await register_and_login(test_client, "user1@example.com", "user1")
    resp = await test_client.post(
        "/chat/completions",
        json={
            "model": "gpt-4o",
            "provider": "openai",
            "messages": [{"role": "user", "content": "Hello"}],
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "openai"
    assert body["model"] == "gpt-4o"
    assert "content" in body
    assert "total_tokens" in body


async def test_gemini_completion_success(test_client: AsyncClient):
    tokens = await register_and_login(test_client, "user1@example.com", "user1")
    resp = await test_client.post(
        "/chat/completions",
        json={
            "model": "gemini-1.5-flash",
            "provider": "gemini",
            "messages": [{"role": "user", "content": "Hello"}],
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "gemini"
    assert body["model"] == "gemini-1.5-flash"
    assert "content" in body


async def test_unsupported_provider(test_client: AsyncClient):
    tokens = await register_and_login(test_client, "user1@example.com", "user1")
    resp = await test_client.post(
        "/chat/completions",
        json={
            "model": "gpt-4o",
            "provider": "anthropic",
            "messages": [{"role": "user", "content": "Hello"}],
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 400
    assert "provider" in resp.json()["detail"].lower()


async def test_unsupported_model(test_client: AsyncClient):
    tokens = await register_and_login(test_client, "user1@example.com", "user1")
    resp = await test_client.post(
        "/chat/completions",
        json={
            "model": "gpt-fake",
            "provider": "openai",
            "messages": [{"role": "user", "content": "Hello"}],
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 400
    assert "model" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Streaming SSE Tests
# ---------------------------------------------------------------------------

async def test_streaming_sse_success(test_client: AsyncClient):
    tokens = await register_and_login(test_client, "user1@example.com", "user1")
    
    # Trigger streaming via query parameter
    resp = await test_client.post(
        "/chat/completions?stream=true",
        json={
            "model": "gpt-4o",
            "provider": "openai",
            "messages": [{"role": "user", "content": "Hi"}],
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    
    # Read first few lines of the stream
    stream_content = resp.text
    assert "data: {" in stream_content
    assert "delta" in stream_content


# ---------------------------------------------------------------------------
# Supported Models list
# ---------------------------------------------------------------------------

async def test_list_models_success(test_client: AsyncClient):
    tokens = await register_and_login(test_client, "user1@example.com", "user1")
    resp = await test_client.get("/chat/models", headers=auth_headers(tokens))
    assert resp.status_code == 200
    body = resp.json()
    assert "models" in body
    models = body["models"]
    assert len(models) == 4
    model_names = {m["name"] for m in models}
    assert "gpt-4o" in model_names
    assert "gemini-1.5-flash" in model_names


# ---------------------------------------------------------------------------
# Prompt Templates CRUD & Render
# ---------------------------------------------------------------------------

async def test_templates_lifecycle(test_client: AsyncClient):
    tokens = await register_and_login(test_client, "user_template@example.com", "template_user")
    headers = auth_headers(tokens)

    # 1. Create Template
    create_resp = await test_client.post(
        "/templates",
        json={
            "name": "Translation Template",
            "body": "Translate '{{text}}' to {{language}}.",
        },
        headers=headers,
    )
    assert create_resp.status_code == 200
    template = create_resp.json()
    template_id = template["id"]
    assert template["name"] == "Translation Template"

    # 2. List Templates
    list_resp = await test_client.get("/templates", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # 3. Retrieve Single Template
    get_resp = await test_client.get(f"/templates/{template_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Translation Template"

    # 4. Render Template
    render_resp = await test_client.post(
        f"/templates/{template_id}/render",
        json={
            "variables": {"text": "Good morning", "language": "Spanish"}
        },
        headers=headers,
    )
    assert render_resp.status_code == 200
    assert render_resp.json()["rendered"] == "Translate 'Good morning' to Spanish."

    # 5. Update Template
    update_resp = await test_client.put(
        f"/templates/{template_id}",
        json={"name": "New Name"},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "New Name"

    # 6. Delete Template (Soft delete)
    delete_resp = await test_client.delete(f"/templates/{template_id}", headers=headers)
    assert delete_resp.status_code == 200

    # 7. Querying again should fail with 404
    get_deleted_resp = await test_client.get(f"/templates/{template_id}", headers=headers)
    assert get_deleted_resp.status_code == 404


# ---------------------------------------------------------------------------
# Usage History & Admin stats
# ---------------------------------------------------------------------------

async def test_usage_logs_and_admin_stats(test_client: AsyncClient):
    tokens = await register_and_login(test_client, "user_analytics@example.com", "analytics_user")
    headers = auth_headers(tokens)

    # 1. Execute a completion to create usage records
    await test_client.post(
        "/chat/completions",
        json={
            "model": "gpt-4o",
            "provider": "openai",
            "messages": [{"role": "user", "content": "Trigger logs check"}],
        },
        headers=headers,
    )
    
    # Allow background logging task to execute
    await asyncio.sleep(0.1)

    # 2. Get Usage Log history (user-scoped)
    usage_resp = await test_client.get("/usage", headers=headers)
    assert usage_resp.status_code == 200
    usage_data = usage_resp.json()
    assert usage_data["total"] >= 1
    assert len(usage_data["records"]) >= 1
    assert usage_data["records"][0]["model"] == "gpt-4o"

    # 3. Query Admin endpoint without admin role (should fail with 403)
    admin_fail_resp = await test_client.get("/admin/usage/stats", headers=headers)
    assert admin_fail_resp.status_code == 403

    # 4. Escalate user to Admin role in the database directly
    await db_instance.db["users"].update_one(
        {"email": "user_analytics@example.com"},
        {"$set": {"role": "admin"}}
    )

    # Re-login to get token with admin role claim
    admin_tokens = await register_and_login(test_client, "user_analytics@example.com", "analytics_user")
    admin_headers = auth_headers(admin_tokens)

    # 5. Query Admin endpoint again (should succeed)
    admin_ok_resp = await test_client.get("/admin/usage/stats", headers=admin_headers)
    assert admin_ok_resp.status_code == 200
    admin_data = admin_ok_resp.json()
    assert admin_data["total_requests"] >= 1
    assert len(admin_data["breakdown"]) >= 1
    assert admin_data["breakdown"][0]["model"] == "gpt-4o"


# ---------------------------------------------------------------------------
# Rate Limiting Throttling Test
# ---------------------------------------------------------------------------

async def test_rate_limit_exceeded(test_client: AsyncClient):
    tokens = await register_and_login(test_client, "user_ratelimit@example.com", "limiter_user")
    headers = auth_headers(tokens)

    # Send 22 rapid completions (20 is the default limit per minute)
    # We execute them concurrently to trigger the throttling immediately
    tasks = [
        test_client.post(
            "/chat/completions",
            json={
                "model": "gpt-3.5-turbo",
                "provider": "openai",
                "messages": [{"role": "user", "content": f"Test {i}"}],
            },
            headers=headers,
        )
        for i in range(22)
    ]

    responses = await asyncio.gather(*tasks)
    status_codes = [r.status_code for r in responses]

    # Verify that at least one request failed with 429
    assert 429 in status_codes
    
    # Verify the 429 JSON response structure (custom handler validation)
    error_response = next(r for r in responses if r.status_code == 429).json()
    assert error_response["error"] == "rate_limit_exceeded"
    assert "retry_after_seconds" in error_response
