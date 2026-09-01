# `pplx` CLI Command Reference

Deterministic CLI command manual for AI agents and developers.

## Subcommand Directory

| Command | Aliases | Purpose | Example |
|---|---|---|---|
| `ask` | `search`, `s` | Execute grounded web search with citations | `pplx ask "query"` |
| `info` | - | Inspect current authentication and token TTL | `pplx info` |
| `refresh` | - | Renew NextAuth session token (+30 days) | `pplx refresh` |
| `login` | - | Extract session token from browser via CDP | `pplx login` |
| `serve` | - | Start OpenAI-compatible `/v1/chat/completions` gateway | `pplx serve --port 8000` |

---

## 1. `pplx ask` / `pplx search` / `pplx s`

### Syntax
```bash
pplx ask [--model <MODEL>] [--mode <MODE>] [--raw] <query>
```

### Options
- `<query>`: Search question or prompt string.
- `--model <MODEL>`: Model alias (e.g., `claude-3-7-sonnet`, `gpt-5.6`, `grok-4.6`). Defaults to `experimental`.
- `--mode <MODE>`: Search depth mode (`copilot` [default], `concise`).
- `--raw`: Emit raw SSE JSON events directly to stdout (useful for protocol debugging).

### Exit Codes
- `0`: Success (answers and citation list output).
- `1`: Error encountered (authentication failure, network error, or invalid parameter).

---

## 2. `pplx info`

### Syntax
```bash
pplx info
```

Displays a structured table with:
- Credentials file path (`~/.perplexity_session.json`)
- User display name and email
- Pro subscription status
- NextAuth session token expiration timestamp
- Last refresh timestamp

---

## 3. `pplx refresh`

### Syntax
```bash
pplx refresh
```

Invokes `https://www.perplexity.ai/api/auth/session` using the existing token to extend validity by 30 days.

---

## 4. `pplx login`

### Syntax
```bash
pplx login
```

Launches automated browser session extraction to retrieve the active `__Secure-next-auth.session-token`.

---

## 5. `pplx serve`

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
