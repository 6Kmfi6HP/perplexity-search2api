"""
Perplexity Search2API HTTP Server (FastAPI)
- 完全兼容 OpenAI /v1/chat/completions 接口标准 (基于 OpenAI 官方 SDK 规范与数据结构)
- 极致优化流式响应首字延迟 (TTFT) 与思考链实时呈现 (delta.reasoning_content 0.2s 极速上屏)
- 平滑流式 Token 节流与微步调度 (消除 Claude / GLM 等大模型一次性倾泻卡顿，打造丝滑打字机体验)
- 深度 Markdown 引用超链接 (正文中的 [1], [2] 自动转为带标题预览的 [[1]](url "title") 可点击链接)
- 文末结构化引用来源列表 (按序号排版可点击 Markdown 链接)
- 自动将多轮历史 messages 格式化为深度搜索上下文
- 完整支持全系列大模型 (Claude 3.7 Sonnet, GPT-5.6, Grok 4.6, Gemini 3.7, GLM 5.3, Kimi K3 等)
- 提供 /v1/models 与 /v1/models/{model} 模型列表
- 提供 /search 结构化检索端点与 /auth/* 凭证管理端点
"""

import asyncio
import json
import os
import re
import time
import uuid
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
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
from openai.types.model import Model
from pydantic import BaseModel, Field

from perplexity_auth import PerplexityAuthManager, load_credentials
from perplexity_client import MODEL_ALIASES, PerplexityClient, resolve_model_name

