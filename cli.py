"""
Perplexity Search2API 命令行交互工具 (CLI)
- 支持 remote (设置、查看、测试远端 API 端点，避免在本地存储凭证)
- 支持 login (从浏览器 SSO 提取 Token)
- 支持 refresh (刷新凭据，支持本地与远端两种模式)
- 支持 info (查看当前账号/企业组织信息与凭据 TTL，支持本地与远端模式)
- 支持 ask (实时流式搜索与回答演示，支持 --raw 原始数据调试模式，支持直连远端 API)
- 支持 models (查看本地或远端可用模型列表)
- 支持 serve (一键启动 OpenAI 兼容接口服务)
"""

import argparse
import json
import sys
import time

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.markup import escape
from rich.syntax import Syntax
from rich.table import Table

from perplexity_auth import (
    PerplexityAuthManager,
    extract_from_browser,
    get_credentials_path,
    load_credentials,
)
from perplexity_client import (
    MODEL_ALIASES,
    PerplexityClient,
    RemotePerplexityClient,
)
from perplexity_config import (
    get_config_path,
    get_remote_api_key,
    get_remote_url,
    set_remote_config,
    unset_remote_config,
)

console = Console()


def cmd_remote(args):
    """管理与配置远端 API 服务端点"""
    subaction = getattr(args, "remote_action", None)

    if subaction == "set":
        url = args.url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            console.print(
                f"[bold red]✗ 错误: 远端 URL 必须以 http:// 或 https:// 开头: {url}[/bold red]"
            )
            sys.exit(1)

        api_key = getattr(args, "api_key", None)
        default_model = getattr(args, "default_model", None)

        console.print(f"[bold blue]正在测试与远端端点的连通性: {url}...[/bold blue]")
        client = RemotePerplexityClient(url, api_key=api_key)
        start_t = time.perf_counter()
        try:
            health = client.check_health(timeout=6.0)
            latency_ms = (time.perf_counter() - start_t) * 1000
            models = client.get_models(timeout=6.0)

            # 保存配置到文件
            set_remote_config(url, api_key=api_key, default_model=default_model)

            console.print(
                f"[bold green]✓ 远端端点连通成功 ({latency_ms:.1f}ms) 并已保存为默认配置！[/bold green]"
            )
            table = Table(title="远端 API 配置摘要", show_header=True, header_style="bold magenta")
            table.add_column("配置项", style="cyan")
            table.add_column("值", style="green")
            table.add_row("远端 URL", url)
            table.add_row("配置文件路径", str(get_config_path()))
            table.add_row(
                "API Key", (api_key[:6] + "..." + api_key[-4:]) if api_key else "未设置 (无鉴权)"
            )
            table.add_row(
                "服务状态",
                f"✅ 正常 (code: {health.get('code', 200) if isinstance(health, dict) else 200})",
            )
            table.add_row("可用模型数", f"{len(models)} 个模型" if models else "默认模型")
            if default_model:
                table.add_row("默认模型", default_model)
            console.print(table)
            console.print(
                "[dim]ℹ 后续所有 pplx 命令将直接请求此远端端点，本地无需存储任何 Perplexity 凭据。[/dim]\n"
            )
        except Exception as e:
            console.print(f"[bold red]✗ 无法连接到远端端点:[/bold red] {e}")
            console.print("[yellow]提示: 请确认远端 serve 服务已启动且端口已正确映射。[/yellow]")
            sys.exit(1)

    elif subaction in ("unset", "clear", "remove"):
        unset_remote_config()
        console.print("[bold green]✓ 已成功清除远端配置，恢复为本地直接请求模式。[/bold green]")

    elif subaction in ("test", "ping", "check"):
        target_url = getattr(args, "url", None) or get_remote_url(getattr(args, "remote", None))
        if not target_url:
            console.print(
                "[bold red]✗ 未配置远端端点。请指定 URL 或先运行 `pplx remote set <URL>`。[/bold red]"
            )
            sys.exit(1)

        api_key = getattr(args, "api_key", None) or get_remote_api_key()
        console.print(f"[bold blue]正在探测远端端点: {target_url}...[/bold blue]")
        client = RemotePerplexityClient(target_url, api_key=api_key)
        start_t = time.perf_counter()
        try:
            health = client.check_health(timeout=8.0)
            latency_ms = (time.perf_counter() - start_t) * 1000
            models = client.get_models(timeout=8.0)
            console.print(f"[bold green]✓ 远端服务响应正常！耗时: {latency_ms:.1f}ms[/bold green]")
            if models:
                console.print(
                    f"[bold cyan]可用模型 ({len(models)} 个):[/bold cyan] {', '.join(models[:8])}{'...' if len(models) > 8 else ''}"
                )
        except Exception as e:
            console.print(f"[bold red]✗ 连通性测试失败:[/bold red] {e}")
            sys.exit(1)

    else:
        # 默认展示当前配置状态 (show / get / status)
        cli_remote = getattr(args, "remote", None)
        remote_url = get_remote_url(cli_remote)
        api_key = get_remote_api_key(getattr(args, "api_key", None))

        if remote_url:
            client = RemotePerplexityClient(remote_url, api_key=api_key)
            status_str = "检测中..."
            model_count = "N/A"
            try:
                client.check_health(timeout=4.0)
                status_str = "✅ 在线 (Online)"
                models = client.get_models(timeout=4.0)
                if models:
                    model_count = f"{len(models)} 个"
            except Exception:
                status_str = "❌ 离线 / 连接超时"

            table = Table(
                title="Perplexity 远端配置状态", show_header=True, header_style="bold magenta"
            )
            table.add_column("字段", style="cyan")
            table.add_column("当前值", style="green")
            table.add_row("当前模式", "🌐 远端 API 模式 (Remote API Mode)")
            table.add_row("远端服务 URL", remote_url)
            table.add_row("服务健康状态", status_str)
            table.add_row(
                "API Key 状态",
                (api_key[:6] + "..." + api_key[-4:]) if api_key else "未设置 (无鉴权)",
            )
            table.add_row("可用模型数", model_count)
            table.add_row("本地配置文件", str(get_config_path()))
            table.add_row("本地凭据需求", "无需本地凭证 (No local credentials needed)")
            console.print(table)
        else:
            table = Table(
                title="Perplexity 运行模式状态", show_header=True, header_style="bold magenta"
            )
            table.add_column("字段", style="cyan")
            table.add_column("当前值", style="yellow")
            table.add_row("当前模式", "💻 本地直接请求模式 (Local Direct Mode)")
            table.add_row("远端配置", "未配置")
            table.add_row("提示", "可通过 `pplx remote set <URL>` 绑定远端端点，免本地凭据存储")
            console.print(table)


