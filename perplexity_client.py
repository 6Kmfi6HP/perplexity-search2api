"""
Perplexity API 客户端 (Perplexity Ask / Copilot / Pro Client)
- 支持异步流式 (Async Streaming) 与同步流式 (Sync Streaming) 查询
- 深度兼容 Perplexity 最新 workflow_root、workflow_block、markdown_block 及 legacy 文本数据结构
- 支持多种专业垂直搜索模型与领域 (Search Verticals & Focus Domains):
  * Web (默认全网综合搜索)
  * Patents (https://www.perplexity.ai/patents 专利检索、IPC/CPC分类与现有技术分析)
  * Academic (https://www.perplexity.ai/academic 学术文献、arXiv、PubMed、JSTOR、DOI期刊论文)
  * Finance (https://www.perplexity.ai/finance 金融市场、SEC财报、高管会议纪要、华尔街分析师共识)
  * Social (社交网络、Reddit、Twitter/X、社区讨论与观点挖掘)
  * Health (临床医学、健康指南、医药参考)
  * Writing / Wolfram / YouTube / Reddit 经典 Focus 模式
- 支持复合模型名称语法 (如 patents:claude-3-7-sonnet, academic:sonar, finance:gpt-5.6)
- 实时捕获搜索过程事件 (Search Progress / Thinking / Web Results / Citations)
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
from perplexity_config import get_remote_api_key, get_remote_url

ASK_ENDPOINT = "https://www.perplexity.ai/rest/sse/perplexity_ask"

# 专业搜索领域与垂直模型预设定义
SEARCH_VERTICALS: dict[str, dict[str, Any]] = {
    "web": {
        "id": "web",
        "name": "Web Search (全网搜索)",
        "query_source": "home",
        "sources": ["web"],
        "search_focus": "internet",
        "description": "实时全面索引整个互联网，适用于通用事实检索、新闻热点与综合知识问答。",
        "url": "https://www.perplexity.ai/",
    },
    "patents": {
        "id": "patents",
        "name": "Perplexity Patents (专利检索)",
        "query_source": "patents",
        "sources": ["web"],
        "search_focus": "internet",
        "description": "深度检索全球专利文献 (Google Patents, USPTO, EPO, WIPO, PubChem Patent)，提取专利号、申请人、CPC分类、权利要求与现有技术分析。",
        "url": "https://www.perplexity.ai/patents",
    },
    "academic": {
        "id": "academic",
        "name": "Perplexity Academic (学术文献)",
        "query_source": "academic",
        "sources": ["scholar"],
        "search_focus": "internet",
        "description": "专为学术研究打造，定向检索 arXiv、PubMed、Semantic Scholar、IEEE、Nature、ScienceDirect、JSTOR 等同行评审论文与期刊。",
        "url": "https://www.perplexity.ai/academic",
    },
    "finance": {
        "id": "finance",
        "name": "Perplexity Finance (金融与市场)",
        "query_source": "finance",
        "sources": ["web"],
        "search_focus": "internet",
        "canonical_page_context": {
            "page_type": "finance",
            "data": {
                "section_name": "market",
                "country": "US",
            },
        },
        "description": "接入机构级金融数据 (FMP, Quartr, Fiscal.ai, S&P Global, SEC Filings)，检索股票实时行情、财报数据、业绩电话会纪要与分析师目标价。",
        "url": "https://www.perplexity.ai/finance",
    },
    "social": {
        "id": "social",
        "name": "Social & Discussions (社交与讨论)",
        "query_source": "social",
        "sources": ["social"],
        "search_focus": "internet",
        "description": "聚合社交平台、Reddit 社区、Twitter/X 与论坛真实用户讨论、使用体验与真实口碑。",
        "url": "https://www.perplexity.ai/",
    },
    "health": {
        "id": "health",
        "name": "Health & Clinical (健康与医疗)",
        "query_source": "health",
        "sources": ["health"],
        "search_focus": "internet",
        "description": "检索临床医学文献、循证医疗指南、疾病预防与权威健康医疗参考数据。",
        "url": "https://www.perplexity.ai/",
    },
    "writing": {
        "id": "writing",
        "name": "Writing & Generation (纯文本生成)",
        "query_source": "home",
        "sources": [],
        "search_focus": "writing",
        "description": "直接调用大模型进行创作、代码生成或文本改写，不触发任何联网搜索。",
        "url": "https://www.perplexity.ai/",
    },
    "wolfram": {
        "id": "wolfram",
        "name": "Wolfram Alpha (计算与数理)",
        "query_source": "home",
        "sources": [],
        "search_focus": "wolfram",
        "description": "利用 Wolfram Alpha 计算引擎进行高精数理计算、方程求解、物理公式与结构化科学数据分析。",
        "url": "https://www.perplexity.ai/",
    },
    "youtube": {
        "id": "youtube",
        "name": "YouTube Search (视频搜索)",
        "query_source": "home",
        "sources": [],
        "search_focus": "youtube",
        "description": "针对 YouTube 视频、播客、字幕转录文稿及时间戳进行精准定向检索与内容提炼。",
        "url": "https://www.perplexity.ai/",
    },
    "reddit": {
        "id": "reddit",
        "name": "Reddit Search (社区搜索)",
        "query_source": "home",
        "sources": [],
        "search_focus": "reddit",
        "description": "专一检索 Reddit 社区帖子、热门 Subreddit 讨论与深度评论互动。",
        "url": "https://www.perplexity.ai/",
    },
}

# 垂直领域别名字典
VERTICAL_ALIASES: dict[str, str] = {
    "web": "web",
    "internet": "web",
    "default": "web",
    "home": "web",
    "patents": "patents",
    "patent": "patents",
    "academic": "academic",
    "scholar": "academic",
    "paper": "academic",
    "papers": "academic",
    "finance": "finance",
    "financial": "finance",
    "stock": "finance",
    "stocks": "finance",
    "market": "finance",
    "markets": "finance",
    "social": "social",
    "discussions": "social",
    "forum": "social",
    "health": "health",
    "medical": "health",
    "medicine": "health",
    "writing": "writing",
    "wolfram": "wolfram",
    "math": "wolfram",
    "youtube": "youtube",
    "video": "youtube",
    "reddit": "reddit",
}

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
    """将用户输入的模型名称/别名转换为 Perplexity 后端识别的模型参数"""
    if not model_name:
        return "experimental"
    norm = model_name.strip().lower()
    if norm in MODEL_ALIASES:
        return MODEL_ALIASES[norm]
    # 支持带模式后缀的模型名，如 claude-3-7-sonnet-copilot, gpt-5.6-deep
    clean_norm = re.sub(r"-(copilot|deep|concise|fast)$", "", norm)
    return MODEL_ALIASES.get(clean_norm, norm)


def resolve_vertical_config(
    vertical: str | None = None,
    sources: list[str] | None = None,
    search_focus: str | None = None,
    query_source: str | None = None,
    canonical_page_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """解析垂直搜索领域配置 (query_source, sources, search_focus, canonical_page_context)"""
    norm_v = (vertical or "").strip().lower()
    canonical_id = VERTICAL_ALIASES.get(norm_v, norm_v) if norm_v else None

    preset = SEARCH_VERTICALS.get(canonical_id or "web", SEARCH_VERTICALS["web"])

    final_query_source = query_source or preset.get("query_source", "home")
    final_search_focus = search_focus or preset.get("search_focus", "internet")
    final_sources = (
        sources if sources is not None else list(preset.get("sources", ["web"]))
    )
    final_context = (
        canonical_page_context
        if canonical_page_context is not None
        else preset.get("canonical_page_context")
    )

    return {
        "vertical": canonical_id or "web",
        "query_source": final_query_source,
        "search_focus": final_search_focus,
        "sources": final_sources,
        "canonical_page_context": final_context,
        "description": preset.get("description", ""),
        "url": preset.get("url", "https://www.perplexity.ai/"),
    }


def parse_model_and_vertical(
    model: str | None,
    explicit_vertical: str | None = None,
) -> tuple[str, str | None]:
    """
    解析模型名称与垂直搜索模式。
    支持显式参数以及复合语法:
    - "patents:claude-3-7-sonnet" -> ("claude-3-7-sonnet", "patents")
    - "academic/sonar" -> ("sonar", "academic")
    - "finance:gpt-5.6" -> ("gpt-5.6", "finance")
    - "patents" -> ("experimental", "patents")
    - "claude-3-7-sonnet", explicit_vertical="academic" -> ("claude-3-7-sonnet", "academic")
    """
    if explicit_vertical and explicit_vertical.strip():
        norm_v = explicit_vertical.strip().lower()
        return (model or "experimental"), VERTICAL_ALIASES.get(norm_v, norm_v)

    clean_model = (model or "").strip()
    if not clean_model:
        return "experimental", None

    # 如果整个模型名称就是一个垂直领域名称 (如 "patents", "academic", "finance")
    if clean_model.lower() in VERTICAL_ALIASES:
        return "experimental", VERTICAL_ALIASES[clean_model.lower()]

    # 检查复合前缀语法: "patents:claude-3-7-sonnet", "academic/sonar", "finance:gpt-5.6"
    for sep in (":", "/"):
        if sep in clean_model:
            prefix, rest = clean_model.split(sep, 1)
            prefix_norm = prefix.strip().lower()
            if prefix_norm in VERTICAL_ALIASES and rest.strip():
                return rest.strip(), VERTICAL_ALIASES[prefix_norm]

    return clean_model, None


def extract_event_payload(
    event: dict[str, Any],
    accumulated_text: str,
    seen_sources: dict[str, dict[str, Any]],
) -> tuple[str, str, bool]:
    """
    统一解析 Perplexity SSE Event 中的增量文本、完整回答与引用源。
    支持格式：
    1. workflow_root / workflow_block (最新专业搜索架构)
    2. ask_text / answer / markdown_block (标准结构化回答架构)
    3. web_results / sources_block (引用数据源)
    4. text / answer 根节点覆盖
    """
    delta = ""
    updated_text = accumulated_text
    has_new_sources = False
    start_sources_len = len(seen_sources)

    blocks = event.get("blocks", [])

    for b in blocks:
        usage = b.get("intended_usage") or b.get("intended_use_case")

        # 1. 现代化 workflow_root / workflow_block 架构解析
        if usage == "workflow_root" or "workflow_block" in b:
            wb = b.get("workflow_block") or b
            steps = wb.get("steps", [])
            for step in steps:
                items = step.get("items", [])
                for item in items:
                    itype = item.get("type", "")
                    payload = item.get("payload", {})

                    # 正文内容提取
                    if itype == "WORKFLOW_ITEM_TEXT" or "text_payload" in payload:
                        tp = payload.get("text_payload", {})
                        text_val = tp.get("text") or tp.get("markdown") or ""
                        chunks_val = tp.get("chunks", [])

                        if text_val:
                            if len(text_val) > len(updated_text):
                                delta = text_val[len(updated_text) :]
                                updated_text = text_val
                        elif chunks_val:
                            d = "".join(chunks_val)
                            if d and len(d) > len(updated_text):
                                delta = d[len(updated_text) :]
                                updated_text = d

                    # 工作流内部实时搜索源提取
                    if itype == "WORKFLOW_ITEM_SOURCES" or "sources_payload" in payload:
                        sp = payload.get("sources_payload", {})
                        for s in sp.get("sources", []):
                            url = s.get("url")
                            if url and url not in seen_sources:
                                seen_sources[url] = {
                                    "name": s.get("name") or s.get("title") or "网页",
                                    "url": url,
                                    "snippet": s.get("snippet", ""),
                                }

        # 2. 标准 ask_text / answer / markdown_block 架构解析
        if usage in ("ask_text", "answer") or "markdown_block" in b:
            mb = b.get("markdown_block") or b
            ans = (
                mb.get("answer")
                or mb.get("markdown")
                or b.get("markdown")
                or b.get("answer")
                or ""
            )
            chunks = mb.get("chunks", [])

            if ans:
                if len(ans) > len(updated_text):
                    delta = ans[len(updated_text) :]
                    updated_text = ans
            elif chunks:
                d = "".join(chunks)
                if d:
                    if len(d) > len(updated_text):
                        delta = d[len(updated_text) :]
                        updated_text = d
                    else:
                        delta = d
                        updated_text += d

        # 3. 独立引用源 Block (web_results, sources_block)
        if (
            usage in ("sources", "web_results")
            or "web_result_block" in b
            or "sources_block" in b
        ):
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
                    }

    # 4. 兼容根节点 web_results 列表
    if "web_results" in event and isinstance(event["web_results"], list):
        for s in event["web_results"]:
            url = s.get("url")
            if url and url not in seen_sources:
                seen_sources[url] = {
                    "name": s.get("name") or s.get("title") or "网页",
                    "url": url,
                    "snippet": s.get("snippet", ""),
                }

    # 5. 兼容旧版本纯文本根字段覆盖流
    if not delta and "text" in event and event["text"]:
        raw_t = event["text"]
        if isinstance(raw_t, str) and raw_t:
            if len(raw_t) > len(updated_text):
                delta = raw_t[len(updated_text) :]
                updated_text = raw_t

    if len(seen_sources) > start_sources_len:
        has_new_sources = True

    return delta, updated_text, has_new_sources


class RemotePerplexityClient:
    """
    Perplexity Search2API 远端客户端
    直接调用部署在远端服务器上的 OpenAI 兼容接口 (/v1/chat/completions, /search, /auth/info 等)
    避免本地存储或提取任何 Perplexity 凭据与 Cookie。
    """

    def __init__(
        self,
        remote_url: str,
        api_key: str | None = None,
        timeout: float = 120.0,
    ):
        self.remote_url = remote_url.strip().rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    @property
    def base_url(self) -> str:
        return self.remote_url

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Perplexity-CLI-Remote/2.4.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["api-key"] = self.api_key
        return headers

    def _get_url(self, path: str) -> str:
        base = self.remote_url
        if base.endswith("/v1") and path.startswith("/v1/"):
            return f"{base}{path[3:]}"
        return f"{base}{path if path.startswith('/') else '/' + path}"

    def check_health(self, timeout: float = 5.0) -> dict[str, Any]:
        """检查远端服务健康状态"""
        headers = self._build_headers()
        req_timeout = httpx.Timeout(timeout, connect=5.0)
        with httpx.Client(timeout=req_timeout) as client:
            try:
                resp = client.get(self._get_url("/health"), headers=headers)
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass
            try:
                resp_root = client.get(self._get_url("/"), headers=headers)
                return {
                    "status": "ok" if resp_root.status_code < 400 else "error",
                    "code": resp_root.status_code,
                }
            except Exception:
                pass
            return {"status": "unreachable"}

    def get_models(self, timeout: float = 8.0) -> list[str]:
        """获取远端服务支持的模型列表"""
        headers = self._build_headers()
        req_timeout = httpx.Timeout(timeout, connect=5.0)
        with httpx.Client(timeout=req_timeout) as client:
            resp = client.get(self._get_url("/v1/models"), headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and "data" in data:
                    return [m["id"] for m in data["data"] if "id" in m]
            return []

    def get_verticals(self, timeout: float = 8.0) -> dict[str, Any]:
        """获取远端服务支持的搜索垂直领域列表 (/verticals)"""
        headers = self._build_headers()
        req_timeout = httpx.Timeout(timeout, connect=5.0)
        with httpx.Client(timeout=req_timeout) as client:
            try:
                resp = client.get(self._get_url("/verticals"), headers=headers)
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass
            return {"data": list(SEARCH_VERTICALS.values()), "aliases": VERTICAL_ALIASES}

    def get_auth_info(self, timeout: float = 8.0) -> dict[str, Any]:
        """获取远端服务登录与凭证状态 (/auth/info)"""
        headers = self._build_headers()
        req_timeout = httpx.Timeout(timeout, connect=5.0)
        with httpx.Client(timeout=req_timeout) as client:
            try:
                resp = client.get(self._get_url("/auth/info"), headers=headers)
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass
            return {}

    def refresh_session(self, timeout: float = 15.0) -> dict[str, Any]:
        """请求远端服务刷新其 Perplexity 登录凭据 (/auth/refresh)"""
        headers = self._build_headers()
        req_timeout = httpx.Timeout(timeout, connect=8.0)
        with httpx.Client(timeout=req_timeout) as client:
            resp = client.post(self._get_url("/auth/refresh"), headers=headers)
            if resp.status_code == 200:
                return resp.json()
            error_text = resp.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"远端凭据刷新失败 ({resp.status_code}): {error_text}")

    def ask_stream(
        self,
        query: str,
        model: str = "experimental",
        mode: str = "concise",
        timeout: float | None = None,
        append_citations: bool = True,
        vertical: str | None = None,
        query_source: str | None = None,
        search_focus: str | None = None,
        sources: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """同步流式调用远端 OpenAI 兼容端点"""
        req_timeout = httpx.Timeout(timeout or self.timeout, connect=10.0)
        url = self._get_url("/v1/chat/completions")
        headers = self._build_headers()

        actual_model, parsed_vertical = parse_model_and_vertical(model, vertical)

        payload: dict[str, Any] = {
            "model": actual_model,
            "messages": [{"role": "user", "content": query}],
            "stream": True,
            "mode": mode,
            "append_citations": append_citations,
        }
        if parsed_vertical:
            payload["vertical"] = parsed_vertical
        if query_source:
            payload["query_source"] = query_source
        if search_focus:
            payload["search_focus"] = search_focus
        if sources is not None:
            payload["sources"] = sources

        accumulated_text = ""
        accumulated_reasoning = ""
        seen_sources: dict[str, dict[str, Any]] = {}

        with httpx.Client(timeout=req_timeout) as client:
            with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    err_msg = response.read().decode("utf-8", errors="ignore")
                    raise RuntimeError(f"远端 API 请求失败 ({response.status_code}): {err_msg}")

                for line in response.iter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            event = json.loads(data_str)
                        except Exception:
                            continue

                        choices = event.get("choices", [])
                        if not choices:
                            continue

                        delta = choices[0].get("delta", {})
                        delta_content = delta.get("content") or ""
                        delta_reasoning = delta.get("reasoning_content") or ""

                        if delta_content:
                            accumulated_text += delta_content
                        if delta_reasoning:
                            accumulated_reasoning += delta_reasoning

                        if "citations" in event and isinstance(event["citations"], list):
                            for s in event["citations"]:
                                url_s = s.get("url")
                                if url_s and url_s not in seen_sources:
                                    seen_sources[url_s] = s

                        yield {
                            "type": "delta",
                            "delta": delta_content,
                            "delta_reasoning": delta_reasoning,
                            "answer": accumulated_text,
                            "reasoning": accumulated_reasoning,
                            "sources": list(seen_sources.values()),
                            "display_model": model,
                            "raw_event": event,
                        }

    async def ask_stream_async(
        self,
        query: str,
        model: str = "experimental",
        mode: str = "concise",
        timeout: float | None = None,
        append_citations: bool = True,
        vertical: str | None = None,
        query_source: str | None = None,
        search_focus: str | None = None,
        sources: list[str] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """异步流式调用远端 OpenAI 兼容端点"""
        req_timeout = httpx.Timeout(timeout or self.timeout, connect=10.0)
        url = self._get_url("/v1/chat/completions")
        headers = self._build_headers()

        actual_model, parsed_vertical = parse_model_and_vertical(model, vertical)

        payload: dict[str, Any] = {
            "model": actual_model,
            "messages": [{"role": "user", "content": query}],
            "stream": True,
            "mode": mode,
            "append_citations": append_citations,
        }
        if parsed_vertical:
            payload["vertical"] = parsed_vertical
        if query_source:
            payload["query_source"] = query_source
        if search_focus:
            payload["search_focus"] = search_focus
        if sources is not None:
            payload["sources"] = sources

        accumulated_text = ""
        accumulated_reasoning = ""
        seen_sources: dict[str, dict[str, Any]] = {}

        async with httpx.AsyncClient(timeout=req_timeout) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    err_msg = (await response.aread()).decode("utf-8", errors="ignore")
                    raise RuntimeError(f"远端 API 请求失败 ({response.status_code}): {err_msg}")

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            event = json.loads(data_str)
                        except Exception:
                            continue

                        choices = event.get("choices", [])
                        if not choices:
                            continue

                        delta = choices[0].get("delta", {})
                        delta_content = delta.get("content") or ""
                        delta_reasoning = delta.get("reasoning_content") or ""

                        if delta_content:
                            accumulated_text += delta_content
                        if delta_reasoning:
                            accumulated_reasoning += delta_reasoning

                        if "citations" in event and isinstance(event["citations"], list):
                            for s in event["citations"]:
                                url_s = s.get("url")
                                if url_s and url_s not in seen_sources:
                                    seen_sources[url_s] = s

                        yield {
                            "type": "delta",
                            "delta": delta_content,
                            "delta_reasoning": delta_reasoning,
                            "answer": accumulated_text,
                            "reasoning": accumulated_reasoning,
                            "sources": list(seen_sources.values()),
                            "display_model": model,
                            "raw_event": event,
                        }

    def ask(
        self,
        query: str,
        model: str = "experimental",
        mode: str = "concise",
        timeout: float | None = None,
        vertical: str | None = None,
        query_source: str | None = None,
        search_focus: str | None = None,
        sources: list[str] | None = None,
    ) -> dict[str, Any]:
        """同步非流式调用远端端点"""
        req_timeout = httpx.Timeout(timeout or self.timeout, connect=10.0)
        url = self._get_url("/v1/chat/completions")
        headers = self._build_headers()

        actual_model, parsed_vertical = parse_model_and_vertical(model, vertical)

        payload: dict[str, Any] = {
            "model": actual_model,
            "messages": [{"role": "user", "content": query}],
            "stream": False,
            "mode": mode,
        }
        if parsed_vertical:
            payload["vertical"] = parsed_vertical
        if query_source:
            payload["query_source"] = query_source
        if search_focus:
            payload["search_focus"] = search_focus
        if sources is not None:
            payload["sources"] = sources

        with httpx.Client(timeout=req_timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                err_msg = resp.read().decode("utf-8", errors="ignore")
                raise RuntimeError(f"远端 API 请求失败 ({resp.status_code}): {err_msg}")
            data = resp.json()
            choices = data.get("choices", [])
            answer = choices[0]["message"]["content"] if choices else ""
            return {
                "query": query,
                "answer": answer,
                "sources": data.get("citations", []),
                "model": data.get("model", model),
                "raw_event": data,
            }

    async def ask_async(
        self,
        query: str,
        model: str = "experimental",
        mode: str = "concise",
        timeout: float | None = None,
        vertical: str | None = None,
        query_source: str | None = None,
        search_focus: str | None = None,
        sources: list[str] | None = None,
    ) -> dict[str, Any]:
        """异步非流式调用远端端点"""
        req_timeout = httpx.Timeout(timeout or self.timeout, connect=10.0)
        url = self._get_url("/v1/chat/completions")
        headers = self._build_headers()

        actual_model, parsed_vertical = parse_model_and_vertical(model, vertical)

        payload: dict[str, Any] = {
            "model": actual_model,
            "messages": [{"role": "user", "content": query}],
            "stream": False,
            "mode": mode,
        }
        if parsed_vertical:
            payload["vertical"] = parsed_vertical
        if query_source:
            payload["query_source"] = query_source
        if search_focus:
            payload["search_focus"] = search_focus
        if sources is not None:
            payload["sources"] = sources

        async with httpx.AsyncClient(timeout=req_timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                err_msg = (await resp.aread()).decode("utf-8", errors="ignore")
                raise RuntimeError(f"远端 API 请求失败 ({resp.status_code}): {err_msg}")
            data = resp.json()
            choices = data.get("choices", [])
            answer = choices[0]["message"]["content"] if choices else ""
            return {
                "query": query,
                "answer": answer,
                "sources": data.get("citations", []),
                "model": data.get("model", model),
                "raw_event": data,
            }


class PerplexityClient:
    """
    Perplexity 核心统一客户端 (支持透明切换 本地直接请求 / 远端网关请求)
    - 自动根据环境变量或本地配置判定是否启用 Remote 模式
    - 完整支持所有垂直搜索领域与模型 (Patents, Academic, Finance, Social, Health, Web 等)
    """

    def __init__(
        self,
        auth_manager: PerplexityAuthManager | None = None,
        remote_url: str | None = None,
        api_key: str | None = None,
    ):
        if auth_manager is not None or remote_url == "":
            self.is_remote = False
            self.remote_client = None
            self.auth_manager = auth_manager or PerplexityAuthManager()
            return

        target_remote_url = remote_url or get_remote_url()
        target_api_key = api_key or get_remote_api_key()

        if target_remote_url:
            self.is_remote = True
            self.remote_client = RemotePerplexityClient(
                remote_url=target_remote_url,
                api_key=target_api_key,
            )
            self.auth_manager = None
        else:
            self.is_remote = False
            self.remote_client = None
            self.auth_manager = PerplexityAuthManager()

    def _build_headers(
        self,
        request_id: str | None = None,
        vertical: str | None = None,
    ) -> dict[str, str]:
        token = self.auth_manager.get_valid_token()
        req_id = request_id or str(uuid.uuid4())

        cookies = [f"__Secure-next-auth.session-token={token}"]
        cf_clearance = getattr(self.auth_manager, "cf_clearance", None)
        if cf_clearance:
            cookies.append(f"cf_clearance={cf_clearance}")

        referer_url = "https://www.perplexity.ai/"
        if vertical and vertical != "web":
            referer_url = f"https://www.perplexity.ai/{vertical}"

        return {
            "User-Agent": APP_USER_AGENT,
            "X-App-ApiClient": "default",
            "X-App-ApiVersion": "2.18",
            "X-Perplexity-Request-Reason": "submit",
            "X-Request-ID": req_id,
            "Origin": "https://www.perplexity.ai",
            "Referer": referer_url,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Cookie": "; ".join(cookies),
        }

    def _build_payload(
        self,
        query: str,
        model: str = "experimental",
        mode: str = "concise",
        search_focus: str | None = None,
        sources: list[str] | None = None,
        vertical: str | None = None,
        query_source: str | None = None,
        canonical_page_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        actual_model, parsed_vertical = parse_model_and_vertical(model, vertical)
        resolved_model = resolve_model_name(actual_model)

        vert_cfg = resolve_vertical_config(
            vertical=parsed_vertical,
            sources=sources,
            search_focus=search_focus,
            query_source=query_source,
            canonical_page_context=canonical_page_context,
        )

        params: dict[str, Any] = {
            "query_str": query,
            "search_focus": vert_cfg["search_focus"],
            "mode": mode,
            "model_preference": resolved_model,
            "sources": vert_cfg["sources"],
            "query_source": vert_cfg["query_source"],
            "prompt_source": "user",
            "is_related_query": False,
            "is_sponsored": False,
            "is_incognito": False,
            "use_schematized_api": True,
            "send_back_text_in_streaming_api": False,
            "supported_block_use_cases": [
                "answer_modes",
                "media_items",
                "inline_entity_cards",
                "place_widgets",
                "finance_widgets",
                "sports_widgets",
                "news_widgets",
                "shopping_widgets",
                "jobs_widgets",
                "search_result_widgets",
                "inline_images",
                "inline_assets",
                "placeholder_cards",
                "diff_blocks",
                "entity_group_v2",
                "refinement_filters",
                "canvas_mode",
                "maps_preview",
                "answer_tabs",
                "price_comparison_widgets",
                "preserve_latex",
                "generic_onboarding_widgets",
                "in_context_suggestions",
                "pending_followups",
                "inline_claims",
                "unified_assets",
                "workflow_steps",
                "workflow_widgets",
                "navigation_results",
                "background_agents",
            ],
            "skip_search_enabled": True,
            "source": "default",
            "always_search_override": False,
            "override_no_search": False,
            "should_ask_for_mcp_tool_confirmation": False,
            "supports_tool_approval_modal": False,
            "force_enable_browser_agent": False,
            "is_local_browser_available": False,
            "is_local_browser_allowed": False,
            "version": "2.18",
        }

        if vert_cfg.get("canonical_page_context"):
            params["canonical_page_context"] = vert_cfg["canonical_page_context"]

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
        vertical: str | None = None,
        query_source: str | None = None,
        search_focus: str | None = None,
        sources: list[str] | None = None,
        canonical_page_context: dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        原生异步流式请求 Perplexity API，实时产出：
        1. 搜索与思考进度 (type="progress")
        2. 增量文本 (type="delta")
        3. 完整文本快照与引用源 (sources)
        """
        if self.is_remote and self.remote_client:
            async for item in self.remote_client.ask_stream_async(
                query,
                model=model,
                mode=mode,
                timeout=timeout,
                vertical=vertical,
                query_source=query_source,
                search_focus=search_focus,
                sources=sources,
            ):
                yield item
            return

        actual_model, parsed_vertical = parse_model_and_vertical(model, vertical)
        headers = self._build_headers(vertical=parsed_vertical)
        payload = self._build_payload(
            query,
            model=actual_model,
            mode=mode,
            search_focus=search_focus,
            sources=sources,
            vertical=parsed_vertical,
            query_source=query_source,
            canonical_page_context=canonical_page_context,
        )
        resolved_model = payload["params"]["model_preference"]

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST", ASK_ENDPOINT, headers=headers, json=payload
            ) as response:
                if response.status_code == 401:
                    # Token 过期，强制刷新并重试一次
                    self.auth_manager.refresh(force=True)
                    headers = self._build_headers(vertical=parsed_vertical)
                    async for item in self.ask_async_stream(
                        query,
                        model=model,
                        mode=mode,
                        timeout=timeout,
                        vertical=vertical,
                        query_source=query_source,
                        search_focus=search_focus,
                        sources=sources,
                        canonical_page_context=canonical_page_context,
                    ):
                        yield item
                    return

                if response.status_code != 200:
                    error_bytes = await response.aread()
                    error_text = error_bytes.decode("utf-8", errors="ignore")
                    raise RuntimeError(
                        f"Perplexity API 请求失败 ({response.status_code}): {error_text}"
                    )

                accumulated_text = ""
                seen_sources: dict[str, dict[str, Any]] = {}
                display_model = resolved_model

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

                        delta, accumulated_text, has_new_sources = extract_event_payload(
                            event=event,
                            accumulated_text=accumulated_text,
                            seen_sources=seen_sources,
                        )

                        # 如果当前事件产出了增量文本或新引用源，向上游派发
                        if delta or has_new_sources:
                            yield {
                                "type": "delta",
                                "delta": delta,
                                "answer": accumulated_text,
                                "sources": list(seen_sources.values()),
                                "display_model": display_model,
                                "vertical": parsed_vertical or "web",
                                "raw_event": event,
                            }

    def ask_stream(
        self,
        query: str,
        model: str = "experimental",
        mode: str = "concise",
        timeout: float = 60.0,
        vertical: str | None = None,
        query_source: str | None = None,
        search_focus: str | None = None,
        sources: list[str] | None = None,
        canonical_page_context: dict[str, Any] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """同步流式请求 Perplexity API"""
        if self.is_remote and self.remote_client:
            yield from self.remote_client.ask_stream(
                query,
                model=model,
                mode=mode,
                timeout=timeout,
                vertical=vertical,
                query_source=query_source,
                search_focus=search_focus,
                sources=sources,
            )
            return

        actual_model, parsed_vertical = parse_model_and_vertical(model, vertical)
        headers = self._build_headers(vertical=parsed_vertical)
        payload = self._build_payload(
            query,
            model=actual_model,
            mode=mode,
            search_focus=search_focus,
            sources=sources,
            vertical=parsed_vertical,
            query_source=query_source,
            canonical_page_context=canonical_page_context,
        )
        resolved_model = payload["params"]["model_preference"]

        with httpx.Client(timeout=timeout) as client:
            with client.stream("POST", ASK_ENDPOINT, headers=headers, json=payload) as response:
                if response.status_code == 401:
                    self.auth_manager.refresh(force=True)
                    headers = self._build_headers(vertical=parsed_vertical)
                    yield from self.ask_stream(
                        query,
                        model=model,
                        mode=mode,
                        timeout=timeout,
                        vertical=vertical,
                        query_source=query_source,
                        search_focus=search_focus,
                        sources=sources,
                        canonical_page_context=canonical_page_context,
                    )
                    return

                if response.status_code != 200:
                    error_text = response.read().decode("utf-8", errors="ignore")
                    raise RuntimeError(
                        f"Perplexity API 请求失败 ({response.status_code}): {error_text}"
                    )

                accumulated_text = ""
                seen_sources: dict[str, dict[str, Any]] = {}
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

                        delta, accumulated_text, has_new_sources = extract_event_payload(
                            event=event,
                            accumulated_text=accumulated_text,
                            seen_sources=seen_sources,
                        )

                        if delta or has_new_sources:
                            yield {
                                "type": "delta",
                                "delta": delta,
                                "answer": accumulated_text,
                                "sources": list(seen_sources.values()),
                                "display_model": display_model,
                                "vertical": parsed_vertical or "web",
                                "raw_event": event,
                            }

    async def ask_async(
        self,
        query: str,
        model: str = "experimental",
        mode: str = "concise",
        timeout: float = 60.0,
        vertical: str | None = None,
        query_source: str | None = None,
        search_focus: str | None = None,
        sources: list[str] | None = None,
        canonical_page_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """异步非流式请求封装"""
        if self.is_remote and self.remote_client:
            return await self.remote_client.ask_async(
                query,
                model=model,
                mode=mode,
                timeout=timeout,
                vertical=vertical,
                query_source=query_source,
                search_focus=search_focus,
                sources=sources,
            )

        final_answer = ""
        sources_list: list[dict[str, Any]] = []
        display_model = model
        raw_event = {}

        async for chunk in self.ask_async_stream(
            query,
            model=model,
            mode=mode,
            timeout=timeout,
            vertical=vertical,
            query_source=query_source,
            search_focus=search_focus,
            sources=sources,
            canonical_page_context=canonical_page_context,
        ):
            if chunk.get("answer"):
                final_answer = chunk["answer"]
            if chunk.get("sources"):
                sources_list = chunk["sources"]
            if chunk.get("display_model"):
                display_model = chunk["display_model"]
            raw_event = chunk.get("raw_event", {})

        return {
            "query": query,
            "answer": final_answer,
            "sources": sources_list,
            "model": display_model,
            "vertical": vertical or "web",
            "raw_event": raw_event,
        }

    def ask(
        self,
        query: str,
        model: str = "experimental",
        mode: str = "concise",
        timeout: float = 60.0,
        vertical: str | None = None,
        query_source: str | None = None,
        search_focus: str | None = None,
        sources: list[str] | None = None,
        canonical_page_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """同步非流式完整回答提取"""
        final_answer = ""
        sources_list: list[dict[str, Any]] = []
        if self.is_remote and self.remote_client:
            return self.remote_client.ask(
                query,
                model=model,
                mode=mode,
                timeout=timeout,
                vertical=vertical,
                query_source=query_source,
                search_focus=search_focus,
                sources=sources,
            )

        display_model = model
        raw_event = {}

        for chunk in self.ask_stream(
            query,
            model=model,
            mode=mode,
            timeout=timeout,
            vertical=vertical,
            query_source=query_source,
            search_focus=search_focus,
            sources=sources,
            canonical_page_context=canonical_page_context,
        ):
            if chunk.get("answer"):
                final_answer = chunk["answer"]
            if chunk.get("sources"):
                sources_list = chunk["sources"]
            if chunk.get("display_model"):
                display_model = chunk["display_model"]
            raw_event = chunk.get("raw_event", {})

        return {
            "query": query,
            "answer": final_answer,
            "sources": sources_list,
            "model": display_model,
            "vertical": vertical or "web",
            "raw_event": raw_event,
        }
