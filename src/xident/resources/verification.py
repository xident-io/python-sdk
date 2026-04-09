"""Verification resource -- create init tokens and retrieve session results.

Provides both synchronous and asynchronous interfaces.
Mirrors the PHP SDK's Verification resource exactly.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from .._http_client import AsyncHttpClient, SyncHttpClient
from ..responses.init_result import InitResult
from ..responses.session_result import SessionResult


class Verification:
    """Synchronous verification resource.

    Usage::

        client = Xident(api_key="sk_test_...")
        result = client.verification.init(callback_url="https://example.com/cb", min_age=18)
        session = client.verification.get_result("xtk_abc123")
    """

    def __init__(self, http: SyncHttpClient) -> None:
        self._http = http

    def init(
        self,
        *,
        callback_url: str,
        min_age: int | None = None,
        success_url: str | None = None,
        failed_url: str | None = None,
        user_id: str | None = None,
        theme: str | None = None,
        locale: str | None = None,
        metadata: str | None = None,
    ) -> InitResult:
        """Create an init token for starting a verification session.

        Returns a token and the full URL to redirect the user to.
        The token is valid for 10 minutes.

        Args:
            callback_url: URL where user is redirected after verification.
            min_age: Minimum age threshold (12, 15, 18, 21, 25).
            success_url: Override redirect URL on success.
            failed_url: Override redirect URL on failure.
            user_id: Your application's user identifier.
            theme: Widget theme ("light", "dark", "auto").
            locale: Widget locale (e.g. "en", "de", "fr").
            metadata: Opaque string stored with the session.

        Returns:
            InitResult with token and verify_url.

        Raises:
            ValidationError: If required params are missing.
            AuthenticationError: If API key is invalid.
        """
        body = self._build_params(
            callback_url=callback_url,
            min_age=min_age,
            success_url=success_url,
            failed_url=failed_url,
            user_id=user_id,
            theme=theme,
            locale=locale,
            metadata=metadata,
        )
        data = self._http.post("/init", body=body)
        return InitResult.from_dict(data)

    def get_result(self, token: str) -> SessionResult:
        """Get the verification result for a token.

        Call this after the user returns from the verification widget.
        NEVER trust URL parameters alone -- always re-verify server-side.

        Args:
            token: The verification token from the callback URL.

        Returns:
            SessionResult with the full session state.

        Raises:
            ValueError: If token is empty.
            NotFoundError: If token does not exist.
            AuthenticationError: If API key is invalid.
        """
        if not token:
            raise ValueError("Token cannot be empty")
        data = self._http.get(f"/result/{quote(token, safe='')}")
        return SessionResult.from_dict(data)

    @staticmethod
    def _build_params(**kwargs: Any) -> dict[str, Any]:
        """Build request body, omitting None values."""
        return {k: v for k, v in kwargs.items() if v is not None}


class AsyncVerification:
    """Asynchronous verification resource.

    Usage::

        client = AsyncXident(api_key="sk_test_...")
        result = await client.verification.init(callback_url="https://example.com/cb", min_age=18)
        session = await client.verification.get_result("xtk_abc123")
    """

    def __init__(self, http: AsyncHttpClient) -> None:
        self._http = http

    async def init(
        self,
        *,
        callback_url: str,
        min_age: int | None = None,
        success_url: str | None = None,
        failed_url: str | None = None,
        user_id: str | None = None,
        theme: str | None = None,
        locale: str | None = None,
        metadata: str | None = None,
    ) -> InitResult:
        """Create an init token for starting a verification session (async).

        Returns a token and the full URL to redirect the user to.
        The token is valid for 10 minutes.

        Args:
            callback_url: URL where user is redirected after verification.
            min_age: Minimum age threshold (12, 15, 18, 21, 25).
            success_url: Override redirect URL on success.
            failed_url: Override redirect URL on failure.
            user_id: Your application's user identifier.
            theme: Widget theme ("light", "dark", "auto").
            locale: Widget locale (e.g. "en", "de", "fr").
            metadata: Opaque string stored with the session.

        Returns:
            InitResult with token and verify_url.

        Raises:
            ValidationError: If required params are missing.
            AuthenticationError: If API key is invalid.
        """
        body = Verification._build_params(
            callback_url=callback_url,
            min_age=min_age,
            success_url=success_url,
            failed_url=failed_url,
            user_id=user_id,
            theme=theme,
            locale=locale,
            metadata=metadata,
        )
        data = await self._http.post("/init", body=body)
        return InitResult.from_dict(data)

    async def get_result(self, token: str) -> SessionResult:
        """Get the verification result for a token (async).

        Call this after the user returns from the verification widget.
        NEVER trust URL parameters alone -- always re-verify server-side.

        Args:
            token: The verification token from the callback URL.

        Returns:
            SessionResult with the full session state.

        Raises:
            ValueError: If token is empty.
            NotFoundError: If token does not exist.
            AuthenticationError: If API key is invalid.
        """
        if not token:
            raise ValueError("Token cannot be empty")
        data = await self._http.get(f"/result/{quote(token, safe='')}")
        return SessionResult.from_dict(data)
