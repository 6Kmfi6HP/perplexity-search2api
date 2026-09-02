import subprocess
import sys


def test_cli_help():
    result = subprocess.run(
        [sys.executable, "cli.py", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Perplexity Search2API" in result.stdout
    assert "login" in result.stdout
    assert "refresh" in result.stdout
    assert "ask" in result.stdout
    assert "serve" in result.stdout


def test_cli_subcommand_help():
    for cmd in ["login", "refresh", "info", "ask", "search", "s", "serve"]:
        result = subprocess.run(
            [sys.executable, "cli.py", cmd, "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0


def test_cli_main_dispatch():
    from cli import main

    # 测试未输入任何命令时直接返回并不抛异常
    main([])


# ---------- get_token_ttl_str 回归测试 ----------


def test_get_token_ttl_str_expires_at_future():
    from datetime import datetime, timedelta, timezone

    from cli import get_token_ttl_str

    # refresh 后凭据以 expires_at 键保存，未来时间应显示剩余天数/小时
    creds = {
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=2, hours=3)).isoformat()
    }
    result = get_token_ttl_str(creds)
    assert result != "长期有效 (Persistent)"
    assert "已过期" not in result
    assert "天" in result
    assert "小时" in result

    # 优先级验证: expires_at 与 expires 同时存在时，expires_at 优先
    creds_both = {
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=2, hours=3)).isoformat(),
        "expires": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
    }
    result_both = get_token_ttl_str(creds_both)
    assert "天" in result_both
    assert "已过期" not in result_both


def test_get_token_ttl_str_expires_at_past():
    from datetime import datetime, timedelta, timezone

    from cli import get_token_ttl_str

    # 过期的 expires_at 应显示已过期而非长期有效
    creds = {
        "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    }
    result = get_token_ttl_str(creds)
    assert "已过期" in result


def test_get_token_ttl_str_legacy_expires_key():
    from datetime import datetime, timedelta, timezone

    from cli import get_token_ttl_str

    # 兼容旧版: 仅存在旧键 expires 时同样应正确计算
    creds = {
        "expires": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    }
    result = get_token_ttl_str(creds)
    assert "已过期" in result


def test_serve_rejects_self_remote_config(monkeypatch, tmp_path):
    """pplx serve 检测到 remote_url 指向即将监听的端口时拒绝启动 (防自调用死循环)"""
    import pytest

    from cli import main

    cfg = tmp_path / "cfg.json"
    cfg.write_text('{"remote_url": "http://127.0.0.1:8765"}')
    monkeypatch.setenv("PERPLEXITY_CONFIG_PATH", str(cfg))
    with pytest.raises(SystemExit) as e:
        main(["serve", "--port", "8765"])
    assert e.value.code == 1
