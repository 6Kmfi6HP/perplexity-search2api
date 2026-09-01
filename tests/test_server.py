from unittest.mock import patch

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

    with patch("server.PerplexityClient.ask", return_value=mock_res):
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
