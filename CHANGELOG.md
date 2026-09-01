# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-01

### Added
- **Agent Skills Support**: Added standard `skills/pplx/SKILL.md` conforming to the open Agent Skills format and `writing-great-skills` guidelines.
- **Claude Code Marketplace**: Added `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` for one-click installation in Claude Code.
- **OpenAI Codex Marketplace**: Added `.agents/plugins/marketplace.json` and `.codex-plugin/plugin.json` for native Codex CLI plugin integration.
- **Progressive References**: Added `references/commands.md`, `references/models.md`, and `references/troubleshooting.md` for fast, lightweight context retrieval.
- **CLI Commands**: Full support for `pplx ask` (search), `pplx info` (status), `pplx refresh` (token extension), `pplx login` (browser SSO extraction), and `pplx serve` (OpenAI gateway).
- **One-Click Installer**: Added `install.sh` for streamlined environment and symlink setup.
- **Agent Documentation**: Added `AGENTS.md` specifying agent workflows and directory taxonomy.
