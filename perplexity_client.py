"""
Perplexity API 客户端 (Perplexity Ask / Copilot / Pro Client)
- 支持异步流式 (Async Streaming) 与同步流式 (Sync Streaming) 查询
- 实时捕获搜索过程事件 (Search Progress / Thinking / Web Results)
- 精准解析 Web Search 引用来源 (Sources / Citations / Web Results)
- 兼容实时 Chunks 增量 Token 流与完整快照同步
- 支持 Pro / Max 全系列大模型
"""

import json
import re
import uuid
from collections.abc import AsyncGenerator, Generator
from typing import Any

import httpx

from perplexity_auth import APP_USER_AGENT, PerplexityAuthManager

ASK_ENDPOINT = "https://www.perplexity.ai/rest/sse/perplexity_ask"

# 用户友好模型名称与 Perplexity 后端 internal key 映射表
MODEL_ALIASES: dict[str, str] = {
    # 最佳可用模型 (Auto / Best)
    "experimental": "experimental",
    "auto": "experimental",
    "best": "experimental",
    "default": "experimental",
    "pplx_pro": "pplx_pro",
    "sonar-pro": "pplx_pro",
    "sonar": "pplx_pro",
    "turbo": "turbo",
    "fast": "turbo",
    "sonar-small": "turbo",

    # OpenAI 全系列
    "gpt-5.6": "gpt56_terra",
    "gpt-5.6-terra": "gpt56_terra",
    "gpt-5.6-thinking": "gpt56_terra",
    "gpt56_terra": "gpt56_terra",
    "gpt-5.6-instant": "gpt56_sol",
    "gpt-5.6-sol": "gpt56_sol",
    "gpt56_sol": "gpt56_sol",
    "gpt-4o": "gpt56_terra",
    "gpt-4": "gpt56_terra",
    "gpt-4.5": "gpt56_terra",
    "o1": "gpt56_terra",
    "o3-mini": "gpt56_terra",

    # Anthropic Claude 3.7 / 3.5 系列
    "claude-3-7-sonnet": "claude50sonnet",
    "claude-3-7-sonnet-thinking": "claude50sonnet",
    "claude-3.7-sonnet": "claude50sonnet",
    "claude-3-5-sonnet": "claude50sonnet",
    "claude50sonnet": "claude50sonnet",
    "claude-3-5-haiku": "claude50sonnet",
    "claude-3-opus": "claude50opus",
    "claude-opus": "claude50opus",
    "claude50opus": "claude50opus",

    # Google Gemini 系列
    "gemini-2.5-flash": "gemini37flash",
    "gemini-2.5-pro": "gemini31pro_high",
    "gemini-3.7-flash": "gemini37flash",
    "gemini37flash": "gemini37flash",
    "gemini-3.1-pro": "gemini31pro_high",
    "gemini31pro_high": "gemini31pro_high",

    # xAI Grok 系列
    "grok-4.6": "grok46low",
    "grok-4": "grok46low",
    "grok46low": "grok46low",
    "grok-2": "grok46low",

    # 智谱 GLM 系列
    "glm-5.3": "glm_5_3_thinking",
    "glm-5.3-thinking": "glm_5_3_thinking",
    "glm_5_3_thinking": "glm_5_3_thinking",
    "glm-5.2": "glm_5_2",
    "glm_5_2": "glm_5_2",

    # 月之暗面 Kimi 系列
    "kimi-k3": "kimik3thinking",
    "kimi-k3-thinking": "kimik3thinking",
    "kimik3thinking": "kimik3thinking",
    "kimi-k2.6": "kimik26instant",
    "kimi-k2.6-instant": "kimik26instant",
    "kimik26instant": "kimik26instant",

    # NVIDIA Nemotron 系列
    "nemotron-3": "nv_nemotron_3_ultra",
    "nemotron-3-ultra": "nv_nemotron_3_ultra",
    "nv_nemotron_3_ultra": "nv_nemotron_3_ultra",
}


def resolve_model_name(model_name: str | None) -> str:
    """将输入的模型名称解析为 Perplexity 后端合法的 model_preference key"""
    if not model_name:
        return "experimental"
    norm = model_name.strip().lower()
    if norm in MODEL_ALIASES:
        return MODEL_ALIASES[norm]
    # 支持带模式后缀的模型名，如 claude-3-7-sonnet-copilot, gpt-5.6-deep
    clean_norm = re.sub(r"-(copilot|deep|concise|fast)$", "", norm)
    return MODEL_ALIASES.get(clean_norm, norm)


