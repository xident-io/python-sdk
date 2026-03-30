"""HTTP transport layer using httpx (sync + async).

Handles request building, retry with exponential backoff + jitter,
response parsing, and error mapping. Not part of the public API.

Mirrors the PHP SDK's HttpClient: same retry logic, same error mapping,
same header construction. Uses httpx instead of cURL.
"""

from __future__ import annotations

import json
import random
import time
from typing import Any

import httpx

from ._config import Config
from .errors import (
    APIError,
    AuthenticationError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)


def _parse_response(response: httpx.Response) -> dict[str, Any]:
    """Parse and validate the API response envelope.

    The Xident API wraps all responses in:
    { "success": bool, "data": T, "error": { "code", "message" }, "meta": { "request_id" } }
    """
    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError):
        body = {
            "success": False,
            "error": {"code": "PARSE_ERROR", "message": "Failed to parse API response"},
        }

    if not isinstance(body, dict):
        body = {
            "success": False,
            "error": {"code": "PARSE_ERROR", "message": "Failed to parse API response"},
        }

    return body


def _raise_for_status(body: dict[str, Any], status_code: int) -> None:
    """Map HTTP status codes to typed exceptions, matching the PHP SDK."""
    error = body.get("error", {}) or {}
    meta = body.get("meta", {}) or {}

    message = error.get("message", "Unknown error")
    error_code = error.get("code", "")
    request_id = meta.get("request_id")

    kwargs = {
        "status_code": status_code,
        "error_code": error_code,
        "request_id": request_id,
    }

    if status_code in (401, 403):
        raise AuthenticationError(message, **kwargs)
    elif status_code == 404:
        raise NotFoundError(message, **kwargs)
    elif status_code == 429:
        raise RateLimitError(message, **kwargs)
    elif status_code >= 500:
        raise ServerError(message, **kwargs)
    else:
        raise ValidationError(message, **kwargs)


def _retry_delay_seconds(attempt: int) -> float:
    """Exponential backoff with jitter: ~1s, ~2s, ~4s, ...

    Uses full jitter (random between 0 and the exponential cap) to prevent
    thundering herd when multiple SDK instances retry simultaneously.
    """
    base = 2 ** (attempt - 1)  # 1, 2, 4, 8, ...
    jitter = random.random()  # noqa: S311 — not security-sensitive
    return base * (0.5 + jitter * 0.5)  # between base*0.5 and base*1.0


class SyncHttpClient:
    """Synchronous HTTP client wrapping httpx.Client.

    Args:
        config: SDK configuration.
        transport: Optional httpx transport override for testing.
    """

    def __init__(self, config: Config, transport: httpx.BaseTransport | None = None) -> None:
        self._config = config
        self._client = httpx.Client(
            base_url=config.api_url,
            timeout=httpx.Timeout(config.timeout, connect=10.0),
            headers=self._build_default_headers(config),
            transport=transport,
        )

    def _build_default_headers(self, config: Config) -> dict[str, str]:
        headers = {
            "X-API-Key": config.api_key,
            "User-Agent": config.user_agent,
            "Accept": "application/json",
        }
        if config.headers:
            headers.update(config.headers)
        return headers

    def get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a GET request and return the parsed data dict."""
        return self._request("GET", path, params=params)

    def post(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a POST request and return the parsed data dict."""
        return self._request("POST", path, json_body=body)

    def patch(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a PATCH request and return the parsed data dict."""
        return self._request("PATCH", path, json_body=body)

    def delete(self, path: str) -> dict[str, Any]:
        """Send a DELETE request and return the parsed data dict."""
        return self._request("DELETE", path)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute request with retry logic."""
        last_exception: Exception | None = None

        for attempt in range(self._config.max_retries + 1):
            if attempt > 0:
                time.sleep(_retry_delay_seconds(attempt))

            try:
                response = self._client.request(
                    method,
                    path,
                    params=params,
                    json=json_body,
                )
            except httpx.HTTPError as exc:
                last_exception = NetworkError(f"Connection error: {exc}")
                if attempt >= self._config.max_retries:
                    raise last_exception from exc
                continue

            body = _parse_response(response)

            # Retry on 5xx server errors
            if response.status_code >= 500 and attempt < self._config.max_retries:
                last_exception = ServerError(
                    f"Server error ({response.status_code})",
                    status_code=response.status_code,
                )
                continue

            # Raise typed exception for error responses
            if not body.get("success", False):
                _raise_for_status(body, response.status_code)

            return body.get("data") or {}

        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
        raise NetworkError("Request failed after retries")

    def close(self) -> None:
        """Close the underlying httpx client."""
        self._client.close()


class AsyncHttpClient:
    """Asynchronous HTTP client wrapping httpx.AsyncClient.

    Args:
        config: SDK configuration.
        transport: Optional httpx async transport override for testing.
    """

    def __init__(
        self, config: Config, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.api_url,
            timeout=httpx.Timeout(config.timeout, connect=10.0),
            headers=self._build_default_headers(config),
            transport=transport,
        )

    def _build_default_headers(self, config: Config) -> dict[str, str]:
        headers = {
            "X-API-Key": config.api_key,
            "User-Agent": config.user_agent,
            "Accept": "application/json",
        }
        if config.headers:
            headers.update(config.headers)
        return headers

    async def get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a GET request and return the parsed data dict."""
        return await self._request("GET", path, params=params)

    async def post(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a POST request and return the parsed data dict."""
        return await self._request("POST", path, json_body=body)

    async def patch(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a PATCH request and return the parsed data dict."""
        return await self._request("PATCH", path, json_body=body)

    async def delete(self, path: str) -> dict[str, Any]:
        """Send a DELETE request and return the parsed data dict."""
        return await self._request("DELETE", path)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute request with retry logic (async)."""
        last_exception: Exception | None = None

        for attempt in range(self._config.max_retries + 1):
            if attempt > 0:
                import asyncio

                await asyncio.sleep(_retry_delay_seconds(attempt))

            try:
                response = await self._client.request(
                    method,
                    path,
                    params=params,
                    json=json_body,
                )
            except httpx.HTTPError as exc:
                last_exception = NetworkError(f"Connection error: {exc}")
                if attempt >= self._config.max_retries:
                    raise last_exception from exc
                continue

            body = _parse_response(response)

            # Retry on 5xx server errors
            if response.status_code >= 500 and attempt < self._config.max_retries:
                last_exception = ServerError(
                    f"Server error ({response.status_code})",
                    status_code=response.status_code,
                )
                continue

            # Raise typed exception for error responses
            if not body.get("success", False):
                _raise_for_status(body, response.status_code)

            return body.get("data") or {}

        if last_exception:
            raise last_exception
        raise NetworkError("Request failed after retries")

    async def aclose(self) -> None:
        """Close the underlying httpx async client."""
        await self._client.aclose()
