"""
Perplexity Search2API HTTP Server (FastAPI)
- 完全兼容 OpenAI /v1/chat/completions 接口标准 (支持流式 & 非流式)
- 支持全系列大模型 (Claude 5, GPT-5.6, Grok 4.6, Gemini 3.7, GLM 5.3/5.2, Kimi K3, Nemotron 3 等)
- 提供 /search 结构化搜索与来源引用端点
- 提供 /v1/models 模型列表端点
- 提供 /auth/info 与 /auth/refresh 凭据管理端点
- 支持可选的 API_KEY / PERPLEXITY_PROXY_KEY 鉴权保护
"""

import json
import os
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from perplexity_auth import PerplexityAuthManager, extract_from_browser, load_credentials
from perplexity_client import MODEL_ALIASES, PerplexityClient

app = FastAPI(
    title="Perplexity Search2API",
    description="Perplexity Pro 搜索与推理能力转 OpenAI 兼容 API 服务",
    version="0.1.0",
)

# 允许跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# API Key Verification (Optional)
# ---------------------------------------------------------------------------

def verify_api_key(request: Request) -> None:
    """如果配置了 API_KEY 或 PERPLEXITY_PROXY_KEY 环境变量，则校验请求头"""
    required_key = os.getenv("API_KEY") or os.getenv("PERPLEXITY_PROXY_KEY")
    if not required_key:
        return

    auth_header = request.headers.get("Authorization", "")
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "api-key" in request.headers:
        token = request.headers.get("api-key", "").strip()

    if token != required_key:
        raise HTTPException(
            status_code=401,
            detail={"error": {"message": "Invalid or missing API key", "type": "auth_error"}},
        )


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: str
    name: str | None = None


class ChatCompletionRequest(BaseModel):
    model: str = "experimental"
    messages: list[ChatMessage]
    stream: bool | None = False
    temperature: float | None = 0.7
    mode: str | None = "copilot"
    max_tokens: int | None = None


class SearchRequest(BaseModel):
    query: str
    model: str | None = "experimental"
    mode: str | None = "copilot"
    timeout: float | None = 60.0


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    """服务概览与运行状态"""
    return {
        "service": "Perplexity Search2API",
        "status": "running",
        "version": "0.1.0",
        "endpoints": {
            "chat_completions": "/v1/chat/completions",
            "models": "/v1/models",
            "search": "/search",
            "health": "/health",
            "auth_info": "/auth/info",
            "auth_refresh": "/auth/refresh",
        },
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    """健康检查端点"""
    return {"status": "ok", "timestamp": int(time.time())}


@app.get("/auth/info")
def get_auth_info():
    """获取当前持久化凭据详情与用户信息"""
    creds = load_credentials()
    if not creds:
        raise HTTPException(status_code=404, detail="未找到任何已保存的凭据，请先执行登录提取")
    user = creds.get("user", {})
    return {
        "logged_in": bool(creds.get("session_token")),
        "user": user,
        "expires_at": creds.get("expires_at"),
        "last_refreshed_at": creds.get("last_refreshed_at"),
        "source": creds.get("source", "file"),
    }


@app.post("/auth/refresh")
def refresh_token():
    """手动触发 NextAuth 滚动刷新 Token (延长 30 天)"""
    try:
        manager = PerplexityAuthManager()
        res = manager.refresh()
        return {"status": "success", "message": "凭据刷新成功，有效期已顺延 30 天", "data": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/auth/login-browser")
def login_from_browser():
    """通过 agent-browser 自动从真实浏览器提取凭据"""
    try:
        creds = extract_from_browser()
        return {"status": "success", "message": "凭据提取并保存成功", "user": creds.get("user")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/models", dependencies=[Depends(verify_api_key)])
def list_models():
    """返回 OpenAI 兼容模型列表"""
    created_ts = int(time.time())
    unique_models = sorted(set(MODEL_ALIASES.keys()))
    data = []
    for m in unique_models:
        data.append(
            {
                "id": m,
                "object": "model",
                "created": created_ts,
                "owned_by": "perplexity",
                "permission": [],
                "root": m,
                "parent": None,
            }
        )
    return {"object": "list", "data": data}


@app.post("/search", dependencies=[Depends(verify_api_key)])
def search_endpoint(req: SearchRequest):
    """
    Perplexity 结构化搜索端点
    返回纯文本回答以及搜索出的全部引用来源 (Sources)
    """
    try:
        client = PerplexityClient()
        res = client.ask(
            query=req.query,
            model=req.model or "experimental",
            mode=req.mode or "copilot",
            timeout=req.timeout or 60.0,
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/chat/completions", dependencies=[Depends(verify_api_key)])
def chat_completions(req: ChatCompletionRequest):
    """
    OpenAI 兼容的 Chat Completions 接口
    支持 Stream (SSE) 与 Non-Stream 两种模式
    """
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages 不能为空")

    # 提取最后一条用户消息作为 query
    user_query = req.messages[-1].content
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created_ts = int(time.time())

    client = PerplexityClient()

    if req.stream:
        # -------------------------------------------------------------
        # 流式模式 (SSE)
        # -------------------------------------------------------------
        def sse_generator():
            last_text = ""
            try:
                for chunk in client.ask_stream(
                    query=user_query,
                    model=req.model,
                    mode=req.mode or "copilot",
                ):
                    full_ans = chunk["answer"]
                    delta_text = full_ans[len(last_text) :]
                    last_text = full_ans

                    if delta_text:
                        data_chunk = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": created_ts,
                            "model": chunk["display_model"],
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"role": "assistant", "content": delta_text},
                                    "finish_reason": None,
                                }
                            ],
                        }
                        yield f"data: {json.dumps(data_chunk, ensure_ascii=False)}\n\n"

                # 拼接引用来源追加输出
                sources = chunk.get("sources", [])
                if sources:
                    source_lines = ["\n\n### 引用来源：\n"]
                    for idx, s in enumerate(sources, 1):
                        name = s.get("name", f"来源 {idx}")
                        url = s.get("url", "")
                        source_lines.append(f"{idx}. [{name}]({url})\n")
                    sources_text = "".join(source_lines)
                    data_chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created_ts,
                        "model": chunk["display_model"],
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": sources_text},
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(data_chunk, ensure_ascii=False)}\n\n"

                # 发送结束标志
                stop_chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created_ts,
                    "model": chunk["display_model"],
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop",
                        }
                    ],
                }
                yield f"data: {json.dumps(stop_chunk, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as err:
                err_data = {"error": {"message": str(err), "type": "perplexity_api_error"}}
                yield f"data: {json.dumps(err_data, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            sse_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # -------------------------------------------------------------
    # 非流式模式 (Non-streaming)
    # -------------------------------------------------------------
    try:
        res = client.ask(
            query=user_query,
            model=req.model,
            mode=req.mode or "copilot",
        )
        content = res["answer"]

        # 追加引用源
        if res.get("sources"):
            source_lines = ["\n\n### 引用来源：\n"]
            for idx, s in enumerate(res["sources"], 1):
                name = s.get("name", f"来源 {idx}")
                url = s.get("url", "")
                source_lines.append(f"{idx}. [{name}]({url})")
            content += "\n".join(source_lines)

        return {
            "id": completion_id,
            "object": "chat.completion",
            "created": created_ts,
            "model": res.get("model", req.model),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": len(user_query) // 4,
                "completion_tokens": len(content) // 4,
                "total_tokens": (len(user_query) + len(content)) // 4,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("server:app", host=host, port=port, reload=True)
