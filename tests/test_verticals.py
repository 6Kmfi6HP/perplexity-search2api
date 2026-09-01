from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from perplexity_client import (
    SEARCH_VERTICALS,
    VERTICAL_ALIASES,
    PerplexityClient,
    RemotePerplexityClient,
    parse_model_and_vertical,
    resolve_vertical_config,
)
from server import app

client = TestClient(app)


def test_resolve_vertical_config():
    # 1. Patents
    patents_cfg = resolve_vertical_config("patents")
    assert patents_cfg["vertical"] == "patents"
    assert patents_cfg["query_source"] == "patents"
    assert patents_cfg["sources"] == ["web"]
    assert patents_cfg["search_focus"] == "internet"
    assert "https://www.perplexity.ai/patents" in patents_cfg["url"]

    # 2. Academic
    academic_cfg = resolve_vertical_config("academic")
    assert academic_cfg["vertical"] == "academic"
    assert academic_cfg["query_source"] == "academic"
    assert academic_cfg["sources"] == ["scholar"]
    assert academic_cfg["search_focus"] == "internet"
    assert "https://www.perplexity.ai/academic" in academic_cfg["url"]

    # 3. Finance
    finance_cfg = resolve_vertical_config("finance")
    assert finance_cfg["vertical"] == "finance"
    assert finance_cfg["query_source"] == "finance"
    assert finance_cfg["sources"] == ["web"]
    assert finance_cfg["canonical_page_context"] is not None
    assert finance_cfg["canonical_page_context"]["page_type"] == "finance"
    assert finance_cfg["canonical_page_context"]["data"]["country"] == "US"
    assert "https://www.perplexity.ai/finance" in finance_cfg["url"]

    # 4. Social
    social_cfg = resolve_vertical_config("social")
    assert social_cfg["vertical"] == "social"
    assert social_cfg["query_source"] == "social"
    assert social_cfg["sources"] == ["social"]

    # 5. Writing / Wolfram / YouTube / Reddit
    writing_cfg = resolve_vertical_config("writing")
    assert writing_cfg["search_focus"] == "writing"
    assert writing_cfg["sources"] == []

    wolfram_cfg = resolve_vertical_config("wolfram")
    assert wolfram_cfg["search_focus"] == "wolfram"

    youtube_cfg = resolve_vertical_config("youtube")
    assert youtube_cfg["search_focus"] == "youtube"

    reddit_cfg = resolve_vertical_config("reddit")
    assert reddit_cfg["search_focus"] == "reddit"

    # 6. Default fallback
    default_cfg = resolve_vertical_config(None)
    assert default_cfg["vertical"] == "web"
    assert default_cfg["query_source"] == "home"
    assert default_cfg["sources"] == ["web"]


def test_parse_model_and_vertical():
    # 复合模型语法 ":"
    m, v = parse_model_and_vertical("patents:claude-3-7-sonnet")
    assert m == "claude-3-7-sonnet"
    assert v == "patents"

    # 复合模型语法 "/"
    m, v = parse_model_and_vertical("academic/sonar")
    assert m == "sonar"
    assert v == "academic"

    m, v = parse_model_and_vertical("finance:gpt-5.6")
    assert m == "gpt-5.6"
    assert v == "finance"

    # 单独垂直领域名称作为模型名
    m, v = parse_model_and_vertical("patents")
    assert m == "experimental"
    assert v == "patents"

    m, v = parse_model_and_vertical("academic")
    assert m == "experimental"
    assert v == "academic"

    # 显式参数优先
    m, v = parse_model_and_vertical("claude-3-7-sonnet", explicit_vertical="finance")
    assert m == "claude-3-7-sonnet"
    assert v == "finance"

    # 别名解析
    m, v = parse_model_and_vertical("scholar:sonar")
    assert m == "sonar"
    assert v == "academic"


def test_build_payload_with_verticals():
    p_client = PerplexityClient(auth_manager=MagicMock(get_valid_token=lambda: "token"))

    # 1. Patents payload
    patents_p = p_client._build_payload("Solid state battery patents", vertical="patents")
    assert patents_p["params"]["query_source"] == "patents"
    assert patents_p["params"]["sources"] == ["web"]

    # 2. Academic payload
    academic_p = p_client._build_payload("Mamba attention models", vertical="academic")
    assert academic_p["params"]["query_source"] == "academic"
    assert academic_p["params"]["sources"] == ["scholar"]

    # 3. Finance payload
    finance_p = p_client._build_payload("NVDA earnings margins", vertical="finance")
    assert finance_p["params"]["query_source"] == "finance"
    assert "canonical_page_context" in finance_p["params"]
    assert finance_p["params"]["canonical_page_context"]["page_type"] == "finance"

    # 4. Headers referer
    headers_patents = p_client._build_headers(vertical="patents")
    assert headers_patents["Referer"] == "https://www.perplexity.ai/patents"

    headers_academic = p_client._build_headers(vertical="academic")
    assert headers_academic["Referer"] == "https://www.perplexity.ai/academic"

    headers_finance = p_client._build_headers(vertical="finance")
    assert headers_finance["Referer"] == "https://www.perplexity.ai/finance"