def cmd_models(args):
    """列出可用模型"""
    remote_url = get_remote_url(getattr(args, "remote", None))
    api_key = get_remote_api_key(getattr(args, "api_key", None))

    if remote_url:
        console.print(f"[bold blue]正在从远端端点 ({remote_url}) 获取模型列表...[/bold blue]")
        client = RemotePerplexityClient(remote_url, api_key=api_key)
        try:
            models = client.get_models()
            table = Table(
                title=f"远端模型列表 ({remote_url})", show_header=True, header_style="bold magenta"
            )
            table.add_column("序号", style="dim", width=6)
            table.add_column("模型 ID", style="cyan")
            for idx, m in enumerate(models, 1):
                table.add_row(str(idx), m)
            console.print(table)
        except Exception as e:
            console.print(f"[bold red]✗ 获取远端模型列表失败:[/bold red] {e}")
            sys.exit(1)
    else:
        table = Table(title="内置支持的模型与别名", show_header=True, header_style="bold magenta")
        table.add_column("友好别名", style="cyan")
        table.add_column("后端标识 (Internal Key)", style="green")
        for alias, internal in MODEL_ALIASES.items():
            table.add_row(alias, internal)
        console.print(table)


def cmd_login(args):
    """自动从当前真实浏览器中提取 SSO 会话 Token"""
    force_local = getattr(args, "local", False)
    remote_url = get_remote_url(getattr(args, "remote", None))

    if remote_url and not force_local:
        console.print(f"[bold yellow]ℹ 当前已配置远端 API 模式: {remote_url}[/bold yellow]")
        console.print(
            "在远端模式下，所有请求直接由远端服务代理，[bold green]无需在当前电脑提取或存储任何登录凭据[/bold green]。"
        )
        console.print('你可以直接运行 [bold cyan]`pplx ask "<问题>"`[/bold cyan] 发起搜索。')
        console.print(
            "[dim]若确实需要提取当前电脑的浏览器凭据，请添加 `--local` 参数，或使用 `pplx remote unset` 清除远端配置。[/dim]"
        )
        return

    console.print("[bold blue]正在连接真实浏览器并提取 Perplexity SSO 凭据...[/bold blue]")
    try:
        creds = extract_from_browser()
        console.print("[bold green]✓ 提取成功并已写入本地凭据库！[/bold green]")
        _display_info(creds)
    except Exception as e:
        console.print(f"[bold red]✗ 提取失败:[/bold red] {e}")
        sys.exit(1)