app = FastAPI(
    title="Perplexity Search2API Gateway",
    description="将 Perplexity 深度联网搜索与全系列前沿大模型无缝转换为标准 OpenAI /v1 接口",
    version="2.3.0",
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
# Pydantic 请求与扩展响应模型
# =====================================================================

class ChatMessage(BaseModel):
    role: str = "user"  # "system", "user", "assistant", "developer", "tool"
    content: Any = ""
    name: str | None = None


class StreamOptions(BaseModel):
    include_usage: bool = False


class ChatCompletionRequest(BaseModel):
    model: str = "experimental"
    messages: list[ChatMessage] = Field(..., min_length=1)
    stream: bool = False
    stream_options: StreamOptions | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    max_completion_tokens: int | None = None
    # Perplexity 优化扩展字段
    mode: str = Field(default_factory=lambda: os.getenv("PERPLEXITY_DEFAULT_MODE", "concise"), description="搜索模式：concise (快速) 或 copilot (深度)")
    search_focus: str = "internet"  # "internet", "scholar", "writing"
    append_citations: bool = True  # 是否在回答末尾附上参考来源与链接
    linkify_in_text: bool = True  # 是否将正文中的 [1] 替换为带悬停标题的可点击超链接 [[1]](url "title")
    enable_reasoning: bool = True  # 是否在流式中推送 delta.reasoning_content 搜索与思考状态
    smooth_stream: bool = True  # 是否开启突发 Token 平滑流式输出 (消除瞬间刷屏)


class SearchRequest(BaseModel):
    query: str
    model: str = "experimental"
    mode: str = Field(default_factory=lambda: os.getenv("PERPLEXITY_DEFAULT_MODE", "concise"))
    search_focus: str = "internet"


def get_effective_mode(model: str, requested_mode: str | None = None) -> str:
    """
    根据模型名称后缀 (如 -copilot, -deep, -concise) 或请求参数计算最终生效的搜索模式
    """
    raw_model = (model or "").lower()
    if "-copilot" in raw_model or "-deep" in raw_model:
        return "copilot"
    if "-concise" in raw_model or "-fast" in raw_model:
        return "concise"
    return requested_mode or os.getenv("PERPLEXITY_DEFAULT_MODE", "concise")


# 支持 DeepSeek / OpenAI o1 思考链规范的扩展 ChoiceDelta
class ExtendedChoiceDelta(ChoiceDelta):
    reasoning_content: str | None = None


class ExtendedChunkChoice(ChunkChoice):
    delta: ExtendedChoiceDelta


class ExtendedChatCompletionChunk(ChatCompletionChunk):
    choices: list[ExtendedChunkChoice]


# =====================================================================
# Markdown 引用与超链接处理函数
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
                name = (s.get("name") or s.get("title") or "网页来源").replace('"', "'").replace("\n", " ").strip()
                if len(name) > 60:
                    name = name[:57] + "..."
                if url:
                    return f'[[{idx}]]({url} "{name}")'
        except ValueError:
            pass
        return match.group(0)

    return re.sub(r'(?<!\[)\[(\d+)\](?!\()', replace_citation, text)


class StreamingCitationLinker:
    """
    流式传输中的引用超链接实时转换器：
    处理 Token 分片 (例如 '[' 与 '1]' 分开推送)，并将实时出现的 [1] 转为 [[1]](url "title")
    """
    def __init__(self, sources_getter):
        self.sources_getter = sources_getter
        self.buffer = ""

    def process(self, delta: str) -> str:
        if not delta:
            return ""

        self.buffer += delta
        sources = self.sources_getter()

        output = []
        i = 0
        n = len(self.buffer)

        while i < n:
            if self.buffer[i] == '[':
                close_bracket = self.buffer.find(']', i)
                if close_bracket == -1:
                    remaining = self.buffer[i:]
                    if re.fullmatch(r'\[\d*', remaining):
                        self.buffer = remaining
                        return "".join(output)
                    else:
                        output.append(self.buffer[i])
                        i += 1
                else:
                    tag_content = self.buffer[i+1:close_bracket]
                    if tag_content.isdigit():
                        idx = int(tag_content)
                        if sources and 1 <= idx <= len(sources):
                            s = sources[idx - 1]
                            url = s.get("url", "")
                            name = (s.get("name") or s.get("title") or "网页来源").replace('"', "'").replace("\n", " ").strip()
                            if len(name) > 60:
                                name = name[:57] + "..."
                            if url:
                                output.append(f'[[{idx}]]({url} "{name}")')
                            else:
                                output.append(f'[{idx}]')
                        else:
                            output.append(f'[{tag_content}]')
                    else:
                        output.append(f'[{tag_content}]')
                    i = close_bracket + 1
            else:
                output.append(self.buffer[i])
                i += 1

        self.buffer = ""
        return "".join(output)

    def flush(self) -> str:
        remaining = self.buffer
        self.buffer = ""
        return remaining


def format_citations_markdown(answer: str, sources: list[dict[str, Any]], max_sources: int = 15) -> str:
    """
    格式化并生成参考链接 Markdown 列表（附在回答尾部）。
    """
    if not sources:
        return ""

    if "参考来源" in answer or "参考资料" in answer or "引用来源" in answer or "### 📚" in answer:
        return ""

    cited_indices = set()
    for match in re.finditer(r'\[(\d+)\]', answer):
        try:
            idx = int(match.group(1))
            if 1 <= idx <= len(sources):
                cited_indices.add(idx)
        except ValueError:
            pass

    if cited_indices:
        target_indices = sorted(cited_indices)
    else:
        target_indices = list(range(1, min(len(sources) + 1, max_sources + 1)))

    lines = ["\n\n### 📚 参考来源与链接"]
    for idx in target_indices:
        s = sources[idx - 1]
        name = s.get("name") or s.get("title") or "网页链接"
        url = s.get("url", "")
        clean_name = name.strip().replace("\n", " ")
        if len(clean_name) > 80:
            clean_name = clean_name[:77] + "..."
        if url:
            lines.append(f"{idx}. [{clean_name}]({url})")

    return "\n".join(lines)


# =====================================================================
# 鉴权与辅助工具函数
# =====================================================================

async def verify_auth(request: Request):
    """验证客户端请求头是否携带了合法的 Bearer Token (若服务端配置了 PROXY_API_KEY 或 API_KEY)"""
    proxy_key = os.getenv("PERPLEXITY_PROXY_KEY") or os.getenv("API_KEY") or PROXY_API_KEY
    if not proxy_key:
        return True

    auth_header = request.headers.get("Authorization", "")
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()

    if token != proxy_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "message": "Invalid or missing API key. Please pass 'Authorization: Bearer <KEY>' header.",
                    "type": "invalid_request_error",
                    "param": None,
                    "code": "invalid_api_key",
                }
            },
        )
    return True


