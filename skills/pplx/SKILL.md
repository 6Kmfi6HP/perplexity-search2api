---
name: pplx
description: Grounded web search, real-time citation extraction, multi-model AI reasoning, and session gateway via the `pplx` CLI. Use when the user asks to search live web data, look up recent facts or library documentation, conduct multi-model research (Sonar, Claude 3.7 Sonnet, GPT-5.6, Grok 4.6, Gemini 3.7), inspect or refresh session credentials via `pplx info` / `pplx refresh`, bind remote gateway endpoints via `pplx remote set <URL>`, or run the local OpenAI-compatible API gateway with `pplx serve`.
---

# Grounded Web Search & AI Research CLI (`pplx`)

The `pplx` skill executes grounded web search, multi-model reasoning, and session maintenance through the deterministic `pplx` command-line interface.

## Quick Invocations

```bash
# 1. Standard search with real-time web citations
pplx ask "<query>"

# 2. High-reasoning search via specialized model
pplx ask --model claude-3-7-sonnet "<query>"

# 3. Fast direct fact lookup
pplx ask --mode concise "<query>"

# 4. Check credentials and token validity TTL
pplx info

# 5. Bind remote Search2API server (avoids storing credentials locally)
pplx remote set http://<host>:<port>/

# 6. List available reasoning and search models
pplx models

# 7. Refresh session credentials (+30 days sliding window)
pplx refresh
```

## Deterministic Execution Workflows

### 1. Grounded Search Query
Execute `pplx ask "<query>"`.
*Success criterion*: Output contains Markdown response followed by numbered web references with source URLs.

### 2. High-Reasoning & Complex Coding Research
Execute `pplx ask --model <model> "<query>"` with reasoning-focused models (`claude-3-7-sonnet`, `gpt-5.6`, `grok-4.6`, `gemini-3.7-flash`).
*Success criterion*: In-depth technical synthesis returned with verified web citations.

### 3. Remote Server Connection (Zero Local Credentials)
Execute `pplx remote set <URL>` (e.g. `pplx remote set http://host:8000/`) or set `PERPLEXITY_BASE_URL` in `.env` / `~/.perplexity_config.json`.
*Success criterion*: All CLI commands directly call the remote endpoint without needing browser login.

### 4. Authentication Maintenance
When observing authentication failure (`401` or missing token):
1. Run `pplx refresh` to trigger NextAuth token renewal.
2. Retry the failed `pplx ask` query.
3. If refresh fails, inform the user to run `pplx login` or connect via `pplx remote set <URL>`.
*Completion criterion*: Query completes successfully on retry, or explicit authentication failure reported with remediation command.

---

## Command Matrix

| CLI Action | Alias | Core Purpose | Critical Flags |
|---|---|---|---|
| `ask` | `search`, `s` | Execute grounded live search | `--model`, `--mode`, `--remote`, `--api-key`, `--raw` |
| `remote` | - | Manage remote API endpoints | `set`, `show`, `test`, `unset` |
| `models` | - | List available models on remote or local | `--remote`, `--api-key` |
| `info` | - | Display authentication status & token TTL | `--local`, `--remote`, `--api-key` |
| `refresh` | - | Renew session token (+30 days) via NextAuth API | `--local`, `--remote`, `-h` |
| `login` | - | Extract session cookies from Chrome/Edge via browser | `--local`, `-h` |
| `serve` | - | Launch OpenAI-compatible `/v1/chat/completions` server | `--host`, `--port` |

---

## Failure Modes & Recovery

| Symptom | Cause | Recovery |
|---|---|---|
| `401 Unauthorized` / Session expired | NextAuth cookie TTL lapsed | Run `pplx refresh` and retry; if persistent, run `pplx login` or configure `pplx remote set <URL>` |
| `Command not found: pplx` | CLI binary missing from `PATH` | Run `export PATH="$HOME/.local/bin:$PATH"` or `./install.sh` |
| `Model requires Pro subscription` | Account lacks Pro entitlement | Omit `--model` flag to use default search tier |
| SSE Stream Disconnect | Transient network drop | Re-run `pplx ask` with a concise query prompt |
| Remote Server Offline | Host unreachable or port mismatch | Run `pplx remote test <URL>` or verify remote `pplx serve` instance |

---

## Progressive References

- When choosing specialized models, reasoning tiers, or search modes, read [`references/models.md`](references/models.md).
- When inspecting CLI syntax, debugging flags, or exit codes, read [`references/commands.md`](references/commands.md).
- When resolving authentication errors, token refresh failures, or browser extraction, read [`references/troubleshooting.md`](references/troubleshooting.md).
- When looking for tested query patterns across debugging, architecture comparison, or scripting, read [`references/examples.md`](references/examples.md).
