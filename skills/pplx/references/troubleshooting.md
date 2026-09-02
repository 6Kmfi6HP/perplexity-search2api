# Troubleshooting & Recovery Guide

## 1. Authentication Issues

### Symptom: `401 Unauthorized` or `Session expired`
**Cause**: The local NextAuth session token in `~/.perplexity_session.json` has expired or been revoked.

**Resolution Steps**:
1. Run `pplx refresh` to renew the token.
2. If `pplx refresh` returns an error, run `pplx login` to re-extract the active browser session.
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
**Cause**: High-tier models (e.g. Claude 3.7 Sonnet, GPT-5.6) require an active Perplexity Pro account.

**Resolution Steps**:
1. Check subscription status using `pplx info`.
2. Omit the `--model` flag to use the default search engine, which works on all authenticated accounts.

---

## 4. Stream Interruptions

### Symptom: SSE stream drops mid-answer or the command hangs
**Cause**: Transient network drop between the CLI and Perplexity.

**Resolution Steps**:
1. Re-run the `pplx ask` query, optionally with `--mode concise` for a shorter single-pass search.
2. To inspect the raw event stream, re-run with `--raw`.

---

## 5. Remote Gateway Issues

### Symptom: Remote requests fail or hang
**Cause**: The remote endpoint is unreachable, the port is wrong, or the gateway process is down.

**Resolution Steps**:
1. Run `pplx remote test` to check connectivity to the configured endpoint.
2. Run `pplx remote show` to confirm the URL is the one you expect.
3. On the remote host, verify the gateway is running (`pplx serve`) and check `GET /health`.
4. To fall back to local credentials, run `pplx remote unset`.
