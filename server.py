"""
Perplexity Search2API HTTP Server (FastAPI)
- 完全兼容 OpenAI /v1/chat/completions 接口标准 (基于 OpenAI 官方 SDK 规范与数据结构)
- 完整支持专业垂直搜索模型与领域 (Search Verticals & Focus Domains):
  * Web Search (全网综合搜索)
  * Patents (https://www.perplexity.ai/patents 专利检索、IPC/CPC分类与现有技术分析)
  * Academic (https://www.perplexity.ai/academic 学术论文、arXiv、PubMed、JSTOR、DOI文献)
  * Finance (https://www.perplexity.ai/finance 机构级金融市场、SEC财报、业绩纪要与分析师目标价)
  * Social (社交网络、Reddit、Twitter/X 社区真实讨论与口碑)
  * Health / Clinical (健康与临床医学)
  * Writing / Wolfram / YouTube / Reddit 经典 Focus 模式
- 支持复合模型名称语法 (如 patents:claude-3-7-sonnet, academic:sonar, finance:gpt-5.6)
- 极致优化流式响应首字延迟 (TTFT) 与思考链实时呈现 (delta.reasoning_content 0.2s 极速上屏)
- 平滑流式 Token 节流与微步调度 (消除 Claude / GLM 等大模型一次性倾泻卡顿，打造丝滑打字机体验)
- 深度 Markdown 引用超链接 (正文中的 [1], [2] 自动转为带标题预览的 [[1]](url "title") 可点击链接)
- 文末结构化引用来源列表 (按序号排版可点击 Markdown 链接)
- 自动将多轮历史 messages 格式化为深度搜索上下文
- 完整支持全系列大模型 (Claude 3.7 Sonnet, GPT-5.6, Grok 4.6, Gemini 3.7, GLM 5.3, Kimi K3 等)
- 提供 /v1/models 与 /v1/models/{model} 模型列表
- 提供 /verticals 垂直搜索领域列表
- 提供 /search 结构化检索端点与 /auth/* 凭证管理端点
"""

import asyncio
import json
import os
import re
import time
import uuid
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionMessage,
)
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_chunk import (
    Choice as ChunkChoice,
)
from openai.types.chat.chat_completion_chunk import (
    ChoiceDelta,
)
from openai.types.completion_usage import CompletionUsage
from pydantic import BaseModel, Field

from perplexity_auth import PerplexityAuthManager, load_credentials
from perplexity_client import (
    MODEL_ALIASES,
    SEARCH_VERTICALS,
    VERTICAL_ALIASES,
    PerplexityClient,
    parse_model_and_vertical,
    resolve_model_name,
    resolve_vertical_config,
)

app = FastAPI(
    title="Perplexity Search2API Gateway",
    description="将 Perplexity 深度联网搜索与全系列前沿大模型无缝转换为标准 OpenAI /v1 接口，支持 Patents/Academic/Finance 等专业搜索垂直模型",
    version="2.4.0",
)

# 允许跨域请求 (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 可选 API Key 保护 (环境变量: PERPLEXITY_PROXY_KEY 或 API_KEY)
PROXY_API_KEY = os.getenv("PERPLEXITY_PROXY_KEY") or os.getenv("API_KEY")
DEFAULT_MODE = os.getenv("PERPLEXITY_DEFAULT_MODE", "concise")


# =====================================================================
# 身份校验 (Authentication)
# =====================================================================


async def verify_auth(request: Request):
    """校验请求携带的 Authorization: Bearer <API_KEY> 或 api-key 请求头"""
    import server

    required_key = (
        getattr(server, "PROXY_API_KEY", None)
        or os.getenv("PERPLEXITY_PROXY_KEY")
        or os.getenv("API_KEY")
    )
    if not required_key:
        return True

    auth_header = request.headers.get("Authorization")
    api_key_header = request.headers.get("api-key")

    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif api_key_header:
        token = api_key_header.strip()

    if not token or token != required_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: 无效的 API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True


