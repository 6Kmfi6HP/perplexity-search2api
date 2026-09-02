import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from server import app

client = TestClient(app)


def test_root_index():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "Perplexity Search2API" in data["service"]


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_models_list():
    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert len(data["data"]) > 0
    ids = [m["id"] for m in data["data"]]
    assert "gpt-5.6" in ids
    assert "claude-3-7-sonnet" in ids
    assert "experimental" in ids


def test_get_single_model():
    response = client.get("/v1/models/gpt-5.6")
    assert response.status_code == 200
    assert response.json()["id"] == "gpt-5.6"

    # Non-existent model
    response_404 = client.get("/v1/models/non-existent-model-xyz")
    assert response_404.status_code == 404


def test_api_key_auth(monkeypatch):
    monkeypatch.setenv("API_KEY", "test_secret_key")

    # Without key -> 401
    resp_no_key = client.get("/v1/models")
    assert resp_no_key.status_code == 401

    # With invalid key -> 401
    resp_bad_key = client.get("/v1/models", headers={"Authorization": "Bearer bad_key"})
    assert resp_bad_key.status_code == 401

    # With valid key -> 200
    resp_ok = client.get("/v1/models", headers={"Authorization": "Bearer test_secret_key"})
    assert resp_ok.status_code == 200


def test_chat_completions_non_stream():
    mock_res = {
        "query": "Hello",
        "answer": "This is a test answer from Perplexity [1].",
        "sources": [{"name": "Doc 1", "url": "https://example.com/doc1"}],
        "model": "claude-3-7-sonnet",
        "raw_event": {},
    }

    with patch("server.PerplexityClient.ask_async", new=AsyncMock(return_value=mock_res)):
        payload = {
            "model": "claude-3-7-sonnet",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False,
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "chat.completion"
        assert len(data["choices"]) == 1
        assert "This is a test answer" in data["choices"][0]["message"]["content"]
        assert "usage" in data


def test_get_single_model_not_found():
    response = client.get("/v1/models/non-existent-model-xyz")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data["detail"]


def test_search_endpoint():
    mock_res = {
        "query": "Test Search",
        "answer": "Search answer content",
        "sources": [{"name": "S1", "url": "https://example.com/s1"}],
        "model": "experimental",
    }
    with patch("server.PerplexityClient.ask_async", new=AsyncMock(return_value=mock_res)):
        resp = client.post("/search", json={"query": "Test Search"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "Search answer content"
        assert len(data["sources"]) == 1


def test_chat_completions_stream():
    async def mock_ask_stream(query, model, mode):
        yield {
            "type": "progress",
            "sources_count": 1,
            "display_model": "claude-3-7-sonnet",
        }
        yield {
            "type": "delta",
            "delta": "Hello ",
            "answer": "Hello ",
            "sources": [{"name": "Doc 1", "url": "https://example.com/doc1"}],
            "display_model": "claude-3-7-sonnet",
        }
        yield {
            "type": "delta",
            "delta": "world [1]!",
            "answer": "Hello world [1]!",
            "sources": [{"name": "Doc 1", "url": "https://example.com/doc1"}],
            "display_model": "claude-3-7-sonnet",
        }

    with patch("server.PerplexityClient.ask_async_stream", side_effect=mock_ask_stream):
        payload = {
            "model": "claude-3-7-sonnet",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
            "smooth_stream": False,
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = response.text
        assert "data: " in body
        assert "[DONE]" in body


# ---------- 修复回归测试 ----------


def test_auth_info_does_not_leak_session_token(monkeypatch):
    """回归: /auth/info 不得回传 session_token / org_token / cookies"""
    import json as _json
    import tempfile
    from pathlib import Path as _Path

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp.write(
            _json.dumps(
                {
                    "session_token": "SECRET-TOKEN-XYZ",
                    "org_token": "ORG-SECRET-XYZ",
                    "cookies": {"__Secure-next-auth.session-token": "SECRET-TOKEN-XYZ"},
                    "user": {"name": "T", "email": "t@example.com"},
                    "expires_at": "2099-01-01T00:00:00Z",
                }
            ).encode()
        )
        tmp_name = tmp.name
    try:
        monkeypatch.setenv("PERPLEXITY_SESSION_PATH", tmp_name)
        resp = client.get("/auth/info")
        assert resp.status_code == 200
        data = resp.json()
        assert "SECRET-TOKEN-XYZ" not in resp.text
        assert data["session_token"] == "***configured***"
        assert data["org_token"] == "***configured***"
        assert set(data["cookies"].values()) == {"***"}
        # 状态展示所需字段保留
        assert data["user"]["email"] == "t@example.com"
        assert data["expires_at"] == "2099-01-01T00:00:00Z"
    finally:
        _Path(tmp_name).unlink(missing_ok=True)


def test_chat_stream_done_sent_after_error():
    """回归: 上游异常后仍应以单个 [DONE] 收尾, 且不再依赖 finally 中的 yield"""

    async def failing_stream(*args, **kwargs):
        yield {
            "type": "delta",
            "delta": "partial",
            "answer": "partial",
            "sources": [],
            "display_model": "experimental",
        }
        raise RuntimeError("upstream boom")

    with patch(
        "server.PerplexityClient.ask_async_stream",
        new=MagicMock(side_effect=failing_stream),
    ):
        payload = {
            "model": "experimental",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
            "smooth_stream": False,
        }
        resp = client.post("/v1/chat/completions", json=payload)
        body = resp.text
        assert "upstream boom" in body
        assert body.count("data: [DONE]") == 1
        assert body.rstrip().endswith("data: [DONE]")


async def test_non_stream_does_not_block_event_loop(monkeypatch):
    """回归: 非流式 /v1/chat/completions 不得阻塞事件循环 (并发 /health 可即时响应)"""
    import asyncio
    import time as _time

    from httpx import ASGITransport, AsyncClient

    def slow_ask(*args, **kwargs):
        _time.sleep(1.0)
        return {
            "query": "hi",
            "answer": "ok",
            "sources": [],
            "model": "experimental",
            "raw_event": {},
        }

    monkeypatch.setattr("server.PerplexityClient.ask", slow_ask)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        chat_task = asyncio.create_task(
            ac.post(
                "/v1/chat/completions",
                json={
                    "model": "experimental",
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
        )
        await asyncio.sleep(0.2)
        t0 = _time.monotonic()
        r = await ac.get("/health")
        elapsed = _time.monotonic() - t0
        assert r.status_code == 200
        assert elapsed < 0.5, f"/health 被阻塞了 {elapsed:.2f}s"
        resp = await chat_task
        assert resp.status_code == 200
