# Supported Models & Search Verticals

Model aliases and search verticals for the `pplx` CLI and OpenAI gateway, mapped to Perplexity's backend engines.

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

## 2. Search Verticals

Verticals route a query through a specialized data pipeline and knowledge corpus. The four specialized domains have their own Perplexity sites; the rest run on the main index with a focused source selection.

| Vertical (`-V`) | Shortcut Flag | Web URL | Data Sources & Scope |
|---|---|---|---|
| `web` *(Default)* | - | `https://www.perplexity.ai/` | Entire live web index, news, docs |
| `patents` | `--patents` | `https://www.perplexity.ai/patents` | Global patent databases (Google Patents, USPTO, EPO, WIPO, PubChem Patent), CPC classifications, prior art |
| `academic` | `--academic` | `https://www.perplexity.ai/academic` | Peer-reviewed journals, arXiv, PubMed, Semantic Scholar, IEEE, JSTOR, DOI citations |
| `finance` | `--finance` | `https://www.perplexity.ai/finance` | Financial Modeling Prep, Fiscal.ai, Quartr earnings transcripts, SEC 10-K/10-Q filings, S&P Global, stock tickers |
| `social` | `--social` | `https://www.perplexity.ai/` | Reddit, Twitter/X, developer forums, community opinions |
| `health` | - | `https://www.perplexity.ai/` | Clinical guidelines, medical literature, health research |
| `writing` | - | `https://www.perplexity.ai/` | Pure model reasoning without triggering web search |
| `wolfram` | - | `https://www.perplexity.ai/` | Computational knowledge, mathematics, physical constants |
| `youtube` | - | `https://www.perplexity.ai/` | YouTube videos, video timestamps, and spoken transcripts |
| `reddit` | - | `https://www.perplexity.ai/` | Targeted subreddit threads, user comments & discussions |

## 3. OpenAI Gateway Compound Model Syntax

When using the Search2API server (`pplx serve` or a remote endpoint), OpenAI API clients select both model and vertical in the `model` parameter:

- `patents:claude-3-7-sonnet` — Claude 3.7 Sonnet on Perplexity Patents
- `academic:sonar` — Sonar on Perplexity Academic
- `finance:gpt-5.6` — GPT-5.6 on Perplexity Finance
- `social:sonar` — Sonar on Social / Reddit discussions
- `patents` / `academic` / `finance` — default model on that vertical

Alternatively, pass `"vertical": "patents"` in the JSON request body or `X-Perplexity-Vertical: patents` in the HTTP header.