# =====================================================================
# Markdown 引用超链接与格式化处理
# =====================================================================


def linkify_citations(text: str, sources: list[dict[str, Any]]) -> str:
    """
    将正文中所有未链接化的引用标记 [1], [2] 转换为标准的 Markdown 行内超链接：
    [[1]](https://url "文章标题/预览")
    在客户端渲染时：
    1. 显示为带方括号的 [1]、[2] 超链接
    2. 鼠标悬停在 [1] 上时显示来源标题 Tooltip
    3. 点击 [1] 可直接在浏览器中跳转打开来源页面
    """
    if not sources or not text:
        return text

    def replace_citation(match):
        idx_str = match.group(1)
        try:
            idx = int(idx_str)
            if 1 <= idx <= len(sources):
                s = sources[idx - 1]
                url = s.get("url", "")
                name = (
                    (s.get("name") or s.get("title") or "网页来源")
                    .replace('"', "'")
                    .replace("\n", " ")
                    .strip()
                )
                if len(name) > 60:
                    name = name[:57] + "..."
                if url:
                    return f'[[{idx}]]({url} "{name}")'
        except ValueError:
            pass
        return match.group(0)

    return re.sub(r"(?<!\[)\[(\d+)\](?!\()", replace_citation, text)


class StreamingCitationLinker:
    """
    流式传输中的引用超链接实时转换器：
    处理 Token 分片 (例如 '[' 与 '1]' 分开推送)，并将实时出现的 [1] 转为 [[1]](url "title")
    """

    def __init__(self, sources_getter):
        self.sources_getter = sources_getter
        self.buffer = ""

    def process(self, chunk_text: str) -> str:
        if not chunk_text:
            return ""
        self.buffer += chunk_text

        sources = self.sources_getter()
        if not sources:
            if "[" in self.buffer:
                last_bracket = self.buffer.rfind("[")
                if len(self.buffer) - last_bracket <= 6:
                    out = self.buffer[:last_bracket]
                    self.buffer = self.buffer[last_bracket:]
                    return out
            out = self.buffer
            self.buffer = ""
            return out

        def replace_fn(match):
            idx_str = match.group(1)
            try:
                idx = int(idx_str)
                if 1 <= idx <= len(sources):
                    s = sources[idx - 1]
                    url = s.get("url", "")
                    name = (
                        (s.get("name") or s.get("title") or "网页来源")
                        .replace('"', "'")
                        .replace("\n", " ")
                        .strip()
                    )
                    if len(name) > 60:
                        name = name[:57] + "..."
                    if url:
                        return f'[[{idx}]]({url} "{name}")'
            except ValueError:
                pass
            return match.group(0)

        converted = re.sub(r"(?<!\[)\[(\d+)\](?!\()", replace_fn, self.buffer)

        if "[" in converted:
            last_bracket = converted.rfind("[")
            if (
                len(converted) - last_bracket <= 6
                and "]" not in converted[last_bracket:]
            ):
                out = converted[:last_bracket]
                self.buffer = converted[last_bracket:]
                return out

        self.buffer = ""
        return converted

    def flush(self) -> str:
        sources = self.sources_getter()
        out = linkify_citations(self.buffer, sources)
        self.buffer = ""
        return out


def format_citations_markdown(text: str, sources: list[dict[str, Any]]) -> str:
    """在回答末尾按序号排版结构化引用来源列表"""
    if not sources:
        return ""
    if "### 📚 参考来源与链接" in text:
        return ""

    lines = ["\n\n### 📚 参考来源与链接\n"]
    for idx, s in enumerate(sources, 1):
        url = s.get("url", "")
        name = (s.get("name") or s.get("title") or "网页来源").strip()
        snippet = s.get("snippet", "").strip()
        if not url:
            continue

        clean_name = name.replace("\n", " ").replace("[", "").replace("]", "")
        if snippet:
            clean_snippet = snippet.replace("\n", " ")
            if len(clean_snippet) > 90:
                clean_snippet = clean_snippet[:87] + "..."
            lines.append(f"{idx}. [{clean_name}]({url}) — *{clean_snippet}*")
        else:
            lines.append(f"{idx}. [{clean_name}]({url})")

    return "\n".join(lines)