def cmd_refresh(args):
    """手动执行会话凭证刷新 (支持本地与远端两种模式)"""
    force_local = getattr(args, "local", False)
    remote_url = get_remote_url(getattr(args, "remote", None))
    api_key = get_remote_api_key(getattr(args, "api_key", None))

    if remote_url and not force_local:
        console.print(
            f"[bold blue]正在请求远端服务 ({remote_url}) 刷新 NextAuth 凭据...[/bold blue]"
        )
        client = RemotePerplexityClient(remote_url, api_key=api_key)
        try:
            res = client.refresh_session()
            console.print("[bold green]✓ 远端服务凭据已成功刷新！[/bold green]")
            if isinstance(res, dict) and "data" in res:
                data = res["data"]
                user = data.get("user", {})
                table = Table(
                    title="远端服务凭证最新状态", show_header=True, header_style="bold magenta"
                )
                table.add_column("字段", style="cyan")
                table.add_column("值", style="green")
                table.add_row("远端服务", remote_url)
                table.add_row("用户名", str(user.get("name", "N/A")))
                table.add_row("用户邮箱", str(user.get("email", "N/A")))
                table.add_row("过期时间 (Expires)", str(data.get("expires_at", "N/A")))
                console.print(table)
            return
        except Exception as e:
            console.print(f"[bold red]✗ 远端刷新失败:[/bold red] {e}")
            sys.exit(1)

    manager = PerplexityAuthManager()
    console.print("[bold blue]正在调用 NextAuth /api/auth/session 端点刷新本地凭据...[/bold blue]")
    try:
        manager.refresh()
        console.print("[bold green]✓ 本地凭证已成功刷新，有效期顺延 30 天！[/bold green]")
        _display_info(manager.credentials)
    except Exception as e:
        console.print(f"[bold red]✗ 刷新失败:[/bold red] {e}")
        sys.exit(1)


def cmd_info(args):
    """展示当前账号、运行模式与凭据信息"""
    force_local = getattr(args, "local", False)
    remote_url = get_remote_url(getattr(args, "remote", None))
    api_key = get_remote_api_key(getattr(args, "api_key", None))

    if remote_url and not force_local:
        client = RemotePerplexityClient(remote_url, api_key=api_key)
        table = Table(
            title="Perplexity 运行模式与服务状态", show_header=True, header_style="bold magenta"
        )
        table.add_column("字段", style="cyan")
        table.add_column("值", style="green")

        table.add_row("运行模式", "🌐 远端 API 模式 (Remote API Mode)")
        table.add_row("远端服务端点", remote_url)
        table.add_row("本地凭据需求", "无需本地凭据 (No local credentials needed)")

        try:
            client.check_health(timeout=5.0)
            table.add_row("远端连接状态", "✅ 正常在线 (HTTP 200)")
            models = client.get_models(timeout=5.0)
            if models:
                table.add_row("远端可用模型数", f"{len(models)} 个可用模型")

            auth_info = client.get_auth_info(timeout=5.0)
            if auth_info and isinstance(auth_info, dict) and "user" in auth_info:
                user = auth_info["user"]
                table.add_row("远端用户名", str(user.get("name", "N/A")))
                table.add_row("远端用户邮箱", str(user.get("email", "N/A")))
                table.add_row(
                    "远端是否 Pro",
                    "✅ 是"
                    if user.get("is_pro") or user.get("subscription_status") == "active"
                    else "❌ 否",
                )
                table.add_row("远端凭证过期时间", str(auth_info.get("expires_at", "N/A")))
        except Exception as e:
            table.add_row("远端连接状态", f"❌ 连接失败: {e}")

        console.print(table)
        return

    creds = load_credentials()
    if not creds:
        console.print("[bold red]未检测到已保存的本地凭据。[/bold red]")
        console.print(
            "提示: 可执行 `pplx login` 提取本地凭据，或通过 `pplx remote set <URL>` 使用远端服务。"
        )
        sys.exit(1)
    _display_info(creds)


