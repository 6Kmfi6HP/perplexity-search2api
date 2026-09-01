# Perplexity Search2API

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue?logo=python" alt="Python Versions"></a>
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white" alt="FastAPI"></a>
  <a href="https://github.com/openai/openai-python"><img src="https://img.shields.io/badge/OpenAI_SDK-Compatible-black.svg?logo=openai&logoColor=white" alt="OpenAI Compatible"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT"></a>
</p>

基于对 [oh-my-pi](https://github.com/can1357/oh-my-pi) 及 Perplexity 官方 Web / SSO 鉴权机制的深度逆向工程，构建的 **Perplexity Pro / Copilot 联网搜索与推理能力转 OpenAI 官方标准 `/v1/chat/completions` 网关服务及终端 CLI 工具**。

---

## 🌟 核心特性

- 🔑 **零门槛 SSO 登录与凭证提取**：
  借助 `agent-browser --auto-connect` 直接连接真实 Chrome 浏览器，一键从 Linux Do SSO、Google 或企业组织登录页面提取会话 Token。
- 🔄 **自动滚动刷新机制 (Rolling Session)**：
  逆向 NextAuth `/api/auth/session` 端点，支持无感会话保活与 30 天滑动窗口刷新，使登录态永不过期。
- 🌐 **原生 Copilot / Pro 级搜索与引用提取**：
  直连 `https://www.perplexity.ai/rest/sse/perplexity_ask`，支持极速流式 (SSE) 渲染与引用来源 (Sources / Citations) 结构化解析。
- 🤖 **全系列顶级大模型路由**：
  支持直通 `Claude 3.7 Sonnet`、`GPT-5.6 / 4o`、`Grok 4.6`、`Gemini 3.7 Thinking`、`GLM 5.3`、`Kimi K3`、`Nemotron 3 Ultra` 等数十种顶级模型。
- ⚡ **100% 严格对齐 OpenAI 官方 SDK 规范**：
  网关完全基于 `openai.types.chat` (`ChatCompletion`, `ChatCompletionChunk`, `CompletionUsage`) 标准数据结构构建，支持流式 (SSE) 与非流式、Token 统计、Finish Reason 以及完整的上下文会话拼接。

---

## 🚀 快速上手

### 1. 安装依赖
```bash
# 推荐使用 uv
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### 2. 提取或配置凭据
```bash
# 方式 A：从当前已登录 Perplexity 的浏览器自动提取 (推荐)
python cli.py login

# 方式 B：通过环境变量指定 Token
export PERPLEXITY_SESSION_TOKEN="<你的 NextAuth Session Token>"
```

### 3. 命令行即时搜索提问
```bash
# 基础提问
python cli.py ask "什么是量子计算？用简单的语言解释"

# 指定模型
python cli.py ask "对比 Rust 与 Go 在高并发场景的优缺点" --model claude-3-7-sonnet

# 开启 --raw 调试模式 (输出底层原始 SSE 事件 JSON)
python cli.py ask "测试提问" --model gpt-5.6 --raw
```

### 4. 启动 OpenAI 兼容接口网关
```bash
python cli.py serve --port 8000
# 或
uvicorn server:app --host 0.0.0.0 --port 8000
```

---

## 💻 客户端接入示例 (Python OpenAI SDK)

```python
from openai import OpenAI

# 将 base_url 指向本地网关
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed-for-local"  # 若服务端未配置 PERPLEXITY_PROXY_KEY 可填任意字符串
)

# 1. 查询支持的模型列表
models = client.models.list()
print(f"支持的模型总数: {len(models.data)}")

# 2. 非流式对话 (Non-streaming)
response = client.chat.completions.create(
    model="gpt-5.6",
    messages=[
        {"role": "system", "content": "你是一个资深技术专家。"},
        {"role": "user", "content": "2025 年主流的大模型有哪些最新突破？"}
    ]
)
print("回答内容:\n", response.choices[0].message.content)
print("Token 统计:", response.usage)

# 3. 流式对话 (Streaming)
stream = client.chat.completions.create(
    model="claude-3-7-sonnet",
    messages=[
        {"role": "user", "content": "用 100 字介绍空间计算与 Vision Pro"}
    ],
    stream=True
)

for chunk in stream:
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

---

## 📚 接口端点清单

| 方法 | 端点 | 说明 |
|---|---|---|
| `POST` | `/v1/chat/completions` | **OpenAI 核心对话补全接口** (支持 `stream=true/false`，对齐官方 SDK) |
| `GET` | `/v1/models` | 获取当前支持的全部大模型列表 |
| `GET` | `/v1/models/{model_id}` | 获取指定模型信息 |
| `POST` | `/search` | Perplexity 原生结构化搜索端点 (返回答案与 Sources 列表) |
| `GET` | `/auth/info` | 查看当前凭据 TTL、用户信息及企业组织身份 |
| `POST` | `/auth/refresh` | 手动触发凭证滚动刷新 (顺延 30 天) |
| `GET` | `/health` | 服务健康检查 |

---

## 🎯 常用模型别名对照

| 友好别名 (请求可直接传) | Perplexity 后端真实 Key | 说明 |
|---|---|---|
| `experimental` / `auto` / `best` | `experimental` | Perplexity 智能优选模型 |
| `gpt-5.6` / `gpt-4o` | `gpt56_terra` | OpenAI GPT-5.6 深度思考版 |
| `gpt-5.6-instant` | `gpt56_sol` | OpenAI GPT-5.6 极速版 |
| `claude-3-7-sonnet` / `claude-3.7-sonnet` | `claude50sonnet` | Anthropic Claude 3.7 Sonnet |
| `claude-opus` / `claude-3-opus` | `claude50opus` | Anthropic Claude 3 Opus |
| `grok-4.6` / `grok-4` | `grok46low` | xAI Grok 4.6 深度思考版 |
| `gemini-3.7-flash` | `gemini37flash` | Google Gemini 3.7 Flash |
| `gemini-3.1-pro` | `gemini31pro_high` | Google Gemini 3.1 Pro |
| `glm-5.3` | `glm_5_3_thinking` | 智谱 GLM 5.3 深度思考版 |
| `kimi-k3` | `kimik3thinking` | 月之暗面 Kimi K3 深度思考版 |
| `nemotron-3` | `nv_nemotron_3_ultra` | NVIDIA Nemotron 3 Ultra |

---

## 📄 开源许可
MIT License