def test_server_verticals_endpoint():
    resp = client.get("/verticals")
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert "aliases" in data
    v_ids = [v["id"] for v in data["data"]]
    assert "patents" in v_ids
    assert "academic" in v_ids
    assert "finance" in v_ids
    assert "social" in v_ids


def test_server_chat_completions_with_vertical_compound_model():
    mock_res = {
        "query": "CRISPR patents",
        "answer": "Here are the top CRISPR-Cas9 patents [1].",
        "sources": [{"name": "USPTO", "url": "https://patents.google.com/patent/US9840699B2"}],
        "model": "claude50sonnet",
        "vertical": "patents",
    }

    with patch("server.PerplexityClient.ask", return_value=mock_res) as mock_ask:
        payload = {
            "model": "patents:claude-3-7-sonnet",
            "messages": [{"role": "user", "content": "CRISPR patents"}],
            "stream": False,
        }
        resp = client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["vertical"] == "patents"
        assert resp.headers.get("X-Perplexity-Vertical") == "patents"
        # Verify ask was called with vertical='patents' and model='claude-3-7-sonnet'
        mock_ask.assert_called_once()
        _, kwargs = mock_ask.call_args
        assert kwargs["vertical"] == "patents"
        assert kwargs["model"] == "claude-3-7-sonnet"


def test_server_chat_completions_with_explicit_vertical_body():
    mock_res = {
        "query": "arXiv Mamba paper",
        "answer": "Mamba paper details [1].",
        "sources": [{"name": "arXiv", "url": "https://arxiv.org/abs/2312.00752"}],
        "model": "experimental",
        "vertical": "academic",
    }

    with patch("server.PerplexityClient.ask", return_value=mock_res) as mock_ask:
        payload = {
            "model": "sonar",
            "vertical": "academic",
            "messages": [{"role": "user", "content": "arXiv Mamba paper"}],
            "stream": False,
        }
        resp = client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["vertical"] == "academic"
        assert resp.headers.get("X-Perplexity-Vertical") == "academic"
        mock_ask.assert_called_once()
        _, kwargs = mock_ask.call_args
        assert kwargs["vertical"] == "academic"


def test_server_search_endpoint_with_vertical():
    mock_res = {
        "query": "NVDA margins",
        "answer": "NVDA gross margins were 75% in latest quarter.",
        "sources": [{"name": "Nvidia IR", "url": "https://nvidianews.nvidia.com"}],
        "model": "experimental",
        "vertical": "finance",
    }

    with patch("server.PerplexityClient.ask", return_value=mock_res) as mock_ask:
        resp = client.get("/search?q=NVDA+margins&vertical=finance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["vertical"] == "finance"
        assert "75%" in data["answer"]
        mock_ask.assert_called_once()
        _, kwargs = mock_ask.call_args
        assert kwargs["vertical"] == "finance"


def test_remote_client_passes_vertical():
    remote_client = RemotePerplexityClient("http://remote-gateway:8000")

    with patch("httpx.Client.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Remote patents answer"}}],
            "citations": [{"name": "P1", "url": "https://patents.google.com"}],
            "model": "claude-3-7-sonnet",
            "vertical": "patents"
        }
        mock_post.return_value = mock_resp

        # 1. Test ask with explicit vertical parameter
        res = remote_client.ask("Query", model="claude-3-7-sonnet", vertical="patents")
        assert res["answer"] == "Remote patents answer"
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["vertical"] == "patents"
        assert kwargs["json"]["model"] == "claude-3-7-sonnet"

    with patch("httpx.Client.post") as mock_post2:
        mock_resp2 = MagicMock()
        mock_resp2.status_code = 200
        mock_resp2.json.return_value = {
            "choices": [{"message": {"content": "Remote academic answer"}}],
            "citations": [],
            "model": "sonar",
            "vertical": "academic"
        }
        mock_post2.return_value = mock_resp2

        # 2. Test ask with compound model name
        res2 = remote_client.ask("Query", model="academic:sonar")
        assert res2["answer"] == "Remote academic answer"
        mock_post2.assert_called_once()
        _, kwargs = mock_post2.call_args
        assert kwargs["json"]["vertical"] == "academic"
        assert kwargs["json"]["model"] == "sonar"