def _display_info(creds: dict):
    table = Table(
        title="Perplexity 本地认证与会话状态", show_header=True, header_style="bold magenta"
    )
    table.add_column("字段", style="cyan")
    table.add_column("值", style="green")

    user = creds.get("user", {})
    table.add_row("凭据存储路径", str(get_credentials_path()))
    table.add_row("用户名", str(user.get("name", "N/A")))
    table.add_row("用户邮箱", str(user.get("email", "N/A")))
    table.add_row("是否已订阅 Pro", "✅ 是" if user.get("is_pro") else "❌ 否")
    table.add_row("过期时间 (Expires)", str(creds.get("expires_at", "N/A")))
    table.add_row("最近刷新时间", str(creds.get("last_refreshed_at", "N/A")))
    table.add_row(
        "Session Token 掩码",
        creds.get("session_token", "")[:12] + "..." if creds.get("session_token") else "N/A",
    )

    console.print(table)


def cmd_ask(args):
    """终端实时搜索提问交互 (支持本地直连与远端 API 两种模式)"""
    remote_url = get_remote_url(getattr(args, "remote", None))
    api_key = get_remote_api_key(getattr(args, "api_key", None))

    query = args.query
    model = args.model
    mode = args.mode

    if remote_url:
        console.print(
            f"[bold cyan]🔍 正在向远端 API 发起搜索 ({escape(model)}):[/bold cyan] {escape(query)} [dim]({remote_url})[/dim]\n"
        )
        client = RemotePerplexityClient(remote_url, api_key=api_key)
    else:
        console.print(
            f"[bold cyan]🔍 正在向 Perplexity ({escape(model)} / {escape(mode)}):[/bold cyan] {escape(query)}\n"
        )
        client = PerplexityClient()

    if args.raw:
        console.print("[bold yellow]--- 进入 RAW 调试模式 (原始 SSE 事件流) ---[/bold yellow]")
        for chunk in client.ask_stream(query, model=model, mode=mode):
            raw = chunk.get("raw_event", {})
            if raw:
                syntax = Syntax(
                    json.dumps(raw, ensure_ascii=False, indent=2), "json", theme="monokai"
                )
                console.print(syntax)
                time.sleep(0.05)
        return

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

    if last_sources and "### 📚 参考来源与链接" not in ans:
        console.print("\n[bold magenta]📚 引用来源 (Sources):[/bold magenta]")
        for idx, s in enumerate(last_sources, 1):
            name = s.get("name", "网页来源")
            url = s.get("url", "")
            snippet = s.get("snippet", "")
            console.print(
                f"  [bold cyan][{idx}][/bold cyan] [underline blue]{name}[/underline blue]: {url}"
            )
            if snippet:
                console.print(f"      [dim]{snippet}[/dim]")