# =====================================================================
# Pydantic 数据模型 (OpenAI API Schema)
# =====================================================================


class ChatMessage(BaseModel):
    role: str
    content: Any = ""
    name: str | None = None


class StreamOptions(BaseModel):
    include_usage: bool | None = False


class ExtendedChoiceDelta(ChoiceDelta):
    reasoning_content: str | None = None


class ExtendedChunkChoice(ChunkChoice):
    delta: ExtendedChoiceDelta


class ExtendedChatCompletionChunk(ChatCompletionChunk):
    choices: list[ExtendedChunkChoice] = Field(default_factory=list)


class ChatCompletionRequest(BaseModel):
    model: str = "experimental"
    messages: list[ChatMessage]
    stream: bool | None = False
    mode: str | None = None
    vertical: str | None = None
    query_source: str | None = None
    search_focus: str | None = None
    sources: list[str] | None = None
    stream_options: StreamOptions | None = None
    append_citations: bool | None = True
    linkify_in_text: bool | None = True
    enable_reasoning: bool | None = True
    smooth_stream: bool | None = True
    throttle_step: int | None = 6
    throttle_delay: float | None = 0.015


class SearchRequest(BaseModel):
    query: str
    model: str | None = "experimental"
    mode: str | None = "concise"
    vertical: str | None = None
    search_focus: str | None = None
    sources: list[str] | None = None


# =====================================================================
# 多轮对话格式化与上下文组装
# =====================================================================


def format_messages_to_prompt(messages: list[ChatMessage]) -> str:
    """将 messages 列表格式化为深度搜索上下文 Prompt"""
    if not messages:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "message": "messages 不能为空",
                    "type": "invalid_request_error",
                }
            },
        )

    if len(messages) == 1:
        c = messages[0].content
        return c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)

    lines = []
    for msg in messages:
        role = msg.role.lower()
        content = (
            msg.content
            if isinstance(msg.content, str)
            else json.dumps(msg.content, ensure_ascii=False)
        )
        content = content.strip()
        if not content:
            continue

        if role in ("system", "developer"):
            lines.append(f"[系统要求]: {content}")
        elif role in ("user", "human"):
            lines.append(f"[用户提问]: {content}")
        elif role in ("assistant", "ai"):
            lines.append(f"[AI回答]: {content}")
        else:
            lines.append(f"[{role}]: {content}")

    return "\n\n".join(lines)


def estimate_tokens(text: str) -> int:
    """快速估算文本对应的 Token 数量"""
    if not text:
        return 0
    cjk_count = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    other_count = len(text) - cjk_count
    return max(1, int(cjk_count / 1.5 + other_count / 4))


# =====================================================================
# OpenAI 兼容流式生成器 (Streaming SSE Generator)
# =====================================================================


