# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take the security of Perplexity Search2API seriously. If you discover a security vulnerability, please **DO NOT** open a public issue.

Instead, please report security issues privately to the repository maintainers via GitHub Security Advisories or by emailing the project maintainer.

### What to include in your report:
- A clear description of the vulnerability.
- Steps or proof-of-concept scripts to reproduce the issue.
- Potential impact of the vulnerability.
- Suggested mitigations or fixes (if any).

---

## ⚠️ Important Credential & Token Protection Guidelines

1. **Local Session Files**:
   `perplexity-search2api` stores NextAuth session tokens in `.perplexity_session.json` or `~/.perplexity_session.json`. These files contain authentication secrets and are excluded via `.gitignore`.
2. **Never Check-In Tokens**:
   Never commit `.perplexity_session.json` or paste real session tokens into public GitHub issues, discussions, or pull requests.
3. **Network Security**:
   If exposing the FastAPI service (`server.py`) publicly or across untrusted networks, always:
   - Configure `API_KEY` in your environment or `.env` file to require Bearer authentication.
   - Run behind a secure reverse proxy with TLS (HTTPS) such as Nginx, Caddy, or Cloudflare Tunnel.
