"""
Perplexity Search2API 配置管理模块 (Perplexity Config Manager)
- 支持多种配置文件格式读取与解析:
  1. JSON 配置文件 (~/.perplexity_config.json, ./.perplexity_config.json, ~/.perplexity_session.json)
  2. 环境变量与 .env 配置文件 (./.env, ~/.env)
  3. TOML 配置文件 (./pplx.toml, ~/.pplx.toml, ./pyproject.toml 中的 [tool.pplx])
  4. YAML 配置文件 (./.perplexity.yaml, ~/.perplexity.yaml)
- 支持远端 API 端点 (Remote URL)、API Key 与默认模型的持久化与多源合并
- 统一优先级: 命令行参数 > 系统环境变量 > 本地/用户目录配置文件 (.env / JSON / TOML / YAML)
"""

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path.home() / ".perplexity_config.json"
LOCAL_CONFIG_PATH = Path(".perplexity_config.json")
DEFAULT_ENV_PATH = Path(".env")
HOME_ENV_PATH = Path.home() / ".env"
LOCAL_TOML_PATH = Path("pplx.toml")
HOME_TOML_PATH = Path.home() / ".pplx.toml"
PYPROJECT_PATH = Path("pyproject.toml")


def parse_dotenv(path: Path) -> dict[str, str]:
    """解析 .env 格式文件"""
    env_vars: dict[str, str] = {}
    if not path.exists():
        return env_vars
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k:
                        env_vars[k] = v
    except Exception:
        pass
    return env_vars


def parse_toml(path: Path) -> dict[str, Any]:
    """解析 TOML 配置文件 (支持 tomllib/tomli 或轻量原生解析)"""
    if not path.exists():
        return {}
    try:
        import tomllib  # Python 3.11+

        with open(path, "rb") as f:
            data = tomllib.load(f)
            if isinstance(data, dict):
                if "tool" in data and isinstance(data["tool"], dict):
                    if "pplx" in data["tool"]:
                        return data["tool"]["pplx"]
                    if "perplexity" in data["tool"]:
                        return data["tool"]["perplexity"]
                if "pplx" in data:
                    return data["pplx"]
                return data
    except Exception:
        pass

    try:
        import tomli  # Python 3.10

        with open(path, "rb") as f:
            data = tomli.load(f)
            if isinstance(data, dict):
                if "tool" in data and isinstance(data["tool"], dict):
                    if "pplx" in data["tool"]:
                        return data["tool"]["pplx"]
                    if "perplexity" in data["tool"]:
                        return data["tool"]["perplexity"]
                if "pplx" in data:
                    return data["pplx"]
                return data
    except Exception:
        pass

    # 原生轻量 TOML 解析回退 (支持顶层键值对与 [tool.pplx] / [pplx] 块)
    result: dict[str, Any] = {}
    current_section = ""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    current_section = line[1:-1].strip()
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k and current_section in ("tool.pplx", "tool.perplexity", "pplx", ""):
                        result[k] = v
    except Exception:
        pass
    return result


def parse_yaml(path: Path) -> dict[str, Any]:
    """解析 YAML 配置文件 (支持 PyYAML 或轻量原生解析)"""
    if not path.exists():
        return {}
    try:
        import yaml

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass

    # 原生轻量 key: value 回退解析
    result: dict[str, Any] = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k:
                        result[k] = v
    except Exception:
        pass
    return result


def get_config_path() -> Path:
    """获取主要配置文件路径 (支持 PERPLEXITY_CONFIG_PATH 环境变量覆盖)"""
    env_path = os.getenv("PERPLEXITY_CONFIG_PATH")
    if env_path:
        return Path(env_path).resolve()
    if LOCAL_CONFIG_PATH.exists():
        return LOCAL_CONFIG_PATH.resolve()
    if LOCAL_TOML_PATH.exists():
        return LOCAL_TOML_PATH.resolve()
    return DEFAULT_CONFIG_PATH.resolve()