async def sse_chat_stream_generator(
    client: PerplexityClient,
    query: str,
    requested_model: str,
    mode: str,
    include_usage: bool = False,
    prompt_tokens: int = 0,
    append_citations: bool = True,
    linkify_in_text: bool = True,
    enable_reasoning: bool = True,
    smooth_stream: bool = True,
    throttle_step: int = 6,
    throttle_delay: float = 0.015,
    vertical: str | None = None,
    query_source: str | None = None,
    search_focus: str | None = None,
    sources: list[str] | None = None,
):
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created_time = int(time.time())
    actual_model, parsed_vertical = parse_model_and_vertical(requested_model, vertical)
    effective_vertical = parsed_vertical or "web"

    # 1. 角色初始首帧：发送 role="assistant"
    init_chunk = ExtendedChatCompletionChunk(
        id=completion_id,
        choices=[
            ExtendedChunkChoice(
                index=0,
                delta=ExtendedChoiceDelta(role="assistant"),
                finish_reason=None,
            )
        ],
        created=created_time,
        model=actual_model,
        object="chat.completion.chunk",
        system_fingerprint="fp_perplexity",
    )
    yield f"data: {init_chunk.model_dump_json(exclude_none=True)}\n\n"

    accumulated_content = ""
    latest_sources: list[dict[str, Any]] = []

    linker = (
        StreamingCitationLinker(lambda: latest_sources)
        if linkify_in_text
        else None
    )

    try:
        async for chunk in client.ask_async_stream(
            query,
            model=actual_model,
            mode=mode,
            vertical=effective_vertical,
            query_source=query_source,
            search_focus=search_focus,
            sources=sources,
        ):
            if chunk.get("display_model"):
                actual_model = chunk["display_model"]

            if chunk.get("sources"):
                latest_sources = chunk["sources"]

            # 2. 思考链 (Reasoning Content / Thinking)
            if enable_reasoning:
                delta_reasoning = chunk.get("delta_reasoning")
                if delta_reasoning:
                    chunk_resp = ExtendedChatCompletionChunk(
                        id=completion_id,
                        choices=[
                            ExtendedChunkChoice(
                                index=0,
                                delta=ExtendedChoiceDelta(
                                    reasoning_content=delta_reasoning
                                ),
                                finish_reason=None,
                            )
                        ],
                        created=created_time,
                        model=actual_model,
                        object="chat.completion.chunk",
                        system_fingerprint="fp_perplexity",
                    )
                    yield f"data: {chunk_resp.model_dump_json(exclude_none=True)}\n\n"

            # 3. 正文回答增量 (Content Delta)
            delta_text = chunk.get("delta", "")
            if delta_text:
                if linker:
                    delta_text = linker.process(delta_text)

                if delta_text:
                    accumulated_content += delta_text

                    # 智能 Token 节流与微步打字机平滑推送
                    if (
                        smooth_stream
                        and throttle_step > 0
                        and len(delta_text) > throttle_step * 2
                    ):
                        step = throttle_step
                        for i in range(0, len(delta_text), step):
                            sub_delta = delta_text[i : i + step]
                            sub_chunk = ExtendedChatCompletionChunk(
                                id=completion_id,
                                choices=[
                                    ExtendedChunkChoice(
                                        index=0,
                                        delta=ExtendedChoiceDelta(
                                            content=sub_delta
                                        ),
                                        finish_reason=None,
                                    )
                                ],
                                created=created_time,
                                model=actual_model,
                                object="chat.completion.chunk",
                                system_fingerprint="fp_perplexity",
                            )
                            yield f"data: {sub_chunk.model_dump_json(exclude_none=True)}\n\n"
                            if throttle_delay > 0:
                                await asyncio.sleep(throttle_delay)
                    else:
                        chunk_resp = ExtendedChatCompletionChunk(
                            id=completion_id,
                            choices=[
                                ExtendedChunkChoice(
                                    index=0,
                                    delta=ExtendedChoiceDelta(
                                        content=delta_text
                                    ),
                                    finish_reason=None,
                                )
                            ],
                            created=created_time,
                            model=actual_model,
                            object="chat.completion.chunk",
                            system_fingerprint="fp_perplexity",
                        )
                        yield f"data: {chunk_resp.model_dump_json(exclude_none=True)}\n\n"

        # 刷新超链接缓冲区
        if linker:
            flush_text = linker.flush()
            if flush_text:
                accumulated_content += flush_text
                flush_chunk = ExtendedChatCompletionChunk(
                    id=completion_id,
                    choices=[
                        ExtendedChunkChoice(
                            index=0,
                            delta=ExtendedChoiceDelta(content=flush_text),
                            finish_reason=None,
                        )
                    ],
                    created=created_time,
                    model=actual_model,
                    object="chat.completion.chunk",
                    system_fingerprint="fp_perplexity",
                )
                yield f"data: {flush_chunk.model_dump_json(exclude_none=True)}\n\n"

        # 4. 引用来源与参考链接帧 (若配置开启且存在外部引用)
        if append_citations and latest_sources:
            citations_md = format_citations_markdown(
                accumulated_content, latest_sources
            )
            if citations_md:
                accumulated_content += citations_md
                citations_chunk = ExtendedChatCompletionChunk(
                    id=completion_id,
                    choices=[
                        ExtendedChunkChoice(
                            index=0,
                            delta=ExtendedChoiceDelta(content=citations_md),
                            finish_reason=None,
                        )
                    ],
                    created=created_time,
                    model=actual_model,
                    object="chat.completion.chunk",
                    system_fingerprint="fp_perplexity",
                )
                yield f"data: {citations_chunk.model_dump_json(exclude_none=True)}\n\n"

        # 5. 终态帧：finish_reason: "stop"
        stop_chunk = ExtendedChatCompletionChunk(
            id=completion_id,
            choices=[
                ExtendedChunkChoice(
                    index=0,
                    delta=ExtendedChoiceDelta(),
                    finish_reason="stop",
                )
            ],
            created=created_time,
            model=actual_model,
            object="chat.completion.chunk",
            system_fingerprint="fp_perplexity",
        )
        yield f"data: {stop_chunk.model_dump_json(exclude_none=True)}\n\n"

        # 6. Usage 统计帧 (若客户端开启 include_usage)
        completion_tokens = estimate_tokens(accumulated_content)
        if include_usage:
            usage_chunk = ExtendedChatCompletionChunk(
                id=completion_id,
                choices=[],
                created=created_time,
                model=actual_model,
                object="chat.completion.chunk",
                system_fingerprint="fp_perplexity",
                usage=CompletionUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                ),
            )
            yield f"data: {usage_chunk.model_dump_json(exclude_none=True)}\n\n"

    except Exception as e:
        err_payload = {
            "error": {
                "message": str(e),
                "type": "server_error",
                "code": "stream_error",
            }
        }
        yield f"data: {json.dumps(err_payload, ensure_ascii=False)}\n\n"
    finally:
        yield "data: [DONE]\n\n"


