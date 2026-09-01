# Supported Models & Aliases

The `pplx` CLI maps user-friendly model aliases directly to Perplexity's backend engine preferences.

## Model Catalog

| Model Alias | Backend Identifier | Optimization / Strengths |
|---|---|---|
| `default` / `sonar` / `sonar-pro` | `experimental` / `pplx_pro` | Real-time web index search, breaking news, rapid synthesis |
| `claude-3-7-sonnet` / `claude-3.7-sonnet` | `claude50sonnet` | Deep code architecture, refactoring, agent workflows |
| `claude-opus` / `claude-3-opus` | `claude50opus` | Extended analytical writing and high-context comprehension |
| `gpt-5.6` / `gpt-5.6-terra` | `gpt56_terra` | OpenAI GPT-5.6 deep reasoning engine with live search |
| `gpt-5.6-instant` / `gpt-5.6-sol` | `gpt56_sol` | High-throughput quick responses |
| `grok-4.6` / `grok-4` / `grok-2` | `grok46low` | Current event analysis, alternative perspectives |
| `gemini-3.7-flash` | `gemini37flash` | Rapid multi-modal search and synthesis |
| `gemini-3.1-pro` | `gemini31pro_high` | Broad cross-domain academic and technical reasoning |
| `glm-5.3` / `glm-5.3-thinking` | `glm_5_3_thinking` | Deep bilingual (Chinese/English) technical reasoning |
| `kimi-k3` / `kimi-k3-thinking` | `kimik3thinking` | Long-context Chinese search and document analysis |
| `nemotron-3` | `nv_nemotron_3_ultra` | NVIDIA Nemotron 3 Ultra enterprise reasoning |

## Search Modes (`--mode`)

- **`copilot`** *(Default)*: Full multi-step query planning, searching across 10-30 web sources, generating rich citations.
- **`concise`**: Low-latency direct extraction without multi-pass web chaining.