class PerplexityClient:
    """Perplexity Search & Ask 客户端 (支持同步与原生异步流式处理)"""

    def __init__(self, auth_manager: PerplexityAuthManager | None = None):
        self.auth_manager = auth_manager or PerplexityAuthManager()

    def _build_headers(self, request_id: str | None = None) -> dict[str, str]:
        token = self.auth_manager.get_valid_token()
        req_id = request_id or str(uuid.uuid4())

        cookies = [f"__Secure-next-auth.session-token={token}"]
        cf_clearance = getattr(self.auth_manager, "cf_clearance", None)
        if cf_clearance:
            cookies.append(f"cf_clearance={cf_clearance}")

        return {
            "User-Agent": APP_USER_AGENT,
            "X-App-ApiClient": "default",
            "X-App-ApiVersion": "2.18",
            "X-Perplexity-Request-Reason": "submit",
            "X-Request-ID": req_id,
            "Origin": "https://www.perplexity.ai",
            "Referer": "https://www.perplexity.ai/",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Cookie": "; ".join(cookies),
        }

    def _build_payload(
        self,
        query: str,
        model: str = "experimental",
        mode: str = "concise",
        search_focus: str = "internet",
        sources: list[str] | None = None,
    ) -> dict[str, Any]:
        resolved_model = resolve_model_name(model)
        sources_list = sources or ["web"]

        params: dict[str, Any] = {
            "query_str": query,
            "search_focus": search_focus,
            "mode": mode,
            "model_preference": resolved_model,
            "sources": sources_list,
            "should_ask_for_mcp_tool_confirmation": False,
            "supports_tool_approval_modal": False,
            "force_enable_browser_agent": False,
            "is_local_browser_available": False,
            "is_local_browser_allowed": False,
        }

        return {
            "query_str": query,
            "params": params,
        }

    async def ask_async_stream(
        self,
        query: str,
        model: str = "experimental",
        mode: str = "concise",
        timeout: float = 60.0,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        原生异步流式请求 Perplexity API，实时产出：
        1. 搜索与思考进度 (type="progress")
        2. 增量文本 (type="delta")
        3. 完整文本快照与引用源 (sources)
        """
        headers = self._build_headers()
        payload = self._build_payload(query, model=model, mode=mode)
        resolved_model = payload["params"]["model_preference"]

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", ASK_ENDPOINT, headers=headers, json=payload) as response:
                if response.status_code == 401:
                    # Token 过期，强制刷新并重试一次
                    self.auth_manager.refresh(force=True)
                    headers = self._build_headers()
                    async for item in self.ask_async_stream(query, model=model, mode=mode, timeout=timeout):
                        yield item
                    return

                if response.status_code != 200:
                    error_bytes = await response.aread()
                    error_text = error_bytes.decode("utf-8", errors="ignore")
                    raise RuntimeError(f"Perplexity API 请求失败 ({response.status_code}): {error_text}")

                accumulated_text = ""
                seen_sources: dict[str, dict[str, Any]] = {}
                display_model = resolved_model
                last_sources_count = 0

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if not data_str:
                            continue
                        try:
                            event = json.loads(data_str)
                        except Exception:
                            continue

                        if event.get("error_code"):
                            msg = event.get("error_message") or event.get("error_code")
                            raise RuntimeError(f"Perplexity Stream 错误: {msg}")

                        if event.get("display_model"):
                            display_model = event["display_model"]

                        delta = ""
                        has_new_sources = False
                        blocks = event.get("blocks", [])

                        for b in blocks:
                            usage = b.get("intended_usage", "")

                            # 1. 文本内容流式解析 (ask_text, ask_text_*_markdown 等)
                            if usage.startswith("ask_text") or "markdown_block" in b:
                                mb = b.get("markdown_block", {})
                                ans = mb.get("answer", "")
                                chunks = mb.get("chunks", [])

                                if ans:
                                    if len(ans) > len(accumulated_text):
                                        delta = ans[len(accumulated_text):]
                                        accumulated_text = ans
                                elif chunks:
                                    d = "".join(chunks)
                                    if d:
                                        delta = d
                                        accumulated_text += d

                            # 2. 联网搜索与引用来源解析 (web_results, sources)
                            if usage in ("sources", "web_results") or "web_result_block" in b or "sources_block" in b:
                                raw_sources = []
                                if "web_result_block" in b:
                                    raw_sources.extend(b["web_result_block"].get("web_results", []))
                                if "sources_block" in b:
                                    raw_sources.extend(b["sources_block"].get("sources", []))

                                for s in raw_sources:
                                    url = s.get("url")
                                    if url and url not in seen_sources:
                                        seen_sources[url] = {
                                            "name": s.get("name") or s.get("title") or "网页",
                                            "url": url,
                                            "snippet": s.get("snippet", ""),
                                            "timestamp": s.get("timestamp", ""),
                                        }
                                        has_new_sources = True

                        current_sources = list(seen_sources.values())

                        # 如果抓取到了新的搜索结果，但还没有正文文本，推送搜索进度事件
                        if has_new_sources and not delta and not accumulated_text:
                            if len(current_sources) > last_sources_count:
                                last_sources_count = len(current_sources)
                                yield {
                                    "type": "progress",
                                    "progress_type": "search",
                                    "sources_count": len(current_sources),
                                    "sources": current_sources,
                                    "display_model": display_model,
                                }

                        # 如果产生了文本增量
                        if delta or accumulated_text:
                            yield {
                                "type": "delta",
                                "delta": delta,
                                "answer": accumulated_text,
                                "sources": current_sources,
                                "display_model": display_model,
                                "raw_event": event,
                            }

    def ask_stream(
        self,
        query: str,
        model: str = "experimental",
        mode: str = "concise",
        timeout: float = 60.0,
    ) -> Generator[dict[str, Any], None, None]:
        """
        同步流式请求 Perplexity API (兼容旧接口)
        """
        headers = self._build_headers()
        payload = self._build_payload(query, model=model, mode=mode)
        resolved_model = payload["params"]["model_preference"]

        with httpx.Client(timeout=timeout) as client:
            with client.stream("POST", ASK_ENDPOINT, headers=headers, json=payload) as response:
                if response.status_code == 401:
                    self.auth_manager.refresh(force=True)
                    yield from self.ask_stream(query, model=model, mode=mode, timeout=timeout)
                    return

                if response.status_code != 200:
                    error_text = response.read().decode("utf-8", errors="ignore")
                    raise RuntimeError(f"Perplexity API 请求失败 ({response.status_code}): {error_text}")

                accumulated_text = ""
                seen_sources: dict[str, dict[str, Any]] = {}
                display_model = resolved_model

                for line in response.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if not data_str:
                        continue
                    try:
                        event = json.loads(data_str)
                    except Exception:
                        continue

                    if event.get("error_code"):
                        msg = event.get("error_message") or event.get("error_code")
                        raise RuntimeError(f"Perplexity Stream 错误: {msg}")

                    if event.get("display_model"):
                        display_model = event["display_model"]

                    delta = ""
                    blocks = event.get("blocks", [])
                    for b in blocks:
                        usage = b.get("intended_usage", "")

                        if usage.startswith("ask_text") or "markdown_block" in b:
                            mb = b.get("markdown_block", {})
                            ans = mb.get("answer", "")
                            chunks = mb.get("chunks", [])

                            if ans:
                                if len(ans) > len(accumulated_text):
                                    delta = ans[len(accumulated_text):]
                                    accumulated_text = ans
                            elif chunks:
                                d = "".join(chunks)
                                if d:
                                    delta = d
                                    accumulated_text += d

                        if usage in ("sources", "web_results") or "web_result_block" in b or "sources_block" in b:
                            raw_sources = []
                            if "web_result_block" in b:
                                raw_sources.extend(b["web_result_block"].get("web_results", []))
                            if "sources_block" in b:
                                raw_sources.extend(b["sources_block"].get("sources", []))

                            for s in raw_sources:
                                url = s.get("url")
                                if url and url not in seen_sources:
                                    seen_sources[url] = {
                                        "name": s.get("name") or s.get("title") or "网页",
                                        "url": url,
                                        "snippet": s.get("snippet", ""),
                                        "timestamp": s.get("timestamp", ""),
                                    }

                    yield {
                        "type": "delta",
                        "delta": delta,
                        "answer": accumulated_text,
                        "sources": list(seen_sources.values()),
                        "display_model": display_model,
                        "raw_event": event,
                    }

    def ask(
        self,
        query: str,
        model: str = "experimental",
        mode: str = "concise",
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        """
        非流式请求封装
        """
        final_answer = ""
        sources = []
        display_model = model
        raw_event = {}

        for chunk in self.ask_stream(query, model=model, mode=mode, timeout=timeout):
            if chunk.get("answer"):
                final_answer = chunk["answer"]
            if chunk.get("sources"):
                sources = chunk["sources"]
            if chunk.get("display_model"):
                display_model = chunk["display_model"]
            raw_event = chunk.get("raw_event", {})

        return {
            "query": query,
            "answer": final_answer,
            "sources": sources,
            "model": display_model,
            "raw_event": raw_event,
        }