# =====================================================================
# API 路由 (Endpoints)
# =====================================================================


@app.get("/")
async def root():
    """服务根路径状态探针"""
    return {
        "service": "Perplexity Search2API",
        "name": "Perplexity Search2API Gateway",
        "status": "online",
        "version": "2.4.0",
        "features": {
            "openai_compatible": "/v1/chat/completions",
            "models_endpoint": "/v1/models",
            "verticals_endpoint": "/verticals",
            "search_endpoint": "/search",
            "patents_search": "https://www.perplexity.ai/patents (patents:...)",
            "academic_search": "https://www.perplexity.ai/academic (academic:...)",
            "finance_search": "https://www.perplexity.ai/finance (finance:...)",
        },
        "endpoints": {
            "chat": "/v1/chat/completions",
            "models": "/v1/models",
            "verticals": "/verticals",
            "search": "/search",
            "auth_info": "/auth/info",
        },
    }


@app.get("/health")
async def health():
    """健康检查端点"""
    return {"status": "ok", "timestamp": int(time.time())}


@app.get("/verticals")
async def get_verticals():
    """获取支持的所有专业搜索领域与垂直模型列表"""
    return {
        "data": list(SEARCH_VERTICALS.values()),
        "aliases": VERTICAL_ALIASES,
    }


