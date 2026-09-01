from unittest.mock import patch

from fastapi.testclient import TestClient

from server import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Perplexity Search2API"
    assert data["status"] == "running"
    assert "endpoints" in data


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


def test_models_endpoint():
    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert isinstance(data["data"], list)
    model_ids = [m["id"] for m in data["data"]]
    assert "claude-3-7-sonnet" in model_ids
    assert "experimental" in model_ids


def test_api_key_protection(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret_key_123")

    # Request without key -> 401
    resp_unauth = client.get("/v1/models")
    assert resp_unauth.status_code == 401

    # Request with wrong key -> 401
    resp_wrong = client.get("/v1/models", headers={"Authorization": "Bearer wrong_key"})
    assert resp_wrong.status_code == 401

    # Request with correct key -> 200
    resp_auth = client.get("/v1/models", headers={"Authorization": "Bearer secret_key_123"})
    assert resp_auth.status_code == 200


def test_chat_completions_non_stream():
    mock_ask_result = {
        "query": "Hello",
        "answer": "Hello from mock assistant!",
        "sources": [{"name": "Example", "url": "https://example.com"}],
        "model": "claude-3-7-sonnet",
        "raw_event": {},
    }

    with patch("server.PerplexityClient.ask", return_value=mock_ask_result):
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
        assert "Hello from mock assistant!" in data["choices"][0]["message"]["content"]
        assert "### 引用来源：" in data["choices"][0]["message"]["content"]
