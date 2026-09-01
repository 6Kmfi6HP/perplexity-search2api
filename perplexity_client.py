"""
Perplexity API 客户端 (Perplexity Ask / Copilot / Pro Client)
- 支持流式 (Streaming) 与非流式 (Non-streaming) 查询
- 支持精准指定 Pro / Max 全系列大模型 (Claude 5, GPT-5.6, Grok 4.6, Gemini 3.7, GLM 5.3/5.2, Kimi K3, Nemotron 等)
- 支持解析 Web Search 引用来源 (Sources / Citations)
"""

import json
import uuid
from collections.abc import Generator
from typing import Any

import httpx

from perplexity_auth import APP_USER_AGENT, PerplexityAuthManager

ASK_ENDPOINT = "https://www.perplexity.ai/rest/sse/perplexity_ask"

# 用户友好模型名称与 Perplexity 后端 internal key 映射表
MODEL_ALIASES: dict[str, str] = {
    # 最佳可用模型
    "experimental": "experimental",
    "auto": "experimental",
    "best": "experimental",
    "default": "experimental",

    # Perplexity 官方 Sonar Pro / 2
    "pplx_pro": "pplx_pro",
    "sonar": "pplx_pro",
    "sonar-pro": "pplx_pro",
    "sonar-2": "pplx_pro",

    # OpenAI GPT
    "gpt56_terra": "gpt56_terra",
    "gpt-5.6": "gpt56_terra",
    "gpt-5.6-terra": "gpt56_terra",
    "gpt-5": "gpt56_terra",
    "gpt-4o": "gpt56_terra",
    "gpt-4": "gpt56_terra",
    "gpt56_sol": "gpt56_sol",
    "gpt-5.6-sol": "gpt56_sol",

    # Anthropic Claude
    "claude50sonnet": "claude50sonnet",
    "claude-sonnet-5": "claude50sonnet",
    "claude-3-7-sonnet": "claude50sonnet",
    "claude-3.7-sonnet": "claude50sonnet",
    "claude-3-5-sonnet": "claude50sonnet",
    "claude": "claude50sonnet",
    "claude50opus": "claude50opus",
    "claude-opus-5": "claude50opus",

    # Google Gemini
    "gemini37flash": "gemini37flash",
    "gemini-3.7-flash": "gemini37flash",
    "gemini-2.0-flash": "gemini37flash",
    "gemini": "gemini37flash",
    "gemini31pro_high": "gemini31pro_high",
    "gemini-3.1-pro": "gemini31pro_high",

    # xAI Grok (正在思考)
    "grok46low": "grok46low",
    "grok-4.6": "grok46low",
    "grok-3": "grok46low",
    "grok": "grok46low",

    # 智谱 GLM (正在思考)
    "glm_5_3_thinking": "glm_5_3_thinking",
    "glm-5.3": "glm_5_3_thinking",
    "glm-5": "glm_5_3_thinking",
    "glm": "glm_5_3_thinking",
    "glm_5_2": "glm_5_2",
    "glm-5.2": "glm_5_2",

    # 月之暗面 Kimi (正在思考)
    "kimik3thinking": "kimik3thinking",
    "kimi-k3": "kimik3thinking",
    "kimi-k3-thinking": "kimik3thinking",
    "kimi": "kimik3thinking",
    "kimik26instant": "kimik26instant",
    "kimi-k2.6": "kimik26instant",

    # NVIDIA Nemotron (正在思考)
    "nv_nemotron_3_ultra": "nv_nemotron_3_ultra",
    "nemotron-3-ultra": "nv_nemotron_3_ultra",
    "nemotron": "nv_nemotron_3_ultra",

    # 快速免费模式
    "turbo": "turbo",
    "fast": "turbo",
}


def resolve_model_name(model_name: str | None) -> str:
    """将输入的模型名称解析为 Perplexity 后端合法的 model_preference key"""
    if not model_name:
        return "experimental"
    norm = model_name.strip().lower()
    return MODEL_ALIASES.get(norm, norm)


class PerplexityClient:
    def __init__(self, auth_manager: PerplexityAuthManager | None = None):
        self.auth_manager = auth_manager or PerplexityAuthManager()

    def _build_headers(self, request_id: str | None = None) -> dict[str, str]:
        token = self.auth_manager.get_valid_token()
        req_id = request_id or str(uuid.uuid4())

        cookies = [f"__Secure-next-auth.session-token={token}"]
        if self.auth_manager.cf_clearance:
            cookies.append(f"cf_clearance={self.auth_manager.cf_clearance}")

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
        mode: str = "copilot",
        search_focus: str = "internet",
        language: str | None = None,
    ) -> dict[str, Any]:
        target_model = resolve_model_name(model)
        params = {
            "query_str": query,
            "search_focus": search_focus,
            "mode": mode,
            "model_preference": target_model,
            "sources": ["web"],
            "should_ask_for_mcp_tool_confirmation": False,
            "supports_tool_approval_modal": False,
            "force_enable_browser_agent": False,
            "is_local_browser_available": False,
            "is_local_browser_allowed": False,
        }
        if language:
            params["search_language_filter"] = language

        return {
            "query_str": query,
            "params": params,
        }

    def ask_stream(
        self,
        query: str,
        model: str = "experimental",
        mode: str = "copilot",
        timeout: float = 60.0,
    ) -> Generator[dict[str, Any], None, None]:
        headers = self._build_headers()
        payload = self._build_payload(query, model=model, mode=mode)
        resolved_model = payload["params"]["model_preference"]

        with httpx.Client(timeout=timeout) as client:
            with client.stream("POST", ASK_ENDPOINT, headers=headers, json=payload) as response:
                if response.status_code == 401:
                    self.auth_manager.refresh(force=True)
                    headers = self._build_headers()
                    yield from self.ask_stream(query, model=model, mode=mode, timeout=timeout)
                    return

                if response.status_code != 200:
                    error_text = response.read().decode("utf-8", errors="ignore")
                    raise RuntimeError(f"Perplexity API 请求失败 ({response.status_code}): {error_text}")

                last_answer = ""
                seen_sources = {}
                display_model = resolved_model

                for line in response.iter_lines():
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

                        current_answer = ""
                        blocks = event.get("blocks", [])
                        for b in blocks:
                            if b.get("intended_usage") == "ask_text":
                                current_answer = b.get("markdown_block", {}).get("answer", "")
                            elif b.get("intended_usage") == "sources":
                                for s in b.get("sources_block", {}).get("sources", []):
                                    url = s.get("url")
                                    if url and url not in seen_sources:
                                        seen_sources[url] = s

                        delta = ""
                        if len(current_answer) > len(last_answer):
                            delta = current_answer[len(last_answer):]
                            last_answer = current_answer

                        yield {
                            "type": "delta",
                            "delta": delta,
                            "answer": current_answer,
                            "sources": list(seen_sources.values()),
                            "display_model": display_model,
                            "raw_event": event,
                        }

    def ask(
        self,
        query: str,
        model: str = "experimental",
        mode: str = "copilot",
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        final_answer = ""
        sources = []
        display_model = model
        raw_event = {}

        for chunk in self.ask_stream(query, model=model, mode=mode, timeout=timeout):
            final_answer = chunk["answer"]
            sources = chunk["sources"]
            display_model = chunk["display_model"]
            raw_event = chunk["raw_event"]

        return {
            "query": query,
            "answer": final_answer,
            "sources": sources,
            "model": display_model,
            "raw_event": raw_event,
        }