def load_config(path: Path | None = None) -> dict[str, Any]:
    """
    从磁盘加载配置，支持合并 .env、JSON、TOML、YAML 以及 credentials 文件中的配置项
    """
    config: dict[str, Any] = {}

    # 1. 加载 .env 文件
    env_candidates = [
        Path(os.getenv("PERPLEXITY_ENV_PATH")) if os.getenv("PERPLEXITY_ENV_PATH") else None,
        DEFAULT_ENV_PATH,
        HOME_ENV_PATH,
    ]
    for env_p in env_candidates:
        if env_p and env_p.exists():
            dotenv_dict = parse_dotenv(env_p)
            for k, v in dotenv_dict.items():
                if k in (
                    "PERPLEXITY_BASE_URL",
                    "PERPLEXITY_REMOTE_URL",
                    "PPLX_REMOTE_URL",
                    "PPLX_BASE_URL",
                    "REMOTE_URL",
                    "BASE_URL",
                ):
                    config.setdefault("remote_url", v)
                elif k in ("PERPLEXITY_API_KEY", "PERPLEXITY_PROXY_KEY", "PPLX_API_KEY", "API_KEY"):
                    config.setdefault("api_key", v)
                elif k in ("PERPLEXITY_DEFAULT_MODEL", "DEFAULT_MODEL", "MODEL"):
                    config.setdefault("default_model", v)
                elif k in ("PERPLEXITY_TIMEOUT", "TIMEOUT"):
                    try:
                        config.setdefault("timeout", float(v))
                    except Exception:
                        pass

    # 2. 加载 TOML 文件 (pplx.toml / pyproject.toml)
    for toml_p in [HOME_TOML_PATH, LOCAL_TOML_PATH, PYPROJECT_PATH]:
        if toml_p.exists():
            toml_data = parse_toml(toml_p)
            for k in ("remote_url", "base_url", "url", "api_key", "default_model", "timeout"):
                if k in toml_data:
                    norm_k = "remote_url" if k in ("base_url", "url") else k
                    config[norm_k] = toml_data[k]

    # 3. 加载 YAML 文件
    for yaml_p in [
        Path.home() / ".perplexity.yaml",
        Path(".perplexity.yaml"),
        Path(".perplexity.yml"),
    ]:
        if yaml_p.exists():
            yaml_data = parse_yaml(yaml_p)
            for k in ("remote_url", "base_url", "url", "api_key", "default_model", "timeout"):
                if k in yaml_data:
                    norm_k = "remote_url" if k in ("base_url", "url") else k
                    config[norm_k] = yaml_data[k]

    # 4. 加载主 JSON 配置文件 (~/.perplexity_config.json 或指定路径)
    target = path or get_config_path()
    if target.exists():
        try:
            with open(target, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    config.update(data)
        except Exception:
            pass

    # 5. 兼容凭据 JSON 文件 (~/.perplexity_session.json / .perplexity_session.json)
    try:
        from perplexity_auth import load_credentials

        creds = load_credentials()
        for k in ("remote_url", "base_url", "api_key"):
            if k in creds and creds[k]:
                norm_k = "remote_url" if k == "base_url" else k
                config.setdefault(norm_k, creds[k])
    except Exception:
        pass

    return config


def save_config(data: dict[str, Any], path: Path | None = None) -> None:
    """保存配置到磁盘 (默认写入 ~/.perplexity_config.json)"""
    target = path or get_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_remote_url(override: str | None = None) -> str | None:
    """
    解析远端服务器地址
    优先级:
    1. CLI 参数 (--remote / --base-url)
    2. 系统环境变量 (PERPLEXITY_BASE_URL, PERPLEXITY_REMOTE_URL, PPLX_REMOTE_URL, PPLX_BASE_URL)
    3. 配置文件 (.env, ~/.perplexity_config.json, pplx.toml, .perplexity_session.json 等)
    4. 系统环境变量 OPENAI_BASE_URL 回退
    """
    if override and override.strip():
        return override.strip().rstrip("/")

    for env_key in [
        "PERPLEXITY_BASE_URL",
        "PERPLEXITY_REMOTE_URL",
        "PPLX_REMOTE_URL",
        "PPLX_BASE_URL",
    ]:
        val = os.getenv(env_key)
        if val and val.strip():
            return val.strip().rstrip("/")

    config = load_config()
    for k in ("remote_url", "base_url", "url"):
        if config.get(k):
            return str(config[k]).strip().rstrip("/")

    openai_base = os.getenv("OPENAI_BASE_URL")
    if openai_base and openai_base.strip() and "api.openai.com" not in openai_base:
        return openai_base.strip().rstrip("/")

    return None


def get_remote_api_key(override: str | None = None) -> str | None:
    """
    解析远端 API Key
    优先级:
    1. CLI 参数 (--api-key)
    2. 系统环境变量 (PERPLEXITY_API_KEY, PERPLEXITY_PROXY_KEY, PPLX_API_KEY, API_KEY)
    3. 配置文件 (.env, ~/.perplexity_config.json, pplx.toml 等)
    4. 系统环境变量 OPENAI_API_KEY 回退
    """
    if override and override.strip():
        return override.strip()

    for env_key in [
        "PERPLEXITY_API_KEY",
        "PERPLEXITY_PROXY_KEY",
        "PPLX_API_KEY",
        "API_KEY",
    ]:
        val = os.getenv(env_key)
        if val and val.strip():
            return val.strip()

    config = load_config()
    for k in ("api_key", "key"):
        if config.get(k):
            return str(config[k]).strip()

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and openai_key.strip():
        return openai_key.strip()

    return None


def set_remote_config(
    url: str,
    api_key: str | None = None,
    default_model: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """设置远端端点与配置并写入持久化配置文件"""
    config = load_config(path)
    clean_url = url.strip().rstrip("/")
    config["remote_url"] = clean_url
    if api_key is not None:
        if api_key.strip():
            config["api_key"] = api_key.strip()
        else:
            config.pop("api_key", None)
    if default_model is not None:
        if default_model.strip():
            config["default_model"] = default_model.strip()
        else:
            config.pop("default_model", None)
    save_config(config, path)
    return config


def unset_remote_config(path: Path | None = None) -> dict[str, Any]:
    """清除远端端点配置"""
    config = load_config(path)
    config.pop("remote_url", None)
    config.pop("api_key", None)
    save_config(config, path)
    return config


def is_remote_mode(override_url: str | None = None) -> bool:
    """判断当前是否运行在远端 API 模式"""
    return bool(get_remote_url(override_url))
