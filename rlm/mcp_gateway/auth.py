"""Authentication helpers for RLM MCP Gateway."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class OAuthValidationResult:
    active: bool
    expires_at: float | None = None


class GatewayAuth:
    """Gateway auth manager supporting API-key and OAuth introspection flows."""

    def __init__(
        self,
        api_key: str | None,
        oauth_introspection_url: str | None = None,
        oauth_client_id: str | None = None,
        oauth_client_secret: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.oauth_introspection_url = oauth_introspection_url
        self.oauth_client_id = oauth_client_id
        self.oauth_client_secret = oauth_client_secret
        self._token_cache: dict[str, OAuthValidationResult] = {}

    @property
    def oauth_enabled(self) -> bool:
        return bool(self.oauth_introspection_url)

    def validate(self, bearer_token: str | None) -> bool:
        """Validate authentication token based on configured mode."""
        if self.oauth_enabled:
            return self._validate_oauth_token(bearer_token)

        if self.api_key is None:
            return True
        return bearer_token == self.api_key

    def _validate_oauth_token(self, token: str | None) -> bool:
        if token is None or token.strip() == "":
            return False

        cached_result = self._token_cache.get(token)
        now = time.time()
        if cached_result is not None:
            if cached_result.expires_at is None or cached_result.expires_at > now:
                return cached_result.active
            del self._token_cache[token]

        validation_result = self._introspect_token(token)
        if validation_result.active:
            self._token_cache[token] = validation_result
        return validation_result.active

    def _introspect_token(self, token: str) -> OAuthValidationResult:
        if not self.oauth_introspection_url:
            return OAuthValidationResult(active=False)

        auth: tuple[str, str] | None = None
        if self.oauth_client_id and self.oauth_client_secret:
            auth = (self.oauth_client_id, self.oauth_client_secret)

        response = requests.post(
            self.oauth_introspection_url,
            data={"token": token},
            auth=auth,
            timeout=5,
        )
        response.raise_for_status()
        payload = response.json()

        active = bool(payload.get("active"))
        expires_at: float | None = None
        exp_value = payload.get("exp")
        if isinstance(exp_value, int):
            expires_at = float(exp_value)

        return OAuthValidationResult(active=active, expires_at=expires_at)

    def oauth_metadata(self) -> dict[str, Any]:
        """Return OAuth metadata payload for well-known endpoints."""
        return {
            "oauth_enabled": self.oauth_enabled,
            "introspection_endpoint": self.oauth_introspection_url,
            "client_id": self.oauth_client_id,
        }
