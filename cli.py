"""
Perplexity Search2API 命令行交互工具 (CLI)
- 支持 remote (设置、查看、测试远端 API 端点，避免在本地存储凭证)
- 支持 login (从浏览器 SSO 提取 Token)
- 支持 refresh (刷新凭据，支持本地与远端两种模式)
- 支持 info (查看当前账号/企业组织信息与凭据 TTL，支持本地与远端模式)
- 支持 ask / search (实时流式搜索与回答演示，支持 --vertical / --patents / --academic / --finance 等垂直搜索模型)
- 支持 models (查看本地或远端可用大模型列表与搜索垂直模型)
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
    SEARCH_VERTICALS,
    PerplexityClient,
    RemotePerplexityClient,
    parse_model_and_vertical,
)
from perplexity_config import (
    get_config_path,
    get_remote_api_key,
    get_remote_url,
    load_config,
    set_remote_config,
    unset_remote_config,
)

console = Console()


def get_token_ttl_str(creds: dict | None) -> str:
    """计算会话凭证剩余有效期字符串"""
    if not creds:
        return "未知"
    # refresh 后保存的键为 expires_at，兼容旧版 expires
    expires = creds.get("expires_at") or creds.get("expires")
    if not expires:
        return "长期有效 (Persistent)"
    try:
        from datetime import datetime, timezone
        exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = exp_dt - now
        if diff.total_seconds() <= 0:
            return "[red]已过期[/red]"
        days = diff.days
        hours = int(diff.seconds / 3600)
        return f"{days} 天 {hours} 小时"
    except Exception:
        return "有效"


def cmd_remote(args):
    """管理远端网关端点配置"""
    action = args.remote_action

    if not action or action in ("show", "get", "status"):
        cfg = load_config()
        current_url = get_remote_url(getattr(args, "remote", None))
        current_key = get_remote_api_key(getattr(args, "api_key", None))

        table = Table(
            title="Perplexity Search2API 远端端点配置",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("配置项", style="cyan")
        table.add_column("当前值", style="green")
        table.add_column("说明", style="dim")

        table.add_row(
            "Remote URL",
            current_url or "[yellow]未配置 (本地模式)[/yellow]",
            "远端 Search2API 接口地址",
        )
        table.add_row(
            "API Key",
            "******" if current_key else "[dim]未设置[/dim]",
            "访问远端服务所需的鉴权密钥",
        )
        table.add_row(
            "Default Model",
            cfg.get("default_model", "[dim]未指定 (默认 experimental)[/dim]"),
            "默认优先使用的模型",
        )
        table.add_row("Config File", str(get_config_path()), "主配置文件存储路径")
        console.print(table)

        if current_url:
            console.print("\n[bold blue]正在测试远端服务健康状态...[/bold blue]")
            client = RemotePerplexityClient(current_url, api_key=current_key)
            status_res = client.check_health()
            if status_res.get("status") in ("ok", "online"):
                console.print(
                    f"[bold green]✓ 远端服务连接成功 ({current_url})[/bold green]"
                )
                try:
                    auth_info = client.get_auth_info()
                    if auth_info:
                        console.print(
                            f"  [dim]远端登录用户: {auth_info.get('user', {}).get('email', '未知')}[/dim]"
                        )
                except Exception:
                    pass
            else:
                console.print(
                    f"[bold red]✗ 远端服务无法连接或返回异常:[/bold red] {status_res}"
                )

    elif action == "set":
        url = args.url.strip()
        api_key = getattr(args, "api_key", None)
        default_model = getattr(args, "default_model", None)

        set_remote_config(url, api_key=api_key, default_model=default_model)
        console.print(f"[bold green]✓ 已成功设置远端端点:[/bold green] {url}")
        if api_key:
            console.print("  [dim]已保存远端 API Key[/dim]")
        if default_model:
            console.print(f"  [dim]已设置默认模型: {default_model}[/dim]")

        console.print("\n[bold blue]正在测试连通性...[/bold blue]")
        client = RemotePerplexityClient(url, api_key=api_key)
        res = client.check_health()
        if res.get("status") in ("ok", "online"):
            console.print(f"[bold green]✓ 远端服务健康正常 ({url})[/bold green]")
        else:
            console.print(
                "[bold yellow]⚠ 注意: 远端服务目前不可达或返回异常，请确认服务端已启动。[/bold yellow]"
            )

    elif action == "unset":
        unset_remote_config()
        console.print(
            "[bold green]✓ 已清除远端端点配置，恢复本地直连模式。[/bold green]"
        )

    elif action == "test":
        url = get_remote_url(getattr(args, "remote", None))
        key = get_remote_api_key(getattr(args, "api_key", None))
        if not url:
            console.print(
                "[bold red]✗ 未配置远端端点。请先运行 `pplx remote set <URL>`。[/bold red]"
            )
            sys.exit(1)

        console.print(f"[bold blue]正在测试远端端点: {url} ...[/bold blue]")
        client = RemotePerplexityClient(url, api_key=key)
        res = client.check_health()
        if res.get("status") in ("ok", "online"):
            console.print("[bold green]✓ 连通性测试通过！[/bold green]")
            try:
                models = client.get_models()
                console.print(
                    f"  [dim]可用模型数: {len(models)} 个 (如 {', '.join(models[:4])}...)[/dim]"
                )
            except Exception:
                pass
        else:
            console.print(
                f"[bold red]✗ 连通性测试失败:[/bold red] 状态: {res.get('status')}"
            )
            sys.exit(1)


def cmd_models(args):
    """列出可用模型与专业垂直搜索领域"""
    remote_url = get_remote_url(getattr(args, "remote", None))
    api_key = get_remote_api_key(getattr(args, "api_key", None))

    if remote_url:
        console.print(
            f"[bold blue]正在从远端端点 ({remote_url}) 获取模型列表...[/bold blue]"
        )
        client = RemotePerplexityClient(remote_url, api_key=api_key)
        try:
            models = client.get_models()
            table = Table(
                title=f"远端模型列表 ({remote_url})",
                show_header=True,
                header_style="bold magenta",
            )
            table.add_column("序号", style="dim", width=6)
            table.add_column("模型 ID / 复合模型", style="cyan")
            for idx, m in enumerate(models, 1):
                table.add_row(str(idx), m)
            console.print(table)
        except Exception as e:
            console.print(f"[bold red]✗ 获取远端模型列表失败:[/bold red] {e}")
            sys.exit(1)
    else:
        # 1. 大模型表格
        table = Table(
            title="🧠 内置支持的 AI 基础模型与别名",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("友好别名 (CLI / API)", style="cyan")
        table.add_column("Perplexity 内部后端映射", style="dim")
        table.add_column("模型说明", style="green")

        descriptions = {
            "experimental": "Perplexity 智能优选模型 (默认推荐)",
            "sonar-pro": "Perplexity 深度思考与长文本研究模型",
            "turbo": "轻量超快速搜索模型",
            "claude-3-7-sonnet": "Anthropic Claude 3.7 Sonnet (支持思考链)",
            "claude-3-opus": "Anthropic Claude 3 Opus 顶级长推理模型",
            "gpt-5.6": "OpenAI 旗舰推理大模型 (GPT-5.6 Terra)",
            "gpt-5.6-sol": "OpenAI 快速响应大模型 (GPT-5.6 Sol)",
            "grok-4.6": "xAI Grok 4.6 深度推理大模型",
            "gemini-3.7-flash": "Google Gemini 3.7 Flash 超低延迟模型",
            "gemini-3.1-pro": "Google Gemini 3.1 Pro 高性能通用模型",
            "glm-5.3": "智谱 GLM 5.3 深度思考大模型",
            "kimi-k3": "月之暗面 Kimi K3 超长文本与推理模型",
            "nemotron-3": "NVIDIA Nemotron 3 Ultra 专有模型",
        }

        for alias, internal in sorted(MODEL_ALIASES.items()):
            desc = descriptions.get(alias, "")
            table.add_row(alias, internal, desc)
        console.print(table)

    # 2. 专业搜索领域与垂直模型表格 (Verticals)
    v_table = Table(
        title="\n🌐 专业搜索垂直领域 / 搜索模型 (Search Verticals & Focus Domains)",
        show_header=True,
        header_style="bold cyan",
    )
    v_table.add_column("垂直领域 ID", style="bold green", width=12)
    v_table.add_column("名称与网页入口", style="cyan", width=30)
    v_table.add_column("搜索范围与特色", style="white")
    v_table.add_column("快速调用指令示例", style="yellow")

    sample_cmds = {
        "web": 'pplx ask "最新量子计算突破"',
        "patents": 'pplx ask --patents "CRISPR-Cas9 基因编辑专利"',
        "academic": 'pplx ask --academic "Mamba State Space Models arXiv"',
        "finance": 'pplx ask --finance "NVDA 最新财报毛利率与分析师目标价"',
        "social": 'pplx ask --social "Rust vs Go Web框架真实评价"',
        "health": 'pplx ask -V health "GLP-1 受体激动剂临床指南"',
        "writing": 'pplx ask -V writing "编写一个 FastAPI 模板"',
        "wolfram": 'pplx ask -V wolfram "integrate x^2 * sin(x)"',
        "youtube": 'pplx ask -V youtube "FastAPI 进阶教程 2026"',
        "reddit": 'pplx ask -V reddit " mechanical keyboard switches"',
    }

    for vid, vdata in SEARCH_VERTICALS.items():
        v_name = f"{vdata['name']}\n[dim]{vdata['url']}[/dim]"
        v_table.add_row(
            vid,
            v_name,
            vdata["description"],
            sample_cmds.get(vid, f'pplx ask -V {vid} "<query>"'),
        )

    console.print(v_table)
    console.print(
        "\n[dim]提示: OpenAI 兼容 API 支持复合模型语法，例如 `patents:claude-3-7-sonnet` 或 `academic:sonar`！[/dim]"
    )


def cmd_login(args):
    """自动从当前真实浏览器中提取 SSO 会话 Token"""
    force_local = getattr(args, "local", False)
    remote_url = get_remote_url(getattr(args, "remote", None))

    if remote_url and not force_local:
        console.print(
            f"[bold yellow]ℹ 当前已配置远端 API 模式: {remote_url}[/bold yellow]"
        )
        console.print(
            "在远端模式下，所有请求直接由远端服务代理，[bold green]无需在当前电脑提取或存储任何登录凭据[/bold green]。"
        )
        console.print(
            '你可以直接运行 [bold cyan]`pplx ask "<问题>"`[/bold cyan] 发起搜索。'
        )
        console.print(
            "[dim]若确实需要提取当前电脑的浏览器凭据，请添加 `--local` 参数，或使用 `pplx remote unset` 清除远端配置。[/dim]"
        )
        return

    console.print(
        "[bold blue]正在连接真实浏览器并提取 Perplexity SSO 凭据...[/bold blue]"
    )
    try:
        creds = extract_from_browser()
        console.print("[bold green]✓ 凭据提取成功并已保存！[/bold green]")
        ttl = get_token_ttl_str(creds)
        console.print(f"  [dim]凭据剩余有效期 (TTL): {ttl}[/dim]")
    except Exception as e:
        console.print(f"[bold red]✗ 提取失败:[/bold red] {e}")
        sys.exit(1)


def cmd_refresh(args):
    """手动刷新 NextAuth 会话"""
    remote_url = get_remote_url(getattr(args, "remote", None))
    api_key = get_remote_api_key(getattr(args, "api_key", None))
    force_local = getattr(args, "local", False)

    if remote_url and not force_local:
        console.print(
            f"[bold blue]正在请求远端服务 ({remote_url}) 刷新其 Perplexity 登录凭据...[/bold blue]"
        )
        client = RemotePerplexityClient(remote_url, api_key=api_key)
        try:
            client.refresh_session()
            console.print(
                "[bold green]✓ 远端服务凭据已成功刷新延长 30 天！[/bold green]"
            )
        except Exception as e:
            console.print(f"[bold red]✗ 远端凭据刷新失败:[/bold red] {e}")
            sys.exit(1)
        return

    console.print("[bold blue]正在向 Perplexity 请求刷新会话 Token...[/bold blue]")
    manager = PerplexityAuthManager()
    try:
        manager.refresh(force=True)
        creds = load_credentials()
        ttl = get_token_ttl_str(creds)
        console.print(
            f"[bold green]✓ 会话已成功刷新！新凭据剩余有效期: {ttl}[/bold green]"
        )
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
            title="Perplexity 运行模式与服务状态",
            show_header=True,
            header_style="bold magenta",
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
                table.add_row("远端用户名", user.get("name", "未知"))
                table.add_row("远端邮箱", user.get("email", "未知"))
                table.add_row("远端 Pro 订阅", "是" if auth_info.get("is_pro") else "否")
                table.add_row(
                    "远端凭据 TTL", get_token_ttl_str(auth_info)
                )
        except Exception:
            table.add_row("远端连接状态", "⚠️ 无法连接或响应超时")

        console.print(table)
        return

    creds = load_credentials()
    if not creds:
        console.print("[bold red]✗ 未找到本地 Perplexity 凭据文件！[/bold red]")
        console.print("请运行 [bold green]`pplx login`[/bold green] 从真实浏览器提取，或使用 [bold green]`pplx remote set <URL>`[/bold green] 接入远端服务。")
        return

    table = Table(
        title="Perplexity 账号与本地凭据信息",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("字段", style="cyan")
    table.add_column("值", style="green")

    user = creds.get("user", {})
    table.add_row("运行模式", "💻 本地凭据直连模式 (Local Mode)")
    table.add_row("用户名", user.get("name", "未知"))
    table.add_row("注册邮箱", user.get("email", "未知"))
    table.add_row("Pro 订阅状态", "✅ 是 (Pro)" if creds.get("is_pro") else "❌ 否 (Free)")
    table.add_row(
        "企业订阅",
        "✅ 是 (Enterprise)" if creds.get("is_enterprise") else "❌ 否",
    )
    table.add_row("凭据保存路径", str(get_credentials_path()))
    table.add_row("凭据剩余有效期", get_token_ttl_str(creds))

    console.print(table)


def cmd_ask(args):
    """终端实时搜索提问交互 (支持本地直连与远端 API 两种模式，支持专业垂直搜索领域)"""
    remote_url = get_remote_url(getattr(args, "remote", None))
    api_key = get_remote_api_key(getattr(args, "api_key", None))

    query = args.query
    raw_model = args.model
    mode = args.mode

    # 解析垂直搜索模式
    vertical = None
    if getattr(args, "patents", False):
        vertical = "patents"
    elif getattr(args, "academic", False):
        vertical = "academic"
    elif getattr(args, "finance", False):
        vertical = "finance"
    elif getattr(args, "social", False):
        vertical = "social"
    else:
        vertical = getattr(args, "vertical", None)

    # 自动解析复合模型名 (如 patents:claude-3-7-sonnet 或 academic)
    model, parsed_vertical = parse_model_and_vertical(
        raw_model, explicit_vertical=vertical
    )
    effective_vertical = parsed_vertical or "web"
    vert_info = SEARCH_VERTICALS.get(
        effective_vertical, SEARCH_VERTICALS["web"]
    )

    badge_colors = {
        "patents": "bold green",
        "academic": "bold cyan",
        "finance": "bold yellow",
        "social": "bold magenta",
        "health": "bold red",
        "web": "bold blue",
    }
    b_color = badge_colors.get(effective_vertical, "bold blue")
    vert_badge = f"[{b_color}][{vert_info['name']}][/{b_color}]"

    if remote_url:
        console.print(
            f"[bold cyan]🔍 正在向远端 API 发起搜索[/bold cyan] {vert_badge} [bold magenta]({escape(model)})[/bold magenta]: {escape(query)} [dim]({remote_url})[/dim]\n"
        )
        client = RemotePerplexityClient(remote_url, api_key=api_key)
    else:
        console.print(
            f"[bold cyan]🔍 正在向 Perplexity 发起搜索[/bold cyan] {vert_badge} [bold magenta]({escape(model)} / {escape(mode)})[/bold magenta]: {escape(query)}\n"
        )
        client = PerplexityClient()

    if args.raw:
        console.print(
            "[bold yellow]--- 进入 RAW 调试模式 (原始 SSE 事件流) ---[/bold yellow]"
        )
        for chunk in client.ask_stream(
            query, model=model, mode=mode, vertical=effective_vertical
        ):
            raw = chunk.get("raw_event", {})
            if raw:
                syntax = Syntax(
                    json.dumps(raw, ensure_ascii=False, indent=2),
                    "json",
                    theme="monokai",
                )
                console.print(syntax)
                time.sleep(0.05)
        return

    last_sources = []
    ans = ""
    if sys.stdout.isatty():
        with Live(console=console, refresh_per_second=12) as live:
            for chunk in client.ask_stream(
                query, model=model, mode=mode, vertical=effective_vertical
            ):
                ans = chunk["answer"]
                last_sources = chunk.get("sources", [])
                live.update(Markdown(ans))
    else:
        for chunk in client.ask_stream(
            query, model=model, mode=mode, vertical=effective_vertical
        ):
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
        description="Perplexity Search2API — 深度搜索与前沿大模型网关 CLI",
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
        "--api-key",
        dest="api_key",
        type=str,
        default=None,
        help="临时指定远端服务 API 密钥",
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # remote
    remote_p = subparsers.add_parser(
        "remote", help="管理与设置远端 API 端点 (免本地凭据存储)"
    )
    remote_sub = remote_p.add_subparsers(
        dest="remote_action", help="远端操作命令"
    )

    # remote set <url>
    remote_set_p = remote_sub.add_parser(
        "set", help="设置并绑定远端 API 端点"
    )
    remote_set_p.add_argument(
        "url", type=str, help="远端服务 URL (如 http://orangepi:53024/)"
    )
    remote_set_p.add_argument(
        "--api-key", type=str, default=None, help="可选 API Key"
    )
    remote_set_p.add_argument(
        "--default-model", type=str, default=None, help="可选默认模型"
    )

    # remote show / get / status
    remote_sub.add_parser(
        "show", aliases=["get", "status"], help="查看当前远端配置状态与连通性"
    )

    # remote unset / remove / clear
    remote_sub.add_parser(
        "unset",
        aliases=["remove", "clear"],
        help="清除已配置的远端端点，恢复本地模式",
    )

    # remote test
    remote_sub.add_parser("test", help="测试当前远端端点连通性")

    # login
    login_p = subparsers.add_parser(
        "login", help="从本地真实浏览器中提取 SSO 会话 Token"
    )
    login_p.add_argument(
        "--local",
        action="store_true",
        help="忽略已配置的远端端点，强制提取并保存本地凭据",
    )

    # refresh
    refresh_p = subparsers.add_parser(
        "refresh", help="主动刷新 NextAuth 会话凭据 (支持本地与远端)"
    )
    refresh_p.add_argument(
        "--local",
        action="store_true",
        help="强制刷新本地凭据而非远端凭据",
    )

    # info
    info_p = subparsers.add_parser(
        "info", help="查看当前认证状态、企业 Pro 订阅与凭证 TTL"
    )
    info_p.add_argument(
        "--local",
        action="store_true",
        help="强制查看本地凭证而非远端状态",
    )

    # models
    models_p = subparsers.add_parser(
        "models", help="查看可用大模型列表与搜索垂直模型 (支持远端与本地查询)"
    )
    models_p.add_argument(
        "--remote",
        "--base-url",
        dest="remote",
        type=str,
        default=None,
        help="指定远端 API URL",
    )
    models_p.add_argument(
        "--api-key",
        dest="api_key",
        type=str,
        default=None,
        help="指定远端 API Key",
    )

    # ask / search / s
    ask_p = subparsers.add_parser(
        "ask",
        aliases=["search", "s"],
        help="直接在终端发起流式搜索提问 (别名: search, s)",
    )
    ask_p.add_argument("query", type=str, help="搜索或提问内容")
    ask_p.add_argument(
        "--model",
        type=str,
        default="experimental",
        help="模型选择 (如 experimental, claude-3-7-sonnet, grok-4.6, 或复合模型如 patents:claude-3-7-sonnet)",
    )
    ask_p.add_argument(
        "--mode",
        type=str,
        default="copilot",
        help="搜索模式 (copilot, concise 等)",
    )
    ask_p.add_argument(
        "-V",
        "--vertical",
        type=str,
        default=None,
        choices=[
            "web",
            "patents",
            "academic",
            "finance",
            "social",
            "health",
            "writing",
            "wolfram",
            "youtube",
            "reddit",
        ],
        help="选择搜索垂直领域/模型 (默认: web, 可选: patents 专利, academic 学术, finance 金融, social 社交等)",
    )
    ask_p.add_argument(
        "--patents",
        action="store_true",
        help="快捷启用 Perplexity Patents (全球专利检索与现有技术分析)",
    )
    ask_p.add_argument(
        "--academic",
        action="store_true",
        help="快捷启用 Perplexity Academic (学术文献、arXiv、PubMed 与期刊检索)",
    )
    ask_p.add_argument(
        "--finance",
        action="store_true",
        help="快捷启用 Perplexity Finance (金融市场行情、SEC财报与业绩电话会)",
    )
    ask_p.add_argument(
        "--social",
        action="store_true",
        help="快捷启用 Social (社交讨论、Reddit 与 Twitter/X 真实口碑)",
    )
    ask_p.add_argument(
        "--raw", action="store_true", help="打印原始 SSE 事件流数据进行调试"
    )

    # serve
    serve_p = subparsers.add_parser(
        "serve", help="启动 OpenAI 兼容标准接口服务器 (/v1/chat/completions)"
    )
    serve_p.add_argument(
        "--host", type=str, default="0.0.0.0", help="监听主机 (默认: 0.0.0.0)"
    )
    serve_p.add_argument(
        "--port", type=int, default=8000, help="监听端口 (默认: 8000)"
    )

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