@app.get("/v1/models")
async def list_models(user=Depends(verify_auth)):
    """返回标准 OpenAI 格式模型列表 (包含全系列大模型与垂直搜索模型)"""
    created_time = 1735689600  # 2025-01-01
    model_ids = sorted(list(MODEL_ALIASES.keys()))

    # 包含独立垂直领域模型与常用复合模型
    vertical_ids = [
        "patents",
        "academic",
        "finance",
        "social",
        "health",
        "writing",
        "wolfram",
        "youtube",
        "reddit",
    ]
    compound_samples = [
        "patents:claude-3-7-sonnet",
        "patents:sonar",
        "patents:gpt-5.6",
        "academic:claude-3-7-sonnet",
        "academic:sonar",
        "academic:gpt-5.6",
        "finance:claude-3-7-sonnet",
        "finance:sonar",
        "finance:gpt-5.6",
        "social:sonar",
    ]

    all_ids = sorted(list(set(model_ids + vertical_ids + compound_samples)))

    data = [
        {
            "id": m_id,
            "object": "model",
            "created": created_time,
            "owned_by": "perplexity",
            "permission": [],
            "root": m_id,
            "parent": None,
        }
        for m_id in all_ids
    ]
    return {"object": "list", "data": data}


@app.get("/v1/models/{model_id}")
async def get_model(model_id: str, user=Depends(verify_auth)):
    """获取单个模型详情"""
    norm = model_id.strip().lower()
    actual_model, parsed_vert = parse_model_and_vertical(norm)
    if (
        norm in MODEL_ALIASES
        or norm in VERTICAL_ALIASES
        or parsed_vert is not None
        or actual_model in MODEL_ALIASES
    ):
        return {
            "id": model_id,
            "object": "model",
            "created": 1735689600,
            "owned_by": "perplexity",
        }
    raise HTTPException(
        status_code=404,
        detail={"error": f"Model '{model_id}' not found"},
    )


@app.post("/v1/chat/completions")
async def chat_completions(
    req: ChatCompletionRequest,
    raw_request: Request,
    user=Depends(verify_auth),
):
    """
    OpenAI 官方兼容接口 /v1/chat/completions
    支持:
    1. stream=True 实时 SSE 流式输出与思考链 (reasoning_content)
    2. stream=False 一次性完整返回
    3. 支持垂直搜索模式 (Patents, Academic, Finance, Social, Health 等)
    4. 自动解析模型名中的垂直前缀 (如 academic:sonar, patents:claude-3-7-sonnet)
    """
    prompt_query = format_messages_to_prompt(req.messages)
    effective_mode = req.mode or DEFAULT_MODE
    prompt_tokens = estimate_tokens(prompt_query)

    # 优先从 Header 或 Body 解析垂直搜索领域
    header_vertical = raw_request.headers.get("X-Perplexity-Vertical")
    explicit_vertical = req.vertical or header_vertical
    actual_model, resolved_vertical = parse_model_and_vertical(
        req.model, explicit_vertical=explicit_vertical
    )

    client = PerplexityClient()

    # 流式调用模式 (Streaming SSE)
    if req.stream:
        include_usage = bool(
            req.stream_options and req.stream_options.include_usage
        )
        generator = sse_chat_stream_generator(
            client=client,
            query=prompt_query,
            requested_model=actual_model,
            mode=effective_mode,
            include_usage=include_usage,
            prompt_tokens=prompt_tokens,
            append_citations=bool(req.append_citations),
            linkify_in_text=bool(req.linkify_in_text),
            enable_reasoning=bool(req.enable_reasoning),
            smooth_stream=bool(req.smooth_stream),
            throttle_step=req.throttle_step or 6,
            throttle_delay=req.throttle_delay or 0.015,
            vertical=resolved_vertical,
            query_source=req.query_source,
            search_focus=req.search_focus,
            sources=req.sources,
        )
        return StreamingResponse(
            generator,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Content-Type": "text/event-stream; charset=utf-8",
                "X-Perplexity-Vertical": resolved_vertical or "web",
            },
        )

    # 非流式调用模式 (Non-Streaming)
    try:
        result = client.ask(
            query=prompt_query,
            model=actual_model,
            mode=effective_mode,
            vertical=resolved_vertical,
            query_source=req.query_source,
            search_focus=req.search_focus,
            sources=req.sources,
        )

        content = result.get("answer", "")
        sources = result.get("sources", [])

        # 正文中的 [1] 转换为带悬停标题的超链接 [[1]](url "title")
        if req.linkify_in_text and sources:
            content = linkify_citations(content, sources)

        # 追加末尾参考链接列表
        if req.append_citations and sources:
            citations_md = format_citations_markdown(content, sources)
            if citations_md:
                content = content + citations_md

        completion_tokens = estimate_tokens(content)
        total_tokens = prompt_tokens + completion_tokens

        # 使用 OpenAI SDK 标准 ChatCompletion 模型构建响应
        completion = ChatCompletion(
            id=f"chatcmpl-{uuid.uuid4().hex}",
            choices=[
                Choice(
                    index=0,
                    message=ChatCompletionMessage(
                        role="assistant",
                        content=content,
                    ),
                    finish_reason="stop",
                )
            ],
            created=int(time.time()),
            model=result.get("model") or req.model,
            object="chat.completion",
            system_fingerprint="fp_perplexity",
            usage=CompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            ),
        )

        resp_dict = completion.model_dump(exclude_none=True)
        if sources:
            resp_dict["citations"] = sources
        resp_dict["vertical"] = resolved_vertical or "web"

        return JSONResponse(
            resp_dict,
            headers={"X-Perplexity-Vertical": resolved_vertical or "web"},
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "message": f"Perplexity 查询失败: {str(e)}",
                    "type": "api_error",
                    "code": "perplexity_internal_error",
                }
            },
        )