def cmd_serve(args):
    """启动本地 OpenAI 兼容接口服务器"""
    import uvicorn

    from server import app

    console.print(
        f"[bold green]🚀 正在启动 Perplexity Search2API 网关服务: http://{args.host}:{args.port}[/bold green]"
    )
    console.print(
        "[dim]提示: 可通过 `pplx remote set http://<host>:<port>` 让其他机器连接此服务。[/dim]"
    )
    uvicorn.run(app, host=args.host, port=args.port)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="pplx",
        description="Perplexity Search2API 客户端 & CLI 管理工具 (支持本地直连与远端 API 两种模式)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--remote",
        "--base-url",
        dest="remote",
        type=str,
        default=None,
        help="临时指定远端 API 服务端点 (如 http://host:port/)",
    )
    parser.add_argument(
        "--api-key", dest="api_key", type=str, default=None, help="临时指定远端服务 API 密钥"
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # remote
    remote_p = subparsers.add_parser("remote", help="管理与设置远端 API 端点 (免本地凭据存储)")
    remote_sub = remote_p.add_subparsers(dest="remote_action", help="远端操作命令")

    # remote set <url>
    remote_set_p = remote_sub.add_parser("set", help="设置并绑定远端 API 端点")
    remote_set_p.add_argument("url", type=str, help="远端服务 URL (如 http://orangepi:53024/)")
    remote_set_p.add_argument("--api-key", type=str, default=None, help="可选 API Key")
    remote_set_p.add_argument("--default-model", type=str, default=None, help="可选默认模型")

    # remote show / get / status
    remote_sub.add_parser("show", aliases=["get", "status"], help="查看当前远端配置状态与连通性")

    # remote unset / clear / remove
    remote_sub.add_parser(
        "unset", aliases=["clear", "remove"], help="清除远端配置，恢复本地直连模式"
    )

    # remote test / ping / check [url]
    remote_test_p = remote_sub.add_parser(
        "test", aliases=["ping", "check"], help="测试远端端点连通性"
    )
    remote_test_p.add_argument(
        "url", nargs="?", type=str, default=None, help="待测试的目标 URL (若留空则使用当前配置)"
    )
    remote_test_p.add_argument("--api-key", type=str, default=None, help="可选 API Key")

    # login
    login_p = subparsers.add_parser(
        "login", help="通过 agent-browser 自动从当前已登录的浏览器提取 SSO 会话"
    )
    login_p.add_argument(
        "--local", action="store_true", help="强制提取本地浏览器凭证 (即使已配置远端模式)"
    )

    # refresh
    refresh_p = subparsers.add_parser(
        "refresh", help="手动调用 NextAuth 接口刷新会话 Token (延长 30 天)"
    )
    refresh_p.add_argument("--local", action="store_true", help="强制刷新本地凭证")
    refresh_p.add_argument(
        "--remote", "--base-url", dest="remote", type=str, default=None, help="指定远端 API URL"
    )
    refresh_p.add_argument(
        "--api-key", dest="api_key", type=str, default=None, help="指定远端 API Key"
    )

    # info
    info_p = subparsers.add_parser("info", help="查看当前保存的账号、企业组织、远端端点与凭证信息")
    info_p.add_argument("--local", action="store_true", help="强制查看本地凭证信息")
    info_p.add_argument(
        "--remote", "--base-url", dest="remote", type=str, default=None, help="指定远端 API URL"
    )
    info_p.add_argument(
        "--api-key", dest="api_key", type=str, default=None, help="指定远端 API Key"
    )

    # models
    models_p = subparsers.add_parser("models", help="查看可用大模型列表 (支持远端与本地查询)")
    models_p.add_argument(
        "--remote", "--base-url", dest="remote", type=str, default=None, help="指定远端 API URL"
    )
    models_p.add_argument(
        "--api-key", dest="api_key", type=str, default=None, help="指定远端 API Key"
    )

    # ask / search / s
    ask_p = subparsers.add_parser(
        "ask", aliases=["search", "s"], help="直接在终端发起流式搜索提问 (别名: search, s)"
    )
    ask_p.add_argument("query", type=str, help="搜索或提问内容")
    ask_p.add_argument(
        "--model",
        type=str,
        default="experimental",
        help="模型选择 (如 experimental, claude-3-7-sonnet, grok-4.6)",
    )
    ask_p.add_argument("--mode", type=str, default="copilot", help="搜索模式 (copilot, concise 等)")
    ask_p.add_argument(
        "--raw", action="store_true", help="开启调试模式，直接实时打印原始 SSE 事件 JSON"
    )
    ask_p.add_argument(
        "--remote", "--base-url", dest="remote", type=str, default=None, help="指定远端 API URL"
    )
    ask_p.add_argument("--api-key", dest="api_key", type=str, default=None, help="指定远端 API Key")

    # serve
    serve_p = subparsers.add_parser("serve", help="启动 OpenAI 兼容接口服务器")
    serve_p.add_argument("--host", type=str, default="0.0.0.0", help="监听地址 (默认 0.0.0.0)")
    serve_p.add_argument("--port", type=int, default=8000, help="监听端口 (默认 8000)")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return

    if args.command == "remote":
        cmd_remote(args)
    elif args.command == "models":
        cmd_models(args)
    elif args.command == "login":
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