def format_messages_to_prompt(messages: list[ChatMessage]) -> str:
    """
    将多轮会话消息转换为适合 Perplexity 深度搜索与上下文理解的单一 Query 文本
    """
    if not messages:
        return ""

    if len(messages) == 1:
        c = messages[0].content
        if isinstance(c, str):
            return c
        return json.dumps(c, ensure_ascii=False)

    lines = []
    for msg in messages:
        role = msg.role.lower()
        content = msg.content if isinstance(msg.content, str) else json.dumps(msg.content, ensure_ascii=False)
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
    cjk_count = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
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
):
    """
    产出符合 OpenAI 官方 /v1/chat/completions 标准的 SSE 流式数据帧：
    1. 首帧秒级推送 (0.1s~0.2s) 建立连接并声明 assistant 角色
    2. 搜索阶段实时推送 delta.reasoning_content 消除等待焦虑
    3. 生成阶段自动将正文中的 [1] 转换为带 Tooltip 的超链接 [[1]](url "title")
    4. 对 Claude/GLM 等模型的突发大块 Token 进行平滑微步节流，呈现顺滑打字机动效
    5. 末尾追加结构化参考来源列表并优雅完成 [DONE]
    """
    created_time = int(time.time())
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    actual_model = resolve_model_name(requested_model)

    # 1. 首帧：声明 assistant 角色 (0.01s 秒级响应)
    role_chunk = ExtendedChatCompletionChunk(
        id=completion_id,
        choices=[
            ExtendedChunkChoice(
                index=0,
                delta=ExtendedChoiceDelta(role="assistant", content=""),
                finish_reason=None,
            )
        ],
        created=created_time,
        model=requested_model,
        object="chat.completion.chunk",
        system_fingerprint="fp_perplexity",
    )
    yield f"data: {role_chunk.model_dump_json(exclude_none=True)}\n\n"

    # 2. 初始思考/搜索状态帧 (0.1s 极速上屏，消除前端空白死等)
    if enable_reasoning:
        init_reasoning = ExtendedChatCompletionChunk(
            id=completion_id,
            choices=[
                ExtendedChunkChoice(
                    index=0,
                    delta=ExtendedChoiceDelta(reasoning_content="🔍 正在联网检索并分析全网最新信源...\n"),
                    finish_reason=None,
                )
            ],
            created=created_time,
            model=requested_model,
            object="chat.completion.chunk",
            system_fingerprint="fp_perplexity",
        )
        yield f"data: {init_reasoning.model_dump_json(exclude_none=True)}\n\n"

    accumulated_content = ""
    latest_sources: list[dict[str, Any]] = []
    has_sent_sources_progress = False

    # 初始化流式链接转换器
    linker = StreamingCitationLinker(lambda: latest_sources)

    try:
        # 3. 异步消费 Perplexity 后端流
        async for chunk in client.ask_async_stream(query, model=requested_model, mode=mode):
            item_type = chunk.get("type")
            if chunk.get("display_model"):
                actual_model = chunk["display_model"]
            if chunk.get("sources"):
                latest_sources = chunk["sources"]

            # 处理搜索阶段进度 (推送至 reasoning_content)
            if item_type == "progress" and enable_reasoning:
                sources_count = chunk.get("sources_count", len(latest_sources))
                if not has_sent_sources_progress and sources_count > 0:
                    has_sent_sources_progress = True
                    progress_chunk = ExtendedChatCompletionChunk(
                        id=completion_id,
                        choices=[
                            ExtendedChunkChoice(
                                index=0,
                                delta=ExtendedChoiceDelta(
                                    reasoning_content=f"🌐 已检索并筛选 {sources_count} 篇高相关网页参考资料，开始综合分析与生成回答...\n\n"
                                ),
                                finish_reason=None,
                            )
                        ],
                        created=created_time,
                        model=actual_model,
                        object="chat.completion.chunk",
                        system_fingerprint="fp_perplexity",
                    )
                    yield f"data: {progress_chunk.model_dump_json(exclude_none=True)}\n\n"

            # 处理正文文本输出
            elif item_type == "delta":
                raw_delta = chunk.get("delta", "")
                if raw_delta:
                    if linkify_in_text:
                        out_delta = linker.process(raw_delta)
                    else:
                        out_delta = raw_delta

                    if out_delta:
                        accumulated_content += out_delta

                        # 平滑流式调度 (对瞬时大块 Tokens 进行微步切片，防止突发刷屏)
                        if smooth_stream and len(out_delta) > 12:
                            slice_size = 4
                            for i in range(0, len(out_delta), slice_size):
                                sub_part = out_delta[i:i + slice_size]
                                delta_chunk = ExtendedChatCompletionChunk(
                                    id=completion_id,
                                    choices=[
                                        ExtendedChunkChoice(
                                            index=0,
                                            delta=ExtendedChoiceDelta(content=sub_part),
                                            finish_reason=None,
                                        )
                                    ],
                                    created=created_time,
                                    model=actual_model,
                                    object="chat.completion.chunk",
                                    system_fingerprint="fp_perplexity",
                                )
                                yield f"data: {delta_chunk.model_dump_json(exclude_none=True)}\n\n"
                                await asyncio.sleep(0.008)  # 8ms 微延迟，打造丝滑打字效果
                        else:
                            delta_chunk = ExtendedChatCompletionChunk(
                                id=completion_id,
                                choices=[
                                    ExtendedChunkChoice(
                                        index=0,
                                        delta=ExtendedChoiceDelta(content=out_delta),
                                        finish_reason=None,
                                    )
                                ],
                                created=created_time,
                                model=actual_model,
                                object="chat.completion.chunk",
                                system_fingerprint="fp_perplexity",
                            )
                            yield f"data: {delta_chunk.model_dump_json(exclude_none=True)}\n\n"

        # 刷新残余 buffer
        if linkify_in_text:
            flushed = linker.flush()
            if flushed:
                accumulated_content += flushed
                flush_chunk = ExtendedChatCompletionChunk(
                    id=completion_id,
                    choices=[
                        ExtendedChunkChoice(
                            index=0,
                            delta=ExtendedChoiceDelta(content=flushed),
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
            citations_md = format_citations_markdown(accumulated_content, latest_sources)
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
                "message": f"Perplexity Stream 异常: {str(e)}",
                "type": "server_error",
                "param": None,
                "code": "stream_error",
            }
        }
        yield f"data: {json.dumps(err_payload, ensure_ascii=False)}\n\n"

    # 7. 结束标记
    yield "data: [DONE]\n\n"


# =====================================================================
# API 路由实现
# =====================================================================

@app.get("/")
async def root_index():
    return {
        "service": "Perplexity Search2API OpenAI Gateway",
        "status": "running",
        "version": "2.3.0",
        "endpoints": {
            "chat_completions": "POST /v1/chat/completions",
            "models": "GET /v1/models",
            "search": "POST /search",
            "auth_info": "GET /auth/info",
            "auth_refresh": "POST /auth/refresh",
        },
    }


@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": int(time.time())}


@app.get("/v1/models")
@app.get("/models")
async def list_models(user=Depends(verify_auth)):
    """返回完全兼容 OpenAI /v1/models 格式的模型列表"""
    created_time = 1700000000
    unique_models = sorted(set(MODEL_ALIASES.keys()))

    models_data = [
        Model(
            id=model_id,
            created=created_time,
            object="model",
            owned_by="perplexity",
        ).model_dump()
        for model_id in unique_models
    ]

    return {
        "object": "list",
        "data": models_data,
    }


@app.get("/v1/models/{model_id}")
async def get_model(model_id: str, user=Depends(verify_auth)):
    """获取单个模型详情"""
    if model_id not in MODEL_ALIASES:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "message": f"The model '{model_id}' does not exist",
                    "type": "invalid_request_error",
                    "param": "model",
                    "code": "model_not_found",
                }
            },
        )
    return Model(
        id=model_id,
        created=1700000000,
        object="model",
        owned_by="perplexity",
    ).model_dump()


