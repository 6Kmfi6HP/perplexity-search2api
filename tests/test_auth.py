import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from perplexity_auth import (
    PerplexityAuthManager,
    get_credentials_path,
    load_credentials,
    save_credentials,
)


def test_get_credentials_path_env(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
        monkeypatch.setenv("PERPLEXITY_SESSION_PATH", tmp.name)
        p = get_credentials_path()
        assert p == Path(tmp.name).resolve()


def test_save_and_load_credentials():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_file = Path(tmpdir) / "test_session.json"
        data = {
            "session_token": "test_token_12345",
            "org_token": "org_abc",
            "user": {"name": "Tester", "email": "tester@example.com"},
        }
        save_credentials(data, path=tmp_file)
        loaded = load_credentials(path=tmp_file)
        assert loaded["session_token"] == "test_token_12345"
        assert loaded["org_token"] == "org_abc"
        assert loaded["user"]["email"] == "tester@example.com"


def test_load_credentials_env_fallback(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        non_existent = Path(tmpdir) / "non_existent.json"
        monkeypatch.setenv("PERPLEXITY_SESSION_TOKEN", "env_token_999")
        monkeypatch.setenv("PERPLEXITY_USER_NAME", "Env Tester")
        monkeypatch.setenv("PERPLEXITY_USER_EMAIL", "env@test.com")

        loaded = load_credentials(path=non_existent)
        assert loaded["session_token"] == "env_token_999"
        assert loaded["user"]["name"] == "Env Tester"
        assert loaded["source"] == "environment"


def test_auth_manager_is_expired():
    # Future date (> 12 hours) -> not expired
    future_date = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    manager = PerplexityAuthManager({"session_token": "tok", "expires_at": future_date})
    assert not manager.is_expired()

    # Past date -> expired
    past_date = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    manager_past = PerplexityAuthManager({"session_token": "tok", "expires_at": past_date})
    assert manager_past.is_expired()

    # Soon expiring (< 12 hours) -> considered expired / needs refresh
    soon_date = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    manager_soon = PerplexityAuthManager({"session_token": "tok", "expires_at": soon_date})
    assert manager_soon.is_expired()


def test_auth_manager_refresh_mock():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers.get_list.return_value = [
        "__Secure-next-auth.session-token=new_token_777; Path=/; HttpOnly; Secure",
        "__Secure-pplx.session.org=new_org_888; Path=/",
    ]
    mock_resp.json.return_value = {
        "user": {"name": "Refreshed User", "email": "refreshed@example.com"},
        "expires": "2026-09-30T00:00:00.000Z",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_file = Path(tmpdir) / "test_refresh.json"
        with patch("httpx.Client.get", return_value=mock_resp):
            manager = PerplexityAuthManager({"session_token": "old_token"})
            with patch("perplexity_auth.get_credentials_path", return_value=tmp_file):
                res = manager.refresh()
                assert res["session_token"] == "new_token_777"
                assert res["user"]["name"] == "Refreshed User"


def test_auth_manager_get_valid_token_extract():
    manager = PerplexityAuthManager({"session_token": ""})
    with patch(
        "perplexity_auth.extract_from_browser",
        return_value={"session_token": "browser_extracted_token"},
    ):
        token = manager.get_valid_token()
        assert token == "browser_extracted_token"
        assert manager.session_token == "browser_extracted_token"


def test_auth_manager_get_valid_token_existing():
    manager = PerplexityAuthManager({"session_token": "existing_valid_token"})
    assert manager.get_valid_token() == "existing_valid_token"


def test_save_credentials_permissions():
    """回归: 凭据文件必须以 0600 权限写入"""
    import stat

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_file = Path(tmpdir) / "perm_session.json"
        save_credentials({"session_token": "tok"}, path=tmp_file)
        mode = stat.S_IMODE(tmp_file.stat().st_mode)
        assert mode == 0o600
