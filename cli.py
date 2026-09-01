"""
Perplexity Search2API 命令行交互工具 (CLI)
- 支持 login (从浏览器 SSO 提取 Token)
- 支持 refresh (仿 oh-my-pi 方式刷新凭证)
- 支持 info (查看当前用户/企业组织信息与凭证 TTL)
- 支持 ask (实时流式搜索与回答演示，支持 --raw 原始数据调试模式)
- 支持 serve (一键启动 OpenAI 兼容接口服务)
"""

import argparse
import json
import sys
import time

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.table import Table

from perplexity_auth import (
    PerplexityAuthManager,
    extract_from_browser,
    get_credentials_path,
    load_credentials,
)
from perplexity_client import PerplexityClient

console = Console()


def cmd_login(args):
    """自动从当前真实浏览器中提取 SSO 会话 Token"""
    console.print("[bold blue]正在连接真实浏览器并提取 Perplexity SSO 凭据...[/bold blue]")
    try:
        creds = extract_from_browser()
        console.print("[bold green]✓ 提取成功并已写入本地凭据库！[/bold green]")
        _display_info(creds)
    except Exception as e:
        console.print(f"[bold red]✗ 提取失败:[/bold red] {e}")
        sys.exit(1)


def cmd_refresh(args):
    """手动执行会话凭证刷新"""
    manager = PerplexityAuthManager()
    console.print("[bold blue]正在调用 NextAuth /api/auth/session 端点刷新凭证...[/bold blue]")
    try:
        manager.refresh()
        console.print("[bold green]✓ 凭证已成功刷新，有效期顺延 30 天！[/bold green]")
        _display_info(manager.credentials)
    except Exception as e:
        console.print(f"[bold red]✗ 刷新失败:[/bold red] {e}")
        sys.exit(1)


def cmd_info(args):
    """展示当前账号与凭据信息"""
    creds = load_credentials()
    if not creds:
        console.print("[bold red]未检测到已保存的凭据，请先执行 `login` 命令！[/bold red]")
        sys.exit(1)
    _display_info(creds)


def _display_info(creds: dict):
    table = Table(title="Perplexity 认证与会话状态", show_header=True, header_style="bold magenta")
    table.add_column("字段", style="cyan")
    table.add_column("值", style="green")

    user = creds.get("user", {})
    table.add_row("凭据存储路径", str(get_credentials_path()))
    table.add_row("用户名", str(user.get("name", "N/A")))
    table.add_row("用户邮箱", str(user.get("email", "N/A")))
    table.add_row("是否已订阅 Pro", "✅ 是" if user.get("is_pro") else "❌ 否")
    table.add_row("过期时间 (Expires)", str(creds.get("expires_at", "N/A")))
    table.add_row("最近刷新时间", str(creds.get("last_refreshed_at", "N/A")))
    table.add_row("Session Token 掩码", creds.get("session_token", "")[:12] + "..." if creds.get("session_token") else "N/A")

    console.print(table)


def cmd_ask(args):
    """终端实时搜索提问交互"""
    client = PerplexityClient()
    query = args.query
    model = args.model
    mode = args.mode

    console.print(f"[bold cyan]🔍 正在向 Perplexity [{model} / {mode}] 发起搜索:[/bold cyan] {query}\n")

    if args.raw:
        # RAW 调试模式：实时输出 SSE 原始 JSON
        console.print("[bold yellow]--- 进入 RAW 调试模式 (原始 SSE 事件流) ---[/bold yellow]")
        for chunk in client.ask_stream(query, model=model, mode=mode):
            raw = chunk.get("raw_event", {})
            if raw:
                syntax = Syntax(json.dumps(raw, ensure_ascii=False, indent=2), "json", theme="monokai")
                console.print(syntax)
                time.sleep(0.05)
        return

    # 正常终端流式渲染
    last_sources = []
    ans = ""
    if sys.stdout.isatty():
        with Live(console=console, refresh_per_second=12) as live:
            for chunk in client.ask_stream(query, model=model, mode=mode):
                ans = chunk["answer"]
                last_sources = chunk.get("sources", [])
                live.update(Markdown(ans))
    else:
        for chunk in client.ask_stream(query, model=model, mode=mode):
            ans = chunk["answer"]
            last_sources = chunk.get("sources", [])
        console.print(Markdown(ans))

    if last_sources:
        console.print("\n[bold magenta]📚 引用来源 (Sources):[/bold magenta]")
        for idx, s in enumerate(last_sources, 1):
            name = s.get("name", "网页来源")
            url = s.get("url", "")
            snippet = s.get("snippet", "")
            console.print(f"  [bold cyan][{idx}][/bold cyan] [underline blue]{name}[/underline blue]: {url}")
            if snippet:
                console.print(f"      [dim]{snippet[:120]}...[/dim]")


def cmd_serve(args):
    """启动 OpenAI 兼容 HTTP 服务端"""
    import uvicorn

    console.print(f"[bold green]🚀 正在启动 Perplexity Search2API 服务 (http://{args.host}:{args.port})...[/bold green]")
    uvicorn.run("server:app", host=args.host, port=args.port, reload=False)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    # 如果直接输入搜索内容而非子命令，自动路由至 ask 搜索
    known_commands = {"login", "refresh", "info", "ask", "search", "s", "serve", "-h", "--help"}
    if argv and argv[0] not in known_commands and not argv[0].startswith("-"):
        argv = ["ask"] + argv

    parser = argparse.ArgumentParser(
        description="Perplexity Search2API 客户端 & CLI 管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # login
    subparsers.add_parser("login", help="通过 agent-browser 自动从当前已登录的浏览器提取 SSO 会话")

    # refresh
    subparsers.add_parser("refresh", help="手动调用 NextAuth 接口刷新当前会话 Token (延长 30 天)")

    # info
    subparsers.add_parser("info", help="查看当前保存的账号、企业组织与凭证信息")

    # ask / search
    ask_p = subparsers.add_parser("ask", aliases=["search", "s"], help="直接在终端发起流式搜索提问 (别名: search, s)")
    ask_p.add_argument("query", type=str, help="搜索或提问内容")
    ask_p.add_argument("--model", type=str, default="experimental", help="模型选择 (如 experimental, claude-3-7-sonnet, grok-4.6)")
    ask_p.add_argument("--mode", type=str, default="copilot", help="搜索模式 (copilot, concise 等)")
    ask_p.add_argument("--raw", action="store_true", help="开启调试模式，直接实时打印 Perplexity 返回的原始 SSE 事件 JSON")

    # serve
    serve_p = subparsers.add_parser("serve", help="启动 OpenAI 兼容接口服务器")
    serve_p.add_argument("--host", type=str, default="0.0.0.0", help="监听地址 (默认 0.0.0.0)")
    serve_p.add_argument("--port", type=int, default=8000, help="监听端口 (默认 8000)")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return

    if args.command == "login":
        cmd_login(args)
    elif args.command == "refresh":
        cmd_refresh(args)
    elif args.command == "info":
        cmd_info(args)
    elif args.command in ("ask", "search", "s"):
        cmd_ask(args)
    elif args.command == "serve":
        cmd_serve(args)


if __name__ == "__main__":
    main()
