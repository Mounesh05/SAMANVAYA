"""
GitHub App Authentication Module (Option 1).
Mints RS256 JWTs for GitHub App and fetches installation access tokens.
Provides short-lived, least-privilege tokens without requiring developer PATs.
"""

import time
import os
import logging
from typing import Optional, Dict, Tuple
from pathlib import Path
import httpx
from jose import jwt

from core.config import settings

logger = logging.getLogger("samanvaya.github_app")


class GitHubAppAuth:
    """Manages GitHub App JWT generation and Installation Access Token caching."""

    _instance = None
    _token_cache: Dict[str, Tuple[str, float]] = {}  # installation_id -> (token, expire_timestamp)

    def __init__(
        self,
        app_id: Optional[str] = None,
        private_key: Optional[str] = None,
        installation_id: Optional[str] = None,
    ):
        self.app_id = app_id or getattr(settings, "GITHUB_APP_ID", "")
        self.installation_id = installation_id or getattr(settings, "GITHUB_APP_INSTALLATION_ID", "")
        self.private_key = private_key or self._load_private_key()

    def _load_private_key(self) -> str:
        """Loads PEM private key from settings or file path."""
        inline_key = getattr(settings, "GITHUB_APP_PRIVATE_KEY", "")
        if inline_key and "PRIVATE KEY" in inline_key:
            return inline_key.replace("\\n", "\n")

        key_path = getattr(settings, "GITHUB_APP_PRIVATE_KEY_PATH", "")
        if key_path and os.path.exists(key_path):
            try:
                return Path(key_path).read_text(encoding="utf-8")
            except Exception as e:
                logger.warning("[GITHUB-APP] Failed to read private key from %s: %s", key_path, e)

        return ""

    def is_configured(self) -> bool:
        """Returns True if App ID and private key are provided."""
        return bool(self.app_id and self.private_key)

    def generate_app_jwt(self) -> str:
        """
        Creates an RS256 signed JWT for GitHub App authentication.
        Valid for 10 minutes (maximum permitted by GitHub).
        """
        if not self.is_configured():
            raise ValueError("GitHub App ID and Private Key are required to generate JWT.")

        now = int(time.time())
        payload = {
            "iat": now - 60,       # 1 minute clock drift allowance
            "exp": now + (10 * 60), # 10 minutes maximum
            "iss": str(self.app_id),
        }
        token = jwt.encode(payload, self.private_key, algorithm="RS256")
        return token

    async def get_installation_access_token(self, installation_id: Optional[str] = None) -> str:
        """
        Retrieves or refreshes an installation access token for the given organization/repo installation.
        Caches tokens until 2 minutes before expiry.
        """
        inst_id = str(installation_id or self.installation_id)
        if not inst_id:
            # Fall back to global GITHUB_TOKEN if no installation ID
            return settings.GITHUB_TOKEN or ""

        # Check memory cache
        cached = self._token_cache.get(inst_id)
        if cached:
            token, exp_time = cached
            if time.time() < exp_time - 120:  # 2 minute buffer
                return token

        # If App is not fully configured, fall back to GITHUB_TOKEN
        if not self.is_configured():
            return settings.GITHUB_TOKEN or ""

        # Request new token from GitHub API
        app_jwt = self.generate_app_jwt()
        url = f"https://api.github.com/app/installations/{inst_id}/access_tokens"
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers)
            if resp.status_code not in (200, 201):
                logger.error("[GITHUB-APP] Failed to fetch installation token for %s: %s %s", inst_id, resp.status_code, resp.text)
                return settings.GITHUB_TOKEN or ""
            
            data = resp.json()
            token = data.get("token")
            # GitHub installation tokens typically expire in 1 hour (3600s)
            expires_at = time.time() + 3500
            self._token_cache[inst_id] = (token, expires_at)
            logger.info("[GITHUB-APP] Generated fresh installation token for installation %s", inst_id)
            return token


# Singleton instance
_app_auth = None

def get_github_app_auth() -> GitHubAppAuth:
    global _app_auth
    if _app_auth is None:
        _app_auth = GitHubAppAuth()
    return _app_auth

