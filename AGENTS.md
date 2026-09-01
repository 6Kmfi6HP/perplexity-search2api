# AGENTS.md — Perplexity Search2API & Agent Skills Guide

## Overview

This repository provides both an OpenAI-compatible API gateway and a CLI tool (`pplx`), alongside a production-ready Agent Skill designed for **Claude Code** and **OpenAI Codex** plugin marketplaces.

## Marketplace Installation

### Skills.sh (Vercel Skills CLI)
```bash
# Install via npx skills CLI
npx skills add 6Kmfi6HP/perplexity-search2api
```

### Codex CLI (v0.117.0+)
```bash
# Add this marketplace catalog
codex plugin marketplace add 6Kmfi6HP/perplexity-search2api

# Install the pplx plugin/skill
codex plugin add pplx@perplexity-search2api
```

### Claude Code
```bash
# Add marketplace
claude plugin marketplace add 6Kmfi6HP/perplexity-search2api

# Install plugin
claude plugin install pplx
```

### Local / Manual Installation
```bash
./install.sh
```

---

## Agent Invocation Pattern

When an AI agent needs to perform grounded web searches or deep research:

1. **Verify Authentication**:
   ```bash
   pplx info
   ```
2. **Execute Grounded Web Search**:
   ```bash
   pplx ask "<query>"
   ```
3. **Execute High-Reasoning Search**:
   ```bash
   pplx ask --model claude-3-7-sonnet "<query>"
   ```
4. **Handle Token Expiry**:
   If an authentication failure occurs, trigger:
   ```bash
   pplx refresh
   ```
   and retry the request.

---

## File Layout & Roles

| Path | Purpose |
|---|---|
| `.agents/plugins/marketplace.json` | Codex / Agent Plugins 1.0 marketplace catalog declaration |
| `.codex-plugin/plugin.json` | OpenAI Codex native plugin manifest |
| `.claude-plugin/plugin.json` | Claude Code plugin manifest |
| `.claude-plugin/marketplace.json` | Claude Code marketplace catalog declaration |
| `skills/pplx/SKILL.md` | Core Agent Skill instructions, triggers, and execution workflows |
| `skills/pplx/agents/openai.yaml` | UI/Codex agent metadata |
| `skills/pplx/references/` | Progressive disclosure reference docs (`commands.md`, `models.md`, `troubleshooting.md`) |
| `cli.py` | Implementation of the `pplx` command-line interface |
| `perplexity_client.py` | Internal client interacting with Perplexity backend & SSE stream |
| `perplexity_auth.py` | NextAuth session token management and browser cookie extraction |
| `server.py` | FastAPI OpenAI-compatible server implementation |
