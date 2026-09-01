"""
Perplexity 认证与凭证管理模块 (Perplexity Auth & Session Manager)
- 逆向 NextAuth 滚动刷新机制 (仿 oh-my-pi 实现)
- 支持通过 agent-browser --auto-connect 自动从真实浏览器提取 SSO / 登录态
- 支持凭证本地持久化与自动定时续期
- 支持环境变量 PERPLEXITY_SESSION_PATH 与 PERPLEXITY_SESSION_TOKEN 配置
"""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# pyrefly: ignore [missing-import]
import httpx

APP_USER_AGENT = "Perplexity/641 CFNetwork/1568 Darwin/25.2.0"
API_VERSION = "2.18"
DEFAULT_CREDENTIALS_PATH = Path.home() / ".perplexity_session.json"
LOCAL_CREDENTIALS_PATH = Path(".perplexity_session.json")
NEXTAUTH_SESSION_URL = "https://www.perplexity.ai/api/auth/session"


def get_credentials_path() -> Path:
    """获取凭据存储路径 (优先环境变量，次之当前目录，最后用户主目录)"""
    env_path = os.getenv("PERPLEXITY_SESSION_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()
    if LOCAL_CREDENTIALS_PATH.exists():
        return LOCAL_CREDENTIALS_PATH
    return DEFAULT_CREDENTIALS_PATH


def load_credentials(path: Path | None = None) -> dict[str, Any]:
    """从磁盘加载凭据，并支持环境变量回退"""
    target = path or get_credentials_path()
    if target.exists():
        try:
            with open(target, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data.get("session_token"):
                    return data
        except Exception:
            pass

    # 环境变量回退机制 (方便 Docker / CI / Serverless 部署)
    env_token = os.getenv("PERPLEXITY_SESSION_TOKEN")
    if env_token:
        return {
            "session_token": env_token,
            "user": {
                "name": os.getenv("PERPLEXITY_USER_NAME", "Env User"),
                "email": os.getenv("PERPLEXITY_USER_EMAIL", ""),
            },
            "expires_at": "",
            "last_refreshed_at": datetime.now(timezone.utc).isoformat(),
            "source": "environment",
        }
    return {}


def save_credentials(data: dict[str, Any], path: Path | None = None) -> None:
    """保存凭据到磁盘"""
    target = path or get_credentials_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def extract_from_browser(url: str = "https://www.perplexity.ai") -> dict[str, Any]:
    """
    使用 agent-browser --auto-connect 连接当前系统真实浏览器，提取 Perplexity 会话 Cookie 与 SSO Token
    """
    cmd = ["agent-browser", "--auto-connect", "eval", "document.cookie"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        output = result.stdout.strip()

        # 解析 cookies
        cookies_dict = {}
        for item in output.split(";"):
            if "=" in item:
                k, v = item.strip().split("=", 1)
                cookies_dict[k] = v

        session_token = cookies_dict.get("__Secure-next-auth.session-token")
        if not session_token:
            # 尝试通过 agent-browser 获取 storage / cookies json
            cmd_cookies = ["agent-browser", "--auto-connect", "cookies"]
            res_c = subprocess.run(
                cmd_cookies,
                capture_output=True,
                text=True,
                timeout=10,
            )
            try:
                cookies_arr = json.loads(res_c.stdout)
                for c in cookies_arr:
                    if c.get("name") == "__Secure-next-auth.session-token":
                        session_token = c.get("value")
                        break
            except Exception:
                pass

        if not session_token:
            raise ValueError(
                "浏览器当前页面或会话中未找到 __Secure-next-auth.session-token，请确认已在浏览器中打开并登录 Perplexity"
            )

        # 查找可能的 organization token
        org_token = None
        for k, v in cookies_dict.items():
            if k.startswith("__Secure-pplx.session."):
                org_token = v
                break

        credentials = {
            "session_token": session_token,
            "org_token": org_token,
            "cookies": cookies_dict,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "source": "browser_auto_connect",
        }

        # 自动调用刷新以获取用户信息和过期时间
        manager = PerplexityAuthManager(credentials)
        try:
            refresh_res = manager.refresh()
            credentials.update(refresh_res)
        except Exception:
            # 刷新失败也保存原始提取的 session_token
            save_credentials(credentials)

        return credentials

    except FileNotFoundError:
        raise RuntimeError("未检测到 agent-browser CLI 工具，请先全局安装: npm i -g agent-browser")
    except Exception as e:
        raise RuntimeError(f"从浏览器提取凭据失败: {e}")


class PerplexityAuthManager:
    """Perplexity 会话管理与滚动刷新器"""

    def __init__(self, credentials: dict[str, Any] | None = None):
        self.credentials = credentials if credentials is not None else load_credentials()
        self.session_token = self.credentials.get("session_token", "")

    @property
    def cf_clearance(self) -> str | None:
        return self.credentials.get("cf_clearance")

    def is_expired(self) -> bool:
        """检查凭据是否过期或即将过期 (提前 12 小时判断)"""
        expires_at = self.credentials.get("expires_at")
        if not expires_at:
            return False
        try:
            exp_time = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            # 剩余时间小于 12 小时即认为需刷新
            return (exp_time - datetime.now(timezone.utc)).total_seconds() < 43200
        except Exception:
            return False

    def refresh(self, force: bool = False) -> dict[str, Any]:
        """
        调用 NextAuth /api/auth/session 端点触发 Set-Cookie 滚动刷新 (延长 30 天有效期)
        :param force: 是否强制立即向服务端请求刷新 Token
        """
        if not self.session_token:
            raise ValueError(
                "当前无有效的 session_token，请先调用 extract_from_browser() 或手动配置凭据"
            )

        cookie_str = f"__Secure-next-auth.session-token={self.session_token}"
        if self.credentials.get("org_token"):
            cookie_str += f"; __Secure-pplx.session.org={self.credentials['org_token']}"

        headers = {
            "User-Agent": APP_USER_AGENT,
            "Accept": "*/*",
            "Cookie": cookie_str,
            "Referer": "https://www.perplexity.ai/",
        }

        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(NEXTAUTH_SESSION_URL, headers=headers)
            if resp.status_code == 401:
                raise RuntimeError(
                    "Session 已失效 (401 Unauthorized)，请重新在浏览器中 SSO 登录并提取"
                )
            if resp.status_code != 200:
                raise RuntimeError(f"刷新 Session 失败 ({resp.status_code}): {resp.text}")

            # 提取新的 Set-Cookie 中的 session-token
            set_cookies = resp.headers.get_list("set-cookie")
            for sc in set_cookies:
                if "__Secure-next-auth.session-token=" in sc:
                    new_token = sc.split("__Secure-next-auth.session-token=")[1].split(";")[0]
                    self.session_token = new_token
                    self.credentials["session_token"] = new_token
                if "__Secure-pplx.session." in sc:
                    org_cookie_val = sc.split("=")[1].split(";")[0]
                    self.credentials["org_token"] = org_cookie_val

            data = resp.json()
            user = data.get("user", {})
            self.credentials["user"] = user
            self.credentials["expires_at"] = data.get("expires", "")
            self.credentials["last_refreshed_at"] = datetime.now(timezone.utc).isoformat()

            save_credentials(self.credentials)
            return {
                "session_token": self.session_token,
                "user": user,
                "expires_at": self.credentials["expires_at"],
            }

    def get_valid_token(self) -> str:
        """获取有效的 session token，若即将过期自动刷新"""
        if not self.session_token:
            # 尝试从浏览器提取
            creds = extract_from_browser()
            self.credentials = creds
            self.session_token = self.credentials.get("session_token", "")
            return self.session_token

        if self.is_expired():
            try:
                self.refresh()
            except Exception:
                # 刷新失败时尝试重新从浏览器提取
                creds = extract_from_browser()
                self.credentials = creds
                self.session_token = self.credentials.get("session_token", "")

        return self.session_token
