# `pplx` CLI Command Reference

Command and flag manual for the `pplx` CLI. Model aliases and vertical scopes live in [models.md](models.md).

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
- `-V`, `--vertical <VERTICAL>`: Select a search vertical; the full table with data sources is in [models.md](models.md).
- `--patents` / `--academic` / `--finance` / `--social`: Shortcuts for `-V patents` / `-V academic` / `-V finance` / `-V social`.
- `--model <MODEL>`: Choose an AI model alias or a compound `vertical:model` name (e.g. `claude-3-7-sonnet`, `patents:claude-3-7-sonnet`); alias table in [models.md](models.md).
- `--mode <MODE>`: `copilot` (default) — full multi-step query planning across 10–30 web sources with rich citations; `concise` — low-latency direct extraction without multi-pass web chaining.
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

Display active session status, subscription tier, and token TTL. `--local` inspects local credentials even when a remote endpoint is configured.

---

## 5. `pplx refresh`

Renew NextAuth session token (+30 days). `--local` refreshes local credentials even when a remote endpoint is configured.

---

## 6. `pplx login`

Extract session token from Chrome/Edge browser. `--local` forces local extraction even when a remote endpoint is configured.

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
