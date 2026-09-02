---
name: pplx
description: Grounded web search, vertical search, and multi-model research via the `pplx` CLI. Use when the user asks to search the live web or look up recent facts, docs, or news; research patents or prior art; find academic papers on arXiv or PubMed; analyze stocks, earnings, or SEC filings; gather Reddit or community opinions; search with a specific model (Claude, GPT, Grok, Gemini, Sonar); inspect or refresh session credentials via `pplx info` / `pplx refresh`; bind a remote gateway via `pplx remote set <URL>`; or run a local OpenAI-compatible API gateway with `pplx serve`.
---

# Grounded Web Search & AI Research CLI (`pplx`)

Answers from `pplx` are grounded: synthesized Markdown followed by numbered source citations. Vertical searches additionally surface native identifiers — patent numbers, arXiv/DOI IDs, SEC filings.

## Routing

Match the query's domain to a vertical. Add `--model` only when the task needs deep reasoning.

| Query domain | Command |
|---|---|
| Patents, prior art, CPC classes | `pplx ask --patents "<query>"` |
| Papers, arXiv, PubMed, DOIs | `pplx ask --academic "<query>"` |
| Tickers, earnings, SEC filings | `pplx ask --finance "<query>"` |
| Reddit, forums, community opinions | `pplx ask --social "<query>"` |
| Everything else — general web | `pplx ask "<query>"` |

- Deep reasoning or coding questions: append `--model claude-3-7-sonnet` or `--model gpt-5.6`. Full alias table in [`references/models.md`](references/models.md).
- Quick fact lookup: append `--mode concise` (default `copilot` runs multi-step search).
- Further verticals — `health`, `writing` (pure reasoning, no web search), `wolfram`, `youtube`, `reddit` — via `pplx ask -V <vertical>`; scope of each in [`references/models.md`](references/models.md).

A search is done when the answer carries numbered citations; vertical answers also cite their native identifiers (shapes in [`references/examples.md`](references/examples.md)).

## Session recovery

Check status any time with `pplx info` (tier, session mode, token TTL). On `401 Unauthorized` or `Session expired`:

1. Run `pplx refresh` — renews the NextAuth session for +30 days.
2. Retry the failed `pplx ask`.
3. Still failing: run `pplx login` to re-extract the browser session, or `pplx remote set <URL>` to use a remote gateway instead.

Done when the retried query succeeds, or you report the failure with the remediation command.

## References

- Models, verticals, compound model names (`patents:claude-3-7-sonnet`): [`references/models.md`](references/models.md)
- Every command, flag, and gateway endpoint (`serve`, `remote`, `--raw`): [`references/commands.md`](references/commands.md)
- Recovery for auth failures, missing CLI, Pro-gated models, stream drops, offline remotes: [`references/troubleshooting.md`](references/troubleshooting.md)
- Tested query patterns and the identifiers each vertical returns: [`references/examples.md`](references/examples.md)
