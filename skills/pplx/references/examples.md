# Practical Agent Usage Scenarios & Examples

This guide provides tested invocation patterns and prompt strategies for common developer, researcher, and AI agent workflows.

---

## Scenario 1: Patent & Prior Art Analysis (`--patents`)
When investigating intellectual property, patent numbers, assignees, or prior art:

```bash
pplx ask --patents "CRISPR-Cas9 base editing Liu David patent numbers and CPC subclass"
```

**Expected Result**:
- Searches Google Patents, USPTO, WIPO, EPO, and PubChem Patent databases.
- Identifies patent identifiers (e.g. `US9840699B2`, `WO2021030666A1`), claims, and assignee data.

---

## Scenario 2: Academic & Scientific Research (`--academic`)
When querying scientific literature, arXiv preprints, or medical studies:

```bash
pplx ask --academic "Mamba state space models visual representation arXiv papers"
```

**Expected Result**:
- Queries arXiv, PubMed, Semantic Scholar, IEEE, and Nature.
- Returns scholarly citations with direct arXiv IDs, DOI links, and author lists.

---

## Scenario 3: Financial Markets & SEC Filings (`--finance`)
When researching ticker financials, earnings reports, or analyst forecasts:

```bash
pplx ask --finance "NVDA Q2 FY27 gross margins, data center revenue, and analyst price targets"
```

**Expected Result**:
- Connects with Financial Modeling Prep, Fiscal.ai, Quartr transcripts, and SEC 10-Q filings.
- Returns GAAP/Non-GAAP gross margins, guidance ranges, and analyst consensus targets.

---

## Scenario 4: Social & Community Feedback (`--social`)
When gathering genuine user feedback, Reddit threads, and forum discussions:

```bash
pplx ask --social "FastAPI vs Litestar vs Sanic developer feedback in 2026"
```

---

## Scenario 5: High-Reasoning Code & Architecture Search
When combining specialized models with live search:

```bash
pplx ask --model claude-3-7-sonnet "FastAPI 0.115 Pydantic v2 migration error: 'BaseSettings' moved to 'pydantic-settings'"
```

---

## Scenario 6: OpenAI API Gateway Integration
Using Python OpenAI SDK with search verticals:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="none")

# Call Patents vertical with Claude 3.7
response = client.chat.completions.create(
    model="patents:claude-3-7-sonnet",
    messages=[{"role": "user", "content": "Top solid-state battery patents"}],
)
print(response.choices[0].message.content)
```
