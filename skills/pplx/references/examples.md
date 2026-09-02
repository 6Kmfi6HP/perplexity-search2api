# Query Patterns & Expected Results

Tested prompts per vertical and the identifiers a grounded answer should contain. Data sources per vertical are listed in [models.md](models.md).

---

## Patent & Prior Art Analysis (`--patents`)

```bash
pplx ask --patents "CRISPR-Cas9 base editing Liu David patent numbers and CPC subclass"
```

**Expected result**: patent identifiers (e.g. `US9840699B2`, `WO2021030666A1`), claims, assignees, and CPC subclasses.

---

## Academic & Scientific Research (`--academic`)

```bash
pplx ask --academic "Mamba state space models visual representation arXiv papers"
```

**Expected result**: direct arXiv IDs, DOI links, venues, and author lists.

---

## Financial Markets & SEC Filings (`--finance`)

```bash
pplx ask --finance "NVDA Q2 FY27 gross margins, data center revenue, and analyst price targets"
```

**Expected result**: GAAP/non-GAAP margins, guidance ranges, and analyst consensus targets tied to SEC 10-K/10-Q filings and earnings transcripts.

---

## Social & Community Feedback (`--social`)

```bash
pplx ask --social "FastAPI vs Litestar vs Sanic developer feedback in 2026"
```

**Expected result**: named Reddit threads, forum posts, and user opinions with links.

---

## High-Reasoning Code & Architecture Search

Combine any vertical flag with a specialized model:

```bash
pplx ask --model claude-3-7-sonnet "FastAPI 0.115 Pydantic v2 migration error: 'BaseSettings' moved to 'pydantic-settings'"
```

---

## OpenAI API Gateway Integration

Using the Python OpenAI SDK against `pplx serve` or a remote endpoint, selecting vertical and model via the compound `model` name:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="none")

# Patents vertical with Claude 3.7
response = client.chat.completions.create(
    model="patents:claude-3-7-sonnet",
    messages=[{"role": "user", "content": "Top solid-state battery patents"}],
)
print(response.choices[0].message.content)
```
