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

### 1. 全局安装 CLI (推荐使用 uv)

支持在任何系统上一键全局安装独立 CLI 工具：

```bash
# 全局一键安装
uv tool install git+https://github.com/6Kmfi6HP/perplexity-search2api.git

# 或者免安装直接即用即走
uvx --from git+https://github.com/6Kmfi6HP/perplexity-search2api.git pplx search "量子计算最新突破"
```

> **提示**：安装完成后，系统将自动注册 `pplx`、`perplexity-search2api` 和 `perplexity-api` 三个全局命令。

---

### 2. 提取或配置凭据
```bash
# 方式 A：从当前已登录 Perplexity 的浏览器自动提取 (推荐)
pplx login
# 或
perplexity-search2api login

# 方式 B：通过环境变量指定 Token (适合无桌面/容器/Agent 环境)
export PERPLEXITY_SESSION_TOKEN="<你的 NextAuth Session Token>"
```

---

### 3. 命令行即时搜索提问

支持使用 `pplx` 超短命令或 `perplexity-search2api` 进行搜索：

```bash
# 极简直达：直接传入搜索问题
pplx "什么是量子计算？用简单的语言解释"

# 标准搜索命令 (支持 search, ask, s 别名)
pplx search "对比 Rust 与 Go 在高并发场景的优缺点"
perplexity-search2api search "对比 Rust 与 Go 在高并发场景的优缺点"

# 指定模型搜索
pplx search "分析最新的科技动态" --model claude-3-7-sonnet
perplexity-search2api ask "深度推理问题" --model grok-4.6

# 调试模式 (输出底层原始 SSE 事件流 JSON)
pplx search "测试提问" --raw
```

---

### 4. 账号状态与凭证管理
```bash
# 查看当前账号、订阅状态与凭据有效期
pplx info

# 手动触发 NextAuth 滚动刷新 (顺延 30 天有效期)
pplx refresh
```

---

### 5. 启动 OpenAI 兼容接口网关
```bash
pplx serve --port 8000
# 或
perplexity-search2api serve --host 0.0.0.0 --port 8000
```

---

### 6. 本地开发与源码运行
```bash
git clone https://github.com/6Kmfi6HP/perplexity-search2api.git
cd perplexity-search2api
uv venv .venv
source .venv/bin/activate
uv pip install -e .

# 使用本地脚本运行
python cli.py search "测试内容"
```

---
## 🐳 Docker 部署方案

本项目提供了完整的 Docker 容器化支持与 GitHub Actions 多架构（`linux/amd64`, `linux/arm64`）自动化镜像编译与发布方案。

### 1. Docker Compose 一键启动（推荐）

项目仓库自带 `docker-compose.yml`，支持通过 `.env` 或环境变量一键拉起服务。

#### 步骤一：准备配置文件
```bash
cp .env.example .env
```
在 `.env` 中填入你的认证配置（二选一）：
- **方式 A（环境变量注入 Token）**：设置 `PERPLEXITY_SESSION_TOKEN=你的NextAuth_Token`，可选设置 `API_KEY` 保护接口。
- **方式 B（挂载 Session 文件）**：本地若已生成 `~/.perplexity_session.json`，将其复制到项目根目录或 `./data/.perplexity_session.json`。

#### 步骤二：启动容器
```bash
# 启动服务并在后台运行
docker compose up -d

# 查看运行日志
docker compose logs -f
```

---

### 2. 使用预编译镜像 (GHCR)

无需拉取源码，直接拉取官方发布的精简安全镜像：

```bash
docker run -d \
  --name perplexity-search2api \
  --restart unless-stopped \
  -p 8000:8000 \
  -e PERPLEXITY_SESSION_TOKEN="你的NextAuth_Token" \
  -e API_KEY="sk-your-custom-gateway-key" \
  -v $(pwd)/data:/app/data \
  ghcr.io/6kmfi6hp/perplexity-search2api:latest
```

---

### 3. 本地构建 Docker 镜像

如需在本地对源码进行定制或自建镜像：

```bash
# 构建镜像
docker build -t perplexity-search2api:latest .

# 运行镜像
docker run -d \
  --name perplexity-search2api \
  -p 8000:8000 \
  --env-file .env \
  perplexity-search2api:latest
```

---

### 4. Makefile 快捷指令

```bash
make docker-build         # 本地构建 Docker 镜像
make docker-run           # 基于本地 .env 启动容器
make docker-compose-up    # 使用 Compose 在后台启动并自动 build
make docker-compose-down  # 停止并清理 Compose 容器
```

---

### 5. 自动化构建与发布流程 (CI/CD)

项目在 `.github/workflows/docker-publish.yml` 中配置了全自动镜像构建发布流水线：

- 🚀 **多架构原生构建**：基于 QEMU + Docker Buildx，同时发布 `linux/amd64` 与 `linux/arm64` 双架构镜像。
- 📦 **双 Registry 分发**：
  - **GHCR (`ghcr.io/6kmfi6hp/perplexity-search2api`)**：开箱即用，自动推送到 GitHub Packages。
  - **Docker Hub**（可选）：在 GitHub Secrets 中配置 `DOCKERHUB_USERNAME` 与 `DOCKERHUB_TOKEN` 后自动同步推送。
- 🏷️ **语义化版本规范**：
  - 推送到 `main` 分支：自动发布 `edge` 和 `latest`。
  - 触发 Git Release Tag（如 `v1.0.0`）：自动生成 `1.0.0`、`1.0`、`1` 及 `latest` 标签。
  - Pull Request：自动触发多架构构建与健康校验（不推送），保障代码质量。
  - 镜像附带 OCI Attestation、SBOM 安全物料清单与 GHA 高速构建缓存。

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