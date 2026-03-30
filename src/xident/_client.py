"""Xident SDK client -- main entry point (sync + async).

Follows the OpenAI Python SDK pattern: resources as cached properties,
constructor accepts all configuration, context manager support.

Usage::

    # Synchronous
    client = Xident(api_key="sk_live_...")
    result = client.verification.init(callback_url="...", min_age=18)

    # Asynchronous
    async_client = AsyncXident(api_key="sk_live_...")
    result = await async_client.verification.init(callback_url="...", min_age=18)

    # Context manager (auto-close)
    with Xident(api_key="sk_live_...") as client:
        result = client.verification.init(callback_url="...", min_age=18)

    async with AsyncXident(api_key="sk_live_...") as client:
        result = await client.verification.init(callback_url="...", min_age=18)
"""

from __future__ import annotations

import functools
from types import TracebackType
from typing import Any

import httpx

from ._config import SDK_VERSION, Config
from ._http_client import AsyncHttpClient, SyncHttpClient
from .resources.verification import AsyncVerification, Verification
from .resources.webhooks import Webhooks


class Xident:
    """Synchronous Xident SDK client.

    Args:
        api_key: Your Xident secret API key (sk_live_xxx or sk_test_xxx).
        base_url: API base URL override.
        timeout: Request timeout in seconds (default: 30).
        max_retries: Max retries on 5xx errors (default: 3).
        headers: Extra headers to send with every request.
        transport: httpx transport override for testing.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
        headers: dict[str, str] | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url is not None:
            kwargs["base_url"] = base_url
        if timeout is not None:
            kwargs["timeout"] = timeout
        if max_retries is not None:
            kwargs["max_retries"] = max_retries
        if headers is not None:
            kwargs["headers"] = headers

        self._config = Config(**kwargs)
        self._http = SyncHttpClient(self._config, transport=transport)

    @functools.cached_property
    def verification(self) -> Verification:
        """Verification resource -- init tokens and session results."""
        return Verification(self._http)

    @functools.cached_property
    def webhooks(self) -> Webhooks:
        """Webhooks resource -- verify signatures and parse events."""
        return Webhooks()

    @staticmethod
    def version() -> str:
        """SDK version string."""
        return SDK_VERSION

    @property
    def config(self) -> Config:
        """Get the current configuration (read-only)."""
        return self._config

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._http.close()

    def __enter__(self) -> Xident:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def __repr__(self) -> str:
        key_preview = self._config.api_key[:8] + "..." if len(self._config.api_key) > 8 else "***"
        return f"Xident(api_key='{key_preview}', base_url='{self._config.base_url}')"


class AsyncXident:
    """Asynchronous Xident SDK client.

    Args:
        api_key: Your Xident secret API key (sk_live_xxx or sk_test_xxx).
        base_url: API base URL override.
        timeout: Request timeout in seconds (default: 30).
        max_retries: Max retries on 5xx errors (default: 3).
        headers: Extra headers to send with every request.
        transport: httpx async transport override for testing.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
        headers: dict[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url is not None:
            kwargs["base_url"] = base_url
        if timeout is not None:
            kwargs["timeout"] = timeout
        if max_retries is not None:
            kwargs["max_retries"] = max_retries
        if headers is not None:
            kwargs["headers"] = headers

        self._config = Config(**kwargs)
        self._http = AsyncHttpClient(self._config, transport=transport)

    @functools.cached_property
    def verification(self) -> AsyncVerification:
        """Verification resource -- init tokens and session results (async)."""
        return AsyncVerification(self._http)

    @functools.cached_property
    def webhooks(self) -> Webhooks:
        """Webhooks resource -- verify signatures and parse events."""
        return Webhooks()

    @staticmethod
    def version() -> str:
        """SDK version string."""
        return SDK_VERSION

    @property
    def config(self) -> Config:
        """Get the current configuration (read-only)."""
        return self._config

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()

    async def __aenter__(self) -> AsyncXident:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    def __repr__(self) -> str:
        key_preview = self._config.api_key[:8] + "..." if len(self._config.api_key) > 8 else "***"
        return f"AsyncXident(api_key='{key_preview}', base_url='{self._config.base_url}')"
