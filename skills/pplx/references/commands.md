# `pplx` CLI Command Reference

Deterministic CLI command manual for AI agents and developers.

## Subcommand Directory

| Command | Aliases | Purpose | Example |
|---|---|---|---|
| `ask` | `search`, `s` | Execute grounded web or vertical search with citations | `pplx ask "query"` |
| `remote` | - | Manage remote API endpoint (avoid storing credentials locally) | `pplx remote set http://host:port/` |
| `models` | - | Inspect supported models & search verticals | `pplx models` |
| `info` | - | Inspect current authentication, remote endpoint, and token TTL | `pplx info` |
| `refresh` | - | Renew NextAuth session token (+30 days) on local or remote | `pplx refresh` |
| `login` | - | Extract session token from browser via CDP | `pplx login` |
| `serve` | - | Start OpenAI-compatible `/v1/chat/completions` gateway | `pplx serve --port 8000` |

---

## 1. `pplx ask` / `pplx search`

Execute streaming live search and multi-model research.

### Syntax
```bash
pplx ask "<QUERY>" [OPTIONS]
```

### Options
- `-V`, `--vertical <VERTICAL>`: Select search vertical (`web`, `patents`, `academic`, `finance`, `social`, `health`, `writing`, `wolfram`, `youtube`, `reddit`).
- `--patents`: Shortcut for `-V patents` (Perplexity Patents search).
- `--academic`: Shortcut for `-V academic` (Perplexity Academic & research papers search).
- `--finance`: Shortcut for `-V finance` (Perplexity Finance & market intelligence).
- `--social`: Shortcut for `-V social` (Social, Reddit, and community discussions).
- `--model <MODEL>`: Choose AI model (e.g. `claude-3-7-sonnet`, `gpt-5.6`, `grok-4.6`, or compound `patents:claude-3-7-sonnet`).
- `--mode <MODE>`: `copilot` (default deep search) or `concise` (fast single-pass).
- `--raw`: Output raw JSON SSE stream events for debugging.

---

## 2. `pplx remote`

Manage and configure remote Search2API gateway endpoints.

### Syntax
```bash
pplx remote set <URL> [--api-key <KEY>] [--default-model <MODEL>]
pplx remote show
pplx remote test
pplx remote unset
```

---

## 3. `pplx models`

List available AI foundation models and search vertical modes.

### Syntax
```bash
pplx models [--remote <URL>] [--api-key <KEY>]
```

---

## 4. `pplx info`

Display active session status, subscription tier, and token TTL.

---

## 5. `pplx refresh`

Renew NextAuth session token (+30 days).

---

## 6. `pplx login`

Extract session token from Chrome/Edge browser.

---

## 7. `pplx serve`

Start the FastAPI gateway service.

### Syntax
```bash
pplx serve [--host <HOST>] [--port <PORT>]
```

### Gateway Endpoints
- `GET /health`: Health check.
- `GET /verticals`: Supported search verticals and metadata.
- `GET /v1/models`: OpenAI-compatible models list.
- `POST /v1/chat/completions`: Streaming & non-streaming OpenAI chat completion endpoint (supports vertical selection via compound model name or `vertical` field).
- `POST /search` / `GET /search`: Structured web search endpoint (supports `?vertical=patents`, etc.).
- `GET /auth/info`: Inspect server credentials.
- `POST /auth/refresh`: Remote token renewal.
