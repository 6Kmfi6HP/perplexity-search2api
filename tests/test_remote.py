import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from perplexity_client import PerplexityClient, RemotePerplexityClient
from perplexity_config import (
    get_remote_api_key,
    get_remote_url,
    is_remote_mode,
    load_config,
    parse_toml,
    parse_yaml,
    save_config,
    set_remote_config,
    unset_remote_config,
)


def test_config_crud():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / ".perplexity_config.json"

        # 初始为空
        assert load_config(config_file) == {}

        # 写入配置
        set_remote_config(
            "http://example.com:8000/", api_key="sk-test123", default_model="fast", path=config_file
        )

        loaded = load_config(config_file)
        assert loaded["remote_url"] == "http://example.com:8000"
        assert loaded["api_key"] == "sk-test123"
        assert loaded["default_model"] == "fast"

        # 清除配置
        unset_remote_config(path=config_file)
        loaded_after = load_config(config_file)
        assert "remote_url" not in loaded_after
        assert "api_key" not in loaded_after


def test_dotenv_config_loading(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        with open(env_file, "w", encoding="utf-8") as f:
            f.write("PERPLEXITY_BASE_URL=http://env-file-host:53000/\n")
            f.write("PERPLEXITY_API_KEY=env-secret-key\n")

        monkeypatch.setenv("PERPLEXITY_ENV_PATH", str(env_file))

        # 验证自动从 .env 文件读取到 remote_url 与 api_key
        url = get_remote_url()
        key = get_remote_api_key()
        assert url == "http://env-file-host:53000"
        assert key == "env-secret-key"
        assert is_remote_mode() is True


def test_toml_config_loading(tmp_path):
    toml_file = tmp_path / "pplx.toml"
    with open(toml_file, "w", encoding="utf-8") as f:
        f.write("""[tool.pplx]
remote_url = "http://toml-server:8080"
api_key = "toml-key"
""")
    parsed = parse_toml(toml_file)
    assert parsed["remote_url"] == "http://toml-server:8080"
    assert parsed["api_key"] == "toml-key"


def test_yaml_config_loading(tmp_path):
    yaml_file = tmp_path / ".perplexity.yaml"
    with open(yaml_file, "w", encoding="utf-8") as f:
        f.write("remote_url: http://yaml-server:9090\napi_key: yaml-key\n")
    parsed = parse_yaml(yaml_file)
    assert parsed["remote_url"] == "http://yaml-server:9090"
    assert parsed["api_key"] == "yaml-key"


def test_remote_url_resolution_priority(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / ".perplexity_config.json"
        monkeypatch.setenv("PERPLEXITY_CONFIG_PATH", str(config_file))

        # 1. 配置文件模式
        save_config({"remote_url": "http://config-host:8000"}, config_file)
        assert get_remote_url() == "http://config-host:8000"
        assert is_remote_mode() is True

        # 2. 环境变量覆盖
        monkeypatch.setenv("PERPLEXITY_BASE_URL", "http://env-host:9000/")
        assert get_remote_url() == "http://env-host:9000"

        # 3. 命令行参数最高优先级
        assert get_remote_url("http://cli-host:5000/") == "http://cli-host:5000"


def test_remote_api_key_resolution_priority(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / ".perplexity_config.json"
        monkeypatch.setenv("PERPLEXITY_CONFIG_PATH", str(config_file))

        save_config({"api_key": "config-key-999"}, config_file)
        assert get_remote_api_key() == "config-key-999"

        monkeypatch.setenv("PERPLEXITY_API_KEY", "env-key-888")
        assert get_remote_api_key() == "env-key-888"

        assert get_remote_api_key("cli-key-777") == "cli-key-777"


def test_remote_client_build_headers_and_url():
    client = RemotePerplexityClient("http://remote-server:8000/v1", api_key="test-token")
    headers = client._build_headers()
    assert headers["Authorization"] == "Bearer test-token"
    assert headers["api-key"] == "test-token"

    assert (
        client._get_url("/v1/chat/completions") == "http://remote-server:8000/v1/chat/completions"
    )
    assert client._get_url("/health") == "http://remote-server:8000/v1/health"

    client2 = RemotePerplexityClient("http://remote-server:8000")
    assert (
        client2._get_url("/v1/chat/completions") == "http://remote-server:8000/v1/chat/completions"
    )


def test_remote_client_health_and_models():
    client = RemotePerplexityClient("http://mock-remote:8000")

    mock_health_resp = MagicMock()
    mock_health_resp.status_code = 200
    mock_health_resp.json.return_value = {"status": "ok", "timestamp": 123456}

    mock_models_resp = MagicMock()
    mock_models_resp.status_code = 200
    mock_models_resp.json.return_value = {
        "object": "list",
        "data": [{"id": "experimental"}, {"id": "claude-3-7-sonnet"}],
    }

    with patch("httpx.Client.get") as mock_get:

        def side_effect(url, headers=None):
            if "/health" in url:
                return mock_health_resp
            if "/v1/models" in url:
                return mock_models_resp
            return mock_health_resp

        mock_get.side_effect = side_effect
        health = client.check_health()
        assert health["status"] == "ok"

        models = client.get_models()
        assert "experimental" in models
        assert "claude-3-7-sonnet" in models


def test_remote_client_ask_stream_mock():
    client = RemotePerplexityClient("http://mock-remote:8000")

    sample_lines = [
        'data: {"id":"chatcmpl-1","choices":[{"delta":{"role":"assistant","content":"Hello "},"index":0}]}',
        'data: {"id":"chatcmpl-1","choices":[{"delta":{"content":"world!"},"index":0}], "citations":[{"name":"Wiki","url":"https://wiki.org"}]}',
        "data: [DONE]",
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_lines.return_value = sample_lines

    class StreamContextManager:
        def __enter__(self):
            return mock_resp

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("httpx.Client.stream", return_value=StreamContextManager()):
        chunks = list(client.ask_stream("Hi"))
        assert len(chunks) == 2
        assert chunks[-1]["answer"] == "Hello world!"
        assert len(chunks[-1]["sources"]) == 1
        assert chunks[-1]["sources"][0]["url"] == "https://wiki.org"


@pytest.mark.asyncio
async def test_remote_client_ask_async_mock():
    client = RemotePerplexityClient("http://mock-remote:8000")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Async non-streaming answer"}}],
        "citations": [{"name": "Source 1", "url": "https://example.com"}],
        "model": "experimental",
    }

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        res = await client.ask_async("Test query")
        assert res["answer"] == "Async non-streaming answer"
        assert len(res["sources"]) == 1
        assert res["sources"][0]["name"] == "Source 1"


def test_perplexity_client_remote_delegation():
    client = PerplexityClient(remote_url="http://mock-server:8000")
    assert client.is_remote is True
    assert client.remote_client is not None
    assert client.remote_client.remote_url == "http://mock-server:8000"


def test_cli_remote_commands(monkeypatch):
    from cli import main

    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / ".perplexity_config.json"
        monkeypatch.setenv("PERPLEXITY_CONFIG_PATH", str(config_file))

        # 1. 测试 set (写入配置文件)
        with patch(
            "perplexity_client.RemotePerplexityClient.check_health", return_value={"status": "ok"}
        ):
            with patch(
                "perplexity_client.RemotePerplexityClient.get_models",
                return_value=["auto", "claude-3-7-sonnet"],
            ):
                main(["remote", "set", "http://my-remote-server:8000", "--api-key", "my-key"])

        cfg = load_config(config_file)
        assert cfg["remote_url"] == "http://my-remote-server:8000"
        assert cfg["api_key"] == "my-key"

        # 2. 测试 show
        with patch(
            "perplexity_client.RemotePerplexityClient.check_health", return_value={"status": "ok"}
        ):
            with patch(
                "perplexity_client.RemotePerplexityClient.get_models", return_value=["auto"]
            ):
                main(["remote", "show"])

        # 3. 测试自动从配置文件中读取 remote_url 进行 ask
        with patch(
            "perplexity_client.RemotePerplexityClient.ask_stream",
            return_value=[{"answer": "Answer from config endpoint", "sources": []}],
        ):
            main(["ask", "Test query via saved remote config"])

        # 4. 测试 unset
        main(["remote", "unset"])
        cfg_after = load_config(config_file)
        assert "remote_url" not in cfg_after
