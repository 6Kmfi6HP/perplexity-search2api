# `pplx` CLI Command Reference

Deterministic CLI command manual for AI agents and developers.

## Subcommand Directory

| Command | Aliases | Purpose | Example |
|---|---|---|---|
| `ask` | `search`, `s` | Execute grounded web search with citations | `pplx ask "query"` |
| `remote` | - | Manage remote API endpoint (avoid storing credentials locally) | `pplx remote set http://host:port/` |
| `models` | - | Inspect supported models list on remote server or local runtime | `pplx models` |
| `info` | - | Inspect current authentication, remote endpoint, and token TTL | `pplx info` |
| `refresh` | - | Renew NextAuth session token (+30 days) on local or remote | `pplx refresh` |
| `login` | - | Extract session token from browser via CDP | `pplx login` |
| `serve` | - | Start OpenAI-compatible `/v1/chat/completions` gateway | `pplx serve --port 8000` |

---

## 1. `pplx remote`

Manage and configure remote Search2API gateway endpoints. When remote mode is active, the CLI connects directly to the remote OpenAI-compatible server without requiring local NextAuth session tokens or browser cookie extraction.

### Syntax
```bash
pplx remote set <URL> [--api-key <KEY>] [--default-model <MODEL>]
pplx remote show
pplx remote test [<URL>] [--api-key <KEY>]
pplx remote unset
```

### Subactions
- `set <URL>`: Test connectivity and persist the remote endpoint into configuration file (`~/.perplexity_config.json`, `.env`, or `pplx.toml`).
- `show` / `get` / `status`: Display the active mode (Remote vs Local), latency, and model availability.
- `test` / `ping` / `check`: Probe target URL for health and list available models.
- `unset` / `clear` / `remove`: Clear saved remote endpoint and return to local direct mode.

---

## 2. `pplx ask` / `pplx search` / `pplx s`

### Syntax
```bash
pplx ask [--model <MODEL>] [--mode <MODE>] [--remote <URL>] [--api-key <KEY>] [--raw] <query>
```

### Options
- `--model <MODEL>`: Choose target model (e.g. `experimental`, `claude-3-7-sonnet`, `gpt-5.6`, `grok-4.6`, `fast`, `gemini-3.7-flash`).
- `--mode <MODE>`: Search depth mode (`copilot` for deep research, `concise` for fast answers).
- `--remote <URL>`, `--base-url <URL>`: Explicitly override the remote gateway endpoint for this invocation.
- `--api-key <KEY>`: Provide API key for gateway authentication.
- `--raw`: Print unprocessed SSE JSON stream for inspection.

---

## 3. `pplx models`

### Syntax
```bash
pplx models [--remote <URL>] [--api-key <KEY>]
```

Lists all available models provided by the remote gateway or supported aliases in local direct mode.

---

## 4. `pplx info`

### Syntax
```bash
pplx info [--local] [--remote <URL>] [--api-key <KEY>]
```

Displays runtime mode, remote endpoint health status, and user / organization subscription credentials.

---

## 5. `pplx refresh`

### Syntax
```bash
pplx refresh [--local] [--remote <URL>]
```

Triggers NextAuth session renewal on the remote gateway server or local token storage (+30 days sliding window).

---

## 6. `pplx login`

### Syntax
```bash
pplx login [--local]
```

Launches automated browser session extraction to retrieve the active `__Secure-next-auth.session-token`. In remote mode, credentials extraction is not needed.

---

## 7. `pplx serve`

### Syntax
```bash
pplx serve [--host <HOST>] [--port <PORT>]
```

### Options
- `--host`: Bind host (default: `0.0.0.0`).
- `--port`: Bind port (default: `8000`).

### Gateway Endpoints
- `GET /health`: Health check.
- `GET /v1/models`: OpenAI-compatible models list.
- `POST /v1/chat/completions`: Streaming & non-streaming OpenAI chat completion endpoint.
- `POST /search`: Structured web search endpoint.
- `GET /auth/info`: Inspect server credentials.
- `POST /auth/refresh`: Remote token renewal.