@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def chat_completions(req: ChatCompletionRequest, user=Depends(verify_auth)):
    """
    OpenAI /v1/chat/completions 核心兼容网关
    - 极致优化流式响应首字延迟 (TTFT) 与思考链实时呈现
    - 平滑流式 Token 节流与微步调度
    - 正文中的 [1], [2] 自动转换为带悬停预览的 Markdown 超链接 [[1]](url "title")
    - 文末自动附带排版整洁的参考链接列表
    - 支持流式输出 (stream=true) 与非流式完整响应 (stream=false)
    - 完全通过 OpenAI 官方 SDK 规范类进行数据组装
    """
    client = PerplexityClient()
    effective_mode = get_effective_mode(req.model, req.mode)
    prompt_query = format_messages_to_prompt(req.messages)
    prompt_tokens = estimate_tokens(prompt_query)

    include_usage = False
    if req.stream_options and req.stream_options.include_usage:
        include_usage = True

    # 1. 流式响应分支
    if req.stream:
        return StreamingResponse(
            sse_chat_stream_generator(
                client=client,
                query=prompt_query,
                requested_model=req.model,
                mode=effective_mode,
                include_usage=include_usage,
                prompt_tokens=prompt_tokens,
                append_citations=req.append_citations,
                linkify_in_text=req.linkify_in_text,
                enable_reasoning=req.enable_reasoning,
                smooth_stream=req.smooth_stream,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Content-Type": "text/event-stream; charset=utf-8",
            },
        )

    # 2. 非流式响应分支
    try:
        result = client.ask(
            query=prompt_query,
            model=req.model,
            mode=effective_mode,
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

        return JSONResponse(content=resp_dict)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "message": f"Perplexity API 调用失败: {str(e)}",
                    "type": "api_error",
                    "param": None,
                    "code": "perplexity_internal_error",
                }
            },
        )


@app.post("/search")
async def search_endpoint(req: SearchRequest, user=Depends(verify_auth)):
    """
    Perplexity 结构化联网搜索端点
    返回原始检索答案与结构化 Sources 列表
    """
    client = PerplexityClient()
    effective_mode = get_effective_mode(req.model, req.mode)
    try:
        res = client.ask(
            query=req.query,
            model=req.model,
            mode=effective_mode,
        )
        return {
            "query": req.query,
            "answer": res.get("answer", ""),
            "sources": res.get("sources", []),
            "model": res.get("model", req.model),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/info")
async def auth_info(user=Depends(verify_auth)):
    """查看当前保存的凭据状态与用户/组织信息"""
    creds = load_credentials()
    if not creds:
        raise HTTPException(status_code=404, detail="未找到任何凭证，请先登录提取")
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
