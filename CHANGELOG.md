# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-09-02

### Fixed
- **Security**: `/auth/info` no longer returns `session_token`, `org_token`, or browser `cookies` (redacted as `***configured***`); API key comparison now constant-time (`secrets.compare_digest`); CORS wildcard origins no longer claim `allow_credentials`.
- **Security**: credentials file is written with `0600` permissions.
- **Server**: non-streaming `/v1/chat/completions`, `/search`, and `/auth/refresh` no longer block the event loop (async client / threadpool); `/health` stays responsive during long searches.
- **Server**: self-loop guard — if a gateway process is (mis)configured with a `remote_url` pointing at its own port, requests are rejected immediately with `508 Loop Detected` instead of recursing into itself; `pplx serve` refuses to start and a startup `CRITICAL` warning is logged when the misconfiguration is detectable.
- **Server**: SSE `data: [DONE]` is emitted after the normal/errored completion instead of `yield` inside `finally` (client-disconnect cancellation no longer corrupts stream teardown).
- **Client**: 401 refresh-retry is capped at one attempt (previously unbounded recursion on persistent 401).
- **Client**: SSE parser accepts both `data: ` and `data:` prefixes.
- **Client**: org cookie parsing keeps values containing `=` (base64 padding).
- **Auth**: browser re-extraction failure during refresh no longer masks the existing valid token (env-token Docker deployments keep working).
- **Config**: `default_model` and `timeout` are now actually consumed by the CLI and server (previously stored but ignored); `PERPLEXITY_TIMEOUT` env var supported.
- **Docker**: container `CMD` respects the `PORT` environment variable (HEALTHCHECK already did).
- **Docs**: `perplexity_config` module docstring now matches the real precedence order.

## [0.2.0] - 2026-03-02

### Added
- **Specialized Search Verticals & Domains**:
  - **Perplexity Patents (`https://www.perplexity.ai/patents`)**: Global patent database search, prior art analysis, CPC/IPC classifications, claims, and assignee extraction via `--patents` or `patents:...`.
  - **Perplexity Academic (`https://www.perplexity.ai/academic`)**: Research paper search routing directly to arXiv, PubMed, Semantic Scholar, IEEE, JSTOR, and peer-reviewed journals with DOI citations via `--academic` or `academic:...`.
  - **Perplexity Finance (`https://www.perplexity.ai/finance`)**: Institutional market data, SEC filings, earnings conference call transcripts, gross margins, and analyst consensus via `--finance` or `finance:...`.
  - **Social & Discussions**: Real-world community feedback, Reddit threads, and forum discussions via `--social` or `social:...`.
  - **Health & Clinical**: Evidence-based clinical guidelines and medical literature via `-V health`.
  - **Writing / Wolfram / YouTube / Reddit**: Pure text generation, computational math, and targeted media focus modes.
- **OpenAI Gateway Compound Model Syntax**:
  - Support compound model naming in `/v1/chat/completions` (e.g. `patents:claude-3-7-sonnet`, `academic:sonar`, `finance:gpt-5.6`), allowing any standard OpenAI client to select search verticals directly in the `model` parameter.
  - New `GET /verticals` API endpoint for discovering supported search domains and metadata.
  - Enhanced `GET /search` and `POST /search` endpoint with `vertical` parameter support.
- **Enhanced CLI Experience (`pplx`)**:
  - Added `-V`, `--vertical`, `--patents`, `--academic`, `--finance`, `--social` shortcut flags.
  - Colorized search vertical badges in terminal live stream.
  - Added Search Verticals catalog table to `pplx models`.
- **Comprehensive Unit & Integration Test Suite**:
  - Added `tests/test_verticals.py` covering vertical resolution, compound model parsing, remote forwarding, and gateway routing (48 passing tests).

## [0.1.0] - 2026-09-01

### Added
- **Agent Skills Support**: Added standard `skills/pplx/SKILL.md` conforming to the open Agent Skills format and `writing-great-skills` guidelines.
- **Claude Code Marketplace**: Added `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` for one-click installation in Claude Code.
- **OpenAI Codex Marketplace**: Added `.agents/plugins/marketplace.json` and `.codex-plugin/plugin.json` for native Codex CLI plugin integration.
- **Progressive References**: Added `references/commands.md`, `references/models.md`, and `references/troubleshooting.md` for fast, lightweight context retrieval.
- **CLI Commands**: Full support for `pplx ask` (search), `pplx info` (status), `pplx refresh` (token extension), `pplx login` (browser SSO extraction), and `pplx serve` (OpenAI gateway).
- **One-Click Installer**: Added `install.sh` for streamlined environment and symlink setup.
- **Agent Documentation**: Added `AGENTS.md` specifying agent workflows and directory taxonomy.
