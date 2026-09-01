# Practical Agent Usage Scenarios & Examples

This guide provides tested invocation patterns and prompt strategies for common developer and AI agent workflows.

---

## Scenario 1: Debugging Upstream Library Changes & Regressions
When encountering a runtime error or unexpected deprecation warning from third-party packages:

```bash
# Query recent discussions, GitHub issues, and release notes
pplx ask "FastAPI 0.115 Pydantic v2 migration error: 'BaseSettings' has been moved to 'pydantic-settings'"
```

**Expected Result**:
- Perplexity searches recent GitHub issues and release notes.
- Provides exact import fix: `from pydantic_settings import BaseSettings`.
- Supplies references to official docs.

---

## Scenario 2: Deep Technical Comparison & Architecture Selection
When deciding between technical architectures or modern frameworks:

```bash
# Leverage Claude 3.7 Sonnet for structured technical evaluation
pplx ask --model claude-3-7-sonnet "Compare Turbopack vs Vite in 2026 for large enterprise Next.js monorepos with benchmark numbers"
```

**Expected Result**:
- Multi-query synthesis across tech blogs and benchmark reports.
- Structured breakdown of build times, HMR latency, and plugin compatibility.

---

## Scenario 3: Quick Syntax & CLI Parameter Verification
When an agent needs to confirm an exact command-line syntax before running destructive commands:

```bash
# Concise mode for fast fact verification
pplx ask --mode concise "What is the exact uv command to install a tool from a local directory in editable mode?"
```

**Expected Result**:
- Direct answer: `uv tool install --editable .`
- Immediate execution without conversational fluff.

---

## Scenario 4: Investigating Recent CVEs & Security Advisories
When auditing dependencies for newly published zero-days or vulnerabilities:

```bash
pplx ask "CVE-2026-XXXX latest impact, affected versions, and mitigation patch"
```

**Expected Result**:
- Direct links to NVD, vendor security bulletins, and patch commit hashes.

---

## Scenario 5: Scripting & Output Redirection
When embedding `pplx` into automated scripts or CI/CD pipelines:

```bash
# Save grounded research directly to a Markdown report
pplx ask "Latest Python PEPs accepted in 2026" > /tmp/pep-report.md

# Verify exit status in bash scripts
if pplx ask --mode concise "Is Redis 8 released?" | grep -i "yes"; then
    echo "Redis 8 is out"
fi
```
