---
name: pplx
description: Grounded web search, specialized vertical search (Patents, Academic, Finance, Social), real-time citation extraction, multi-model AI reasoning, and session gateway via the `pplx` CLI. Use when the user asks to search live web data, research patents, explore academic papers/arXiv/PubMed, analyze financial markets and SEC filings, look up recent facts or library documentation, conduct multi-model research (Sonar, Claude 3.7 Sonnet, GPT-5.6, Grok 4.6, Gemini 3.7), inspect or refresh session credentials via `pplx info` / `pplx refresh`, bind remote gateway endpoints via `pplx remote set <URL>`, or run the local OpenAI-compatible API gateway with `pplx serve`.
---

# Grounded Web Search & AI Research CLI (`pplx`)

The `pplx` skill executes grounded web search, specialized vertical research (Patents, Academic, Finance, Social), multi-model reasoning, and session maintenance through the deterministic `pplx` command-line interface.

## Quick Invocations

```bash
# 1. Standard web search with real-time web citations
pplx ask "<query>"

# 2. Specialized vertical search domains
pplx ask --patents "<patent / prior art query>"     # Perplexity Patents (https://www.perplexity.ai/patents)
pplx ask --academic "<paper / arXiv / PubMed query>" # Perplexity Academic (https://www.perplexity.ai/academic)
pplx ask --finance "<stock / earnings / SEC query>" # Perplexity Finance (https://www.perplexity.ai/finance)
pplx ask --social "<community discussion query>"     # Social & Reddit discussions

# 3. High-reasoning search via specialized model
pplx ask --model claude-3-7-sonnet "<query>"
pplx ask --patents --model claude-3-7-sonnet "Solid-state battery electrolyte patents"

# 4. Fast direct fact lookup
pplx ask --mode concise "<query>"

# 5. Check credentials and token validity TTL
pplx info

# 6. Refresh session token before expiry
pplx refresh
```

---

## Autonomous Decision Flow for AI Agents

```
User Query Received
       │
       ▼
Is it domain-specialized?
 ├─ Patent / Prior Art / CPC Classification ──► `pplx ask --patents "<query>"`
 ├─ Academic / arXiv / PubMed / Research   ──► `pplx ask --academic "<query>"`
 ├─ Finance / Tickers / Earnings / SEC    ──► `pplx ask --finance "<query>"`
 ├─ Social / Community Opinions / Reddit  ──► `pplx ask --social "<query>"`
 └─ General Web / Facts / Docs / News     ──► `pplx ask "<query>"`
       │
       ▼
Requires High Reasoning / Coding?
 ├─ Yes ──► Add `--model claude-3-7-sonnet` or `--model gpt-5.6`
 └─ No  ──► Default tier (`experimental` / `sonar`)
```

---

## Core Execution Workflows

### Workflow 1: Specialized Academic & Patent Research
1. Execute query on target vertical:
   ```bash
   pplx ask --academic "Mamba state space models visual representation arXiv"
   # or
   pplx ask --patents "CRISPR-Cas9 base editing Liu David"
   ```
2. Extract direct DOI, arXiv identifiers, patent numbers (`US...`, `WO...`), or SEC filing citations from the synthesized response.

### Workflow 2: Financial & Market Intelligence
1. Execute query on Finance vertical:
   ```bash
   pplx ask --finance "NVDA Q2 FY27 revenue gross margins analyst consensus"
   ```
2. Extract institutional-grade metrics, earnings call commentary, and price targets.

### Workflow 3: Session Credentials Lifecycle
When observing authentication failure (`401` or missing token):
1. Execute `pplx refresh`.
2. Retry the failed `pplx ask` query.
3. If refresh fails, inform the user to run `pplx login` or connect via `pplx remote set <URL>`.
*Completion criterion*: Query completes successfully on retry, or explicit authentication failure reported with remediation command.

---

## CLI Command Summary

| Command | Subcommand / Target | Primary Function | Key Flags |
|---|---|---|---|
| `ask` | `<query>` | Stream live grounded search results & citations | `--vertical`, `--patents`, `--academic`, `--finance`, `--social`, `--model`, `--mode`, `--raw` |
| `remote` | `set <URL>` / `show` / `unset` / `test` | Configure remote gateway to avoid local credential storage | `--api-key`, `--default-model` |
| `models` | - | List AI models, aliases, and search verticals | `--remote`, `--api-key` |
| `info` | - | Display account Pro status, session mode, and TTL | `--local`, `-h` |
| `refresh` | - | Extend NextAuth session (+30 days) | `--local`, `-h` |
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

- When choosing specialized models, search verticals, or compound model syntax, read [`references/models.md`](references/models.md).
- When inspecting CLI syntax, debugging flags, or exit codes, read [`references/commands.md`](references/commands.md).
- When resolving authentication errors, token refresh failures, or browser extraction, read [`references/troubleshooting.md`](references/troubleshooting.md).
- When looking for tested query patterns across debugging, patent analysis, academic research, or financial modeling, read [`references/examples.md`](references/examples.md).