@app.api_route("/search", methods=["GET", "POST"])
async def search_endpoint(
    request: Request,
    q: str | None = Query(None, description="搜索关键词"),
    query: str | None = Query(None, description="搜索关键词"),
    model: str = Query("experimental", description="大模型名称或别名"),
    mode: str = Query("concise", description="搜索模式 (concise / copilot)"),
    vertical: str | None = Query(
        None,
        description="搜索垂直领域/模型 (web, patents, academic, finance, social, health 等)",
    ),
    focus: str | None = Query(None, description="搜索焦点 (Focus)"),
    user=Depends(verify_auth),
):
    """
    通用结构化搜索端点，支持直接返回 Markdown 答案、引用来源列表及垂直领域元数据
    """
    search_q = q or query
    req_model = model
    req_mode = mode
    req_vertical = vertical or focus
    req_sources = None

    if request.method == "POST":
        try:
            body = await request.json()
            search_q = body.get("query") or body.get("q") or search_q
            req_model = body.get("model") or req_model
            req_mode = body.get("mode") or req_mode
            req_vertical = (
                body.get("vertical")
                or body.get("focus")
                or body.get("search_focus")
                or req_vertical
            )
            req_sources = body.get("sources")
        except Exception:
            pass

    if not search_q or not search_q.strip():
        raise HTTPException(status_code=400, detail="query 参数不能为空")

    actual_model, parsed_vertical = parse_model_and_vertical(
        req_model, explicit_vertical=req_vertical
    )

    client = PerplexityClient()
    try:
        res = client.ask(
            search_q,
            model=actual_model,
            mode=req_mode,
            vertical=parsed_vertical,
            sources=req_sources,
        )
        return {
            "query": search_q,
            "answer": res.get("answer", ""),
            "sources": res.get("sources", []),
            "model": res.get("model", actual_model),
            "vertical": parsed_vertical or "web",
            "timestamp": int(time.time()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================================
# 凭据管理端点 (Auth Endpoints)
# =====================================================================


@app.get("/auth/info")
async def auth_info(user=Depends(verify_auth)):
    """查看当前服务端配置的凭据与账号状态"""
    creds = load_credentials()
    if not creds:
        raise HTTPException(
            status_code=404, detail="未找到任何凭证，请先登录提取"
        )
    return creds


@app.post("/auth/refresh")
async def auth_refresh(user=Depends(verify_auth)):
    """手动执行凭据滚动刷新 (NextAuth 延长 30 天)"""
    manager = PerplexityAuthManager()
    try:
        res = manager.refresh(force=True)
        return {"status": "refreshed", "data": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刷新失败: {e}")


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("server:app", host=host, port=port, reload=True)
