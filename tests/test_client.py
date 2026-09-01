import json
from unittest.mock import MagicMock, patch

from perplexity_client import (
    PerplexityClient,
    resolve_model_name,
)


def test_resolve_model_name():
    assert resolve_model_name("claude-3-7-sonnet") == "claude50sonnet"
    assert resolve_model_name("gpt-4o") == "gpt56_terra"
    assert resolve_model_name("gpt-5.6") == "gpt56_terra"
    assert resolve_model_name("default") == "experimental"
    assert resolve_model_name("unknown-model-xyz") == "unknown-model-xyz"


def test_build_payload():
    client = PerplexityClient(auth_manager=MagicMock(get_valid_token=lambda: "mock_token"))
    payload = client._build_payload(
        query="What is python?",
        model="claude-3-7-sonnet",
        mode="copilot",
    )
    assert payload["query_str"] == "What is python?"
    assert payload["params"]["mode"] == "copilot"
    assert payload["params"]["model_preference"] == "claude50sonnet"
    assert payload["params"]["search_focus"] == "internet"


def test_perplexity_client_ask_mock():
    # Mock Perplexity SSE format
    sample_event = {
        "display_model": "claude50sonnet",
        "blocks": [
            {
                "intended_usage": "ask_text",
                "markdown_block": {
                    "answer": "Python is a programming language.",
                },
            },
            {
                "intended_usage": "sources",
                "sources_block": {
                    "sources": [
                        {"name": "Python Org", "url": "https://python.org"}
                    ]
                },
            },
        ],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_lines.return_value = [
        f"data: {json.dumps(sample_event)}",
        "",
    ]

    with patch("httpx.Client.stream") as mock_stream:
        mock_stream.return_value.__enter__.return_value = mock_resp
        client = PerplexityClient(auth_manager=MagicMock(get_valid_token=lambda: "mock_token"))
        res = client.ask("What is python?")
        assert res["answer"] == "Python is a programming language."
        assert len(res["sources"]) == 1
        assert res["sources"][0]["name"] == "Python Org"
