---
name: pplx
description: Grounded web search, real-time citation extraction, multi-model AI reasoning, and session gateway via the `pplx` CLI. Use when the user asks to search live web data, look up recent facts or library documentation, conduct multi-model research (Sonar, Claude 3.7 Sonnet, GPT-5.6, Grok 4.6, Gemini 3.7), inspect or refresh session credentials via `pplx info` / `pplx refresh`, or run the local OpenAI-compatible API gateway with `pplx serve`.
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

# 5. Renew session token for 30 days
pplx refresh
```

## Deterministic Execution Process

Follow this sequence for every search request:

### Step 1: Probe (Model & Mode Selection)
Select the execution tier matching the task complexity:
- **Fast / General Search**: Use default model (`sonar` / `copilot`).
- **Code, Architecture & Refactoring**: Use `--model claude-3-7-sonnet`.
- **Complex Reasoning & Analysis**: Use `--model gpt-5.6` or `--model grok-4.6`.
- **Direct Fact Retrieval**: Use `--mode concise`.

*Completion criterion*: Model alias and search mode determined before command dispatch.

### Step 2: Stream (CLI Execution)
Dispatch the search query non-interactively:
```bash
pplx ask [--model <alias>] [--mode <mode>] "<query>"
```
*Completion criterion*: Process exits with code `0` and yields synthesized text containing bracketed source indices (`[1]`, `[2]`).

### Step 3: Ground (Citation Preservation)
Retain all citation brackets `[1][2]` in the final synthesized output. Include the corresponding source links listed at the bottom of the `pplx` output.

*Completion criterion*: Every factual claim in the synthesized answer is backed by its numbered citation reference.

### Step 4: Recover (Auth & Drift Fallback)
If the CLI exits with non-zero or emits `401 Unauthorized`:
1. Execute `pplx refresh` immediately to renew the NextAuth session token.
2. Retry the original `pplx ask` command once.
3. If refresh fails, inform the user to run `pplx login`.

*Completion criterion*: Query completes successfully on retry, or explicit authentication failure reported with remediation command.

---

## Core Command Matrix

| Subcommand | Alias | Primary Purpose | Key Flags |
|---|---|---|---|
| `ask` | `search`, `s` | Live web search with inline citations | `--model <name>`, `--mode <mode>`, `--raw` |
| `info` | - | Display session status, token TTL, Pro tier | `-h` |
| `refresh` | - | Renew session token (+30 days) via NextAuth API | `-h` |
| `login` | - | Extract session cookies from Chrome/Edge via browser | `-h` |
| `serve` | - | Launch OpenAI-compatible `/v1/chat/completions` server | `--host`, `--port` |

---

## Failure Modes & Recovery

| Symptom | Cause | Recovery |
|---|---|---|
| `401 Unauthorized` / Session expired | NextAuth cookie TTL lapsed | Run `pplx refresh` and retry; if persistent, run `pplx login` |
| `Command not found: pplx` | CLI binary missing from `PATH` | Run `export PATH="$HOME/.local/bin:$PATH"` or `./install.sh` |
| `Model requires Pro subscription` | Account lacks Pro entitlement | Omit `--model` flag to use default search tier |
| SSE Stream Disconnect | Transient network drop | Re-run `pplx ask` with a concise query prompt |

---

## Progressive References

- When choosing specialized models, reasoning tiers, or search modes, read [`references/models.md`](references/models.md).
- When inspecting CLI syntax, debugging flags, or exit codes, read [`references/commands.md`](references/commands.md).
- When resolving authentication errors, token refresh failures, or browser extraction, read [`references/troubleshooting.md`](references/troubleshooting.md).
- When looking for tested query patterns across debugging, architecture comparison, or scripting, read [`references/examples.md`](references/examples.md).
