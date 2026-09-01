import json
import os


def test_codex_marketplace_manifest():
    path = ".agents/plugins/marketplace.json"
    assert os.path.exists(path), f"{path} should exist"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["name"] == "perplexity-search2api"
    assert "plugins" in data
    assert len(data["plugins"]) >= 1
    assert data["plugins"][0]["name"] == "pplx"


def test_codex_plugin_manifest():
    path = ".codex-plugin/plugin.json"
    assert os.path.exists(path), f"{path} should exist"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["name"] == "pplx"
    assert data["skills"] == "./skills/"


def test_claude_plugin_manifests():
    p_path = ".claude-plugin/plugin.json"
    m_path = ".claude-plugin/marketplace.json"
    assert os.path.exists(p_path)
    assert os.path.exists(m_path)
    with open(p_path, encoding="utf-8") as f:
        p_data = json.load(f)
    with open(m_path, encoding="utf-8") as f:
        m_data = json.load(f)
    assert p_data["name"] == "pplx"
    assert m_data["name"] == "pplx"


def test_skill_md_and_references():
    skill_path = "skills/pplx/SKILL.md"
    assert os.path.exists(skill_path)
    with open(skill_path, encoding="utf-8") as f:
        content = f.read()
    assert "name: pplx" in content
    assert "pplx ask" in content
    assert "references/models.md" in content

    assert os.path.exists("skills/pplx/references/commands.md")
    assert os.path.exists("skills/pplx/references/models.md")
    assert os.path.exists("skills/pplx/references/troubleshooting.md")
    assert os.path.exists("skills/pplx/references/examples.md")
    assert os.path.exists("skills/pplx/agents/openai.yaml")


def test_skills_sh_config():
    path = "skills.sh.json"
    assert os.path.exists(path), f"{path} should exist"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert "groupings" in data
    assert len(data["groupings"]) >= 1
    assert "pplx" in data["groupings"][0]["skills"]
