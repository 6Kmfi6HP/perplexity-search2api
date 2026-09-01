# Troubleshooting & Recovery Guide

## 1. Authentication Issues

### Symptom: `401 Unauthorized` or `Session expired`
**Cause**: The local NextAuth session token in `~/.perplexity_session.json` has expired or been revoked.

**Resolution Steps**:
1. Run `pplx refresh` to renew the token.
2. If `pplx refresh` returns an error, run `pplx login` to automatically re-extract the active browser session.
3. Alternatively, export `PERPLEXITY_SESSION_TOKEN="<your-token>"` in your environment.

---

## 2. CLI Execution Issues

### Symptom: `command not found: pplx`
**Cause**: The Python bin directory is not in your shell's `PATH`.

**Resolution Steps**:
1. Check `which pplx` or `uv run pplx`.
2. Add `~/.local/bin` to your `PATH`:
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   ```
3. Or reinstall using `uv tool install --editable .` from this repo directory.

---

## 3. Rate Limits & Pro Status

### Symptom: `Model requires Pro subscription`
**Cause**: High-tier models (like Claude 3.7 Sonnet or GPT-4.5) require an active Perplexity Pro account.

**Resolution Steps**:
1. Check subscription status using `pplx info`.
2. Omit the `--model` flag to use the default search engine, which works on all authenticated accounts.
