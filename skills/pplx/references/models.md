# Supported Models & Search Verticals

The `pplx` CLI and OpenAI gateway map user-friendly model aliases and search verticals directly to Perplexity's backend engine preferences.

## 1. AI Reasoning Models

| Model Alias | Backend Identifier | Optimization / Strengths |
|---|---|---|
| `default` / `sonar` / `sonar-pro` | `experimental` / `pplx_pro` | Real-time web index search, breaking news, rapid synthesis |
| `claude-3-7-sonnet` / `claude-3.7-sonnet` | `claude50sonnet` | Deep code architecture, refactoring, agent workflows, thinking chain |
| `claude-opus` / `claude-3-opus` | `claude50opus` | Extended analytical writing and high-context comprehension |
| `gpt-5.6` / `gpt-5.6-terra` | `gpt56_terra` | OpenAI GPT-5.6 deep reasoning engine with live search |
| `gpt-5.6-instant` / `gpt-5.6-sol` | `gpt56_sol` | High-throughput quick responses |
| `grok-4.6` / `grok-4` / `grok-2` | `grok46low` | Current event analysis, alternative perspectives |
| `gemini-3.7-flash` | `gemini37flash` | Rapid multi-modal search and synthesis |
| `gemini-3.1-pro` | `gemini31pro_high` | Broad cross-domain academic and technical reasoning |
| `glm-5.3` / `glm-5.3-thinking` | `glm_5_3_thinking` | Deep bilingual (Chinese/English) technical reasoning |
| `kimi-k3` / `kimi-k3-thinking` | `kimik3thinking` | Long-context Chinese search and document analysis |
| `nemotron-3` | `nv_nemotron_3_ultra` | NVIDIA Nemotron 3 Ultra enterprise reasoning |

---

## 2. Search Verticals & Focus Domains

Search verticals route your query through specialized data pipelines and knowledge corpuses.

| Vertical (`-V`) | Shortcut Flag | Web URL | Data Sources & Scope | Example Prompt |
|---|---|---|---|---|
| `web` *(Default)* | - | `https://www.perplexity.ai/` | Entire live web index, news, docs | `pplx ask "Quantum computing breakthrough"` |
| `patents` | `--patents` | `https://www.perplexity.ai/patents` | Global patent databases (Google Patents, USPTO, EPO, WIPO, PubChem Patent), CPC classifications, prior art | `pplx ask --patents "Solid state battery patents"` |
| `academic` | `--academic` | `https://www.perplexity.ai/academic` | Peer-reviewed journals, arXiv, PubMed, Semantic Scholar, IEEE, JSTOR, DOI citations | `pplx ask --academic "Mamba state space models arXiv"` |
| `finance` | `--finance` | `https://www.perplexity.ai/finance` | Financial Modeling Prep, Fiscal.ai, Quartr earnings transcripts, SEC 10-K/10-Q filings, S&P Global, stock tickers | `pplx ask --finance "NVDA gross margins & analyst targets"` |
| `social` | `--social` | `https://www.perplexity.ai/` | Reddit, Twitter/X, developer forums, community opinions | `pplx ask --social "FastAPI vs Litestar real world feedback"` |
| `health` | `-V health` | `https://www.perplexity.ai/` | Clinical guidelines, medical literature, health research | `pplx ask -V health "GLP-1 receptor agonist clinical trials"` |
| `writing` | `-V writing` | `https://www.perplexity.ai/` | Pure model reasoning without triggering web search | `pplx ask -V writing "Draft an executive summary"` |
| `wolfram` | `-V wolfram` | `https://www.perplexity.ai/` | Computational knowledge, mathematics, physical constants | `pplx ask -V wolfram "integrate x^2 * sin(x)"` |
| `youtube` | `-V youtube` | `https://www.perplexity.ai/` | YouTube videos, video timestamps, and spoken transcripts | `pplx ask -V youtube "FastAPI advanced tutorial 2026"` |
| `reddit` | `-V reddit` | `https://www.perplexity.ai/` | Targeted Subreddit threads, user comments & discussions | `pplx ask -V reddit "best mechanical keyboard switches"` |

---

## 3. OpenAI Gateway Compound Model Syntax

When using the Search2API server (`pplx serve` or remote endpoint), standard OpenAI API clients can select both the AI reasoning model and search vertical directly in the `model` parameter using the prefix syntax:

- `patents:claude-3-7-sonnet` — Run Claude 3.7 Sonnet on Perplexity Patents
- `academic:sonar` — Run Sonar on Perplexity Academic papers
- `finance:gpt-5.6` — Run GPT-5.6 on Perplexity Finance & market data
- `social:sonar` — Run Sonar on Social / Reddit discussions
- `patents` / `academic` / `finance` — Run default model on target vertical

Alternatively, pass `"vertical": "patents"` in the JSON request body or `X-Perplexity-Vertical: patents` in the HTTP header.

---

## 4. Search Modes (`--mode`)

- **`copilot`** *(Default)*: Full multi-step query planning, searching across 10-30 web sources, generating rich citations.
- **`concise`**: Low-latency direct extraction without multi-pass web chaining.
