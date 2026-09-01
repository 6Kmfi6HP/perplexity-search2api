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
