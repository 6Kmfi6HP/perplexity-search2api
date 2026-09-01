# Perplexity Search2API

<p align="center">
  <a href="https://github.com/6Kmfi6HP/perplexity-search2api/actions"><img src="https://img.shields.io/github/actions/workflow/status/6Kmfi6HP/perplexity-search2api/ci.yml?branch=main&label=CI&logo=github" alt="CI Status"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue?logo=python" alt="Python Versions"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT"></a>
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white" alt="FastAPI"></a>
</p>

基于对 [oh-my-pi](https://github.com/can1357/oh-my-pi) 及 Perplexity 官方 Web / SSO 鉴权机制的深度逆向工程，构建的 **Perplexity Pro / Copilot 搜索与推理能力转 OpenAI 兼容 API 服务及终端 CLI 工具**。

---

## 🌟 核心特性

- 🔑 **零门槛 SSO 登录与凭证提取**：
  借助 `agent-browser --auto-connect` 直接连接真实 Chrome 浏览器，一键从 Linux Do SSO、Google 或企业组织登录页面提取会话 Token。
- 🔄 **自动滚动刷新机制 (Rolling Session)**：
  逆向 NextAuth `/api/auth/session` 端点，支持无感会话保活与 30 天滑动窗口刷新，使登录态永不过期。
- 🌐 **原生 Copilot / Pro 级搜索与引用提取**：
  直连 `https://www.perplexity.ai/rest/sse/perplexity_ask`，支持极速流式 (SSE) 渲染与引用来源 (Sources / Citations) 解析。
- 🤖 **全系列顶级大模型路由**：
  支持直通 `Claude 5 / Sonnet`、`GPT-5.6 / 4o`、`Grok 4.6`、`Gemini 3.7 Thinking`、`GLM 5.3`、`Kimi K3`、`Nemotron 3 Ultra` 等数十种顶级模型。
- ⚡ **OpenAI 兼容接口**：
  提供标准 `/v1/chat/completions` 与 `/v1/models`，可直接无缝接入 NextChat、ChatBox、LobeChat、Dify、沉浸式翻译或 Cursor 等生态。
- 🛡️ **安全配置与容器友好**：
  支持可选的 `API_KEY` 访问鉴权、`PERPLEXITY_SESSION_TOKEN` 环境变量注入与 Docker / CI / Serverless 部署支持。

---

## 🚀 快速上手

### 1. 环境准备与依赖安装

推荐使用 [uv](https://github.com/astral-sh/uv) 或 Python 虚拟环境：

```bash
# 克隆仓库
git clone https://github.com/6Kmfi6HP/perplexity-search2api.git
cd perplexity-search2api

# 创建虚拟环境并安装依赖
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
```

若需使用自动从真实浏览器提取凭据功能，请确保全局安装了 `agent-browser`：

```bash
npm install -g agent-browser
```

---

### 2. 凭证提取与管理

#### 一键从浏览器提取登录凭据
在您的 Chrome 浏览器中打开并登录 [Perplexity.ai](https://www.perplexity.ai)（包含 SSO / Linux Do 登录），随后在终端执行：

```bash
perplexity-search2api login
# 或直接运行：python cli.py login
```

#### 查看当前凭据与有效期状态
```bash
perplexity-search2api info
```

#### 手动滚动刷新 Token (顺延 30 天有效期)
```bash
perplexity-search2api refresh
```

---

### 3. 命令行即时搜索提问

```bash
# 标准交互搜索
perplexity-search2api ask "什么是量子计算？用简单清晰的语言解释"

# 指定模型与搜索模式
perplexity-search2api ask "分析 2026 年最新大模型技术趋势" --model claude-3-7-sonnet --mode copilot

# RAW 调试模式 (直接打印 Perplexity 原始 SSE 事件流 JSON)
perplexity-search2api ask "测试提问" --raw
```

---

### 4. 启动 OpenAI 兼容 HTTP 服务

```bash
# 启动 API 服务 (默认监听 0.0.0.0:8000)
perplexity-search2api serve --port 8000
# 或运行：python server.py
```

服务就绪后，即可访问交互式 API 文档：`http://localhost:8000/docs`。

---

## 🔌 API 接口与使用示例

### 1. OpenAI 兼容 Chat Completions (`/v1/chat/completions`)

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-7-sonnet",
    "messages": [
      {"role": "user", "content": "请介绍 2026 年最先进的 Agent 架构"}
    ],
    "stream": false
  }'
```

### 2. 专用结构化搜索接口 (`/search`)

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Linux Do 社区最新热门帖子",
    "model": "experimental",
    "mode": "copilot"
  }'
```

### 3. 查看可用模型列表 (`/v1/models`)

```bash
curl http://localhost:8000/v1/models
```

---

## 🧭 支持模型与别名映射 (Model Aliases)

| 类别 | 推荐请求名称 (Alias) | Perplexity 后端内部模型 | 说明 |
| :--- | :--- | :--- | :--- |
| **官方默认** | `experimental`, `auto`, `default` | `experimental` | Perplexity 综合最优自动路由 |
| **Sonar** | `sonar-pro`, `pplx_pro`, `sonar` | `pplx_pro` | Perplexity 官方 Sonar 深度搜索 |
| **Claude** | `claude-3-7-sonnet`, `claude-3.7-sonnet` | `claude50sonnet` | Anthropic Claude 旗舰模型 |
| **GPT** | `gpt-5.6`, `gpt-5`, `gpt-4o` | `gpt56_terra` | OpenAI GPT 系列旗舰模型 |
| **GPT (Sol)** | `gpt-5.6-sol`, `gpt56_sol` | `gpt56_sol` | OpenAI 高速轻量模型 |
| **Grok** | `grok-4.6`, `grok-3`, `grok` | `grok46low` | xAI Grok 旗舰推理模型 |
| **Gemini** | `gemini-3.7-thinking`, `gemini-thinking` | `gemini37thinking` | Google 深度思考与长上下文模型 |
| **GLM** | `glm-5.3`, `glm-5`, `glm` | `glm_5_3_thinking` | 智谱 GLM 思考模型 |
| **Kimi** | `kimi-k3`, `kimi-k3-thinking`, `kimi` | `kimik3thinking` | 月之暗面 Kimi 深度推理模型 |
| **Nemotron**| `nemotron-3-ultra`, `nemotron` | `nv_nemotron_3_ultra` | NVIDIA 旗舰推理模型 |

---

## ⚙️ 环境变量配置

支持通过环境变量或根目录 `.env` 文件定制配置：

| 变量名 | 默认值 | 描述 |
| :--- | :--- | :--- |
| `HOST` | `0.0.0.0` | 服务端监听 IP 地址 |
| `PORT` | `8000` | 服务端监听端口 |
| `API_KEY` | *(空)* | 可选的代理鉴权 Key。设置后需在请求头携带 `Authorization: Bearer <API_KEY>` |
| `PERPLEXITY_SESSION_PATH` | `~/.perplexity_session.json` | 凭据存储文件绝对路径 |
| `PERPLEXITY_SESSION_TOKEN`| *(空)* | 直接从环境变量注入 NextAuth Session Token (适用于 Docker / CI) |
| `PERPLEXITY_USER_NAME` | `Env User` | 环境变量注入模式下的默认用户名 |
| `PERPLEXITY_USER_EMAIL`| *(空)* | 环境变量注入模式下的用户邮箱 |

---

## 📁 目录结构

```
perplexity-search2api/
├── .github/
│   ├── workflows/ci.yml                # GitHub Actions 自动化持续集成
│   ├── ISSUE_TEMPLATE/                 # 问题与功能建议模板
│   └── PULL_REQUEST_TEMPLATE.md        # 合并请求规范模板
├── tests/                              # Pytest 单元测试集
│   ├── test_auth.py
│   ├── test_client.py
│   ├── test_server.py
│   └── test_cli.py
├── .editorconfig                       # 统一跨编辑器代码格式规范
├── .env.example                        # 环境变量模板示例
├── .gitignore                          # 严格的凭证脱敏与忽略规则
├── CODE_OF_CONDUCT.md                  # 社区行为准则
├── CONTRIBUTING.md                     # 开源贡献与 Git 提交规范
├── LICENSE                             # MIT 开源许可证
├── pyproject.toml                      # 现代 PEP 517/621 包构建与 Ruff/Pytest 配置
├── README.md                           # 项目说明文档
├── requirements.txt                    # 依赖清单
├── perplexity-oauth-technical-details.md # 深度逆向技术解析文档
├── perplexity_auth.py                  # 认证、SSO 提取与会话滚动刷新器
├── perplexity_client.py                # Perplexity Ask / Pro 搜索与流式客户端
├── cli.py                              # 丰富交互的终端命令行工具
└── server.py                           # FastAPI / OpenAI 兼容 HTTP 服务端
```

---

## 🧪 运行测试

```bash
pytest -v
ruff check .
```

---

## 📖 技术深度解析

如需了解 Perplexity Web 接口调用细节、SSE 事件流格式、NextAuth 滚动刷新算法以及反逆向工程细节，请参阅技术文档：
👉 [Perplexity OAuth & API 深度逆向技术解析](perplexity-oauth-technical-details.md)

---

## ⚠️ 免责声明 (Disclaimer)

1. 本项目仅供技术研究、逆向工程学习和个人合法合规使用，严禁用于任何商业牟利或恶意爬取行为。
2. 使用本项目时，请自觉遵守 [Perplexity 服务条款](https://www.perplexity.ai/tos) 及相关法律法规。
3. 请妥善保管您的本地凭证文件 (`.perplexity_session.json`)，切勿将其公开或提交至公共代码仓库。

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 许可证开源。
