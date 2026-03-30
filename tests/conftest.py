"""Shared fixtures and mock transport for Xident SDK tests."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

import xident


def make_success_response(data: dict[str, Any], status_code: int = 200) -> httpx.Response:
    """Build a mock httpx.Response with the standard API envelope."""
    envelope = {"success": True, "data": data, "meta": {"request_id": "req_test_123"}}
    return httpx.Response(
        status_code=status_code,
        json=envelope,
        headers={"content-type": "application/json"},
    )


def make_error_response(
    status_code: int,
    error_code: str,
    message: str,
) -> httpx.Response:
    """Build a mock httpx.Response with an error envelope."""
    envelope = {
        "success": False,
        "error": {"code": error_code, "message": message},
        "meta": {"request_id": "req_test_err_456"},
    }
    return httpx.Response(
        status_code=status_code,
        json=envelope,
        headers={"content-type": "application/json"},
    )


class MockTransport(httpx.BaseTransport):
    """Mock transport for synchronous httpx.Client.

    Queue responses with queue_response()/queue_success()/queue_error(),
    then inject into the Xident client via the transport parameter.
    Records all requests for assertion.
    """

    def __init__(self) -> None:
        self._responses: list[httpx.Response] = []
        self._requests: list[httpx.Request] = []

    def queue_response(self, response: httpx.Response) -> MockTransport:
        """Queue a raw httpx.Response."""
        self._responses.append(response)
        return self

    def queue_success(self, data: dict[str, Any]) -> MockTransport:
        """Queue a successful API response with the standard envelope."""
        return self.queue_response(make_success_response(data))

    def queue_error(self, status_code: int, error_code: str, message: str) -> MockTransport:
        """Queue an error API response with the standard envelope."""
        return self.queue_response(make_error_response(status_code, error_code, message))

    @property
    def last_request(self) -> httpx.Request | None:
        """Get the last recorded request."""
        return self._requests[-1] if self._requests else None

    def get_request(self, index: int) -> httpx.Request | None:
        """Get a recorded request by index."""
        return self._requests[index] if index < len(self._requests) else None

    @property
    def request_count(self) -> int:
        """Number of recorded requests."""
        return len(self._requests)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Handle an httpx request (called by httpx.Client)."""
        self._requests.append(request)
        if not self._responses:
            raise RuntimeError("MockTransport: no more queued responses")
        return self._responses.pop(0)


class AsyncMockTransport(httpx.AsyncBaseTransport):
    """Mock transport for asynchronous httpx.AsyncClient.

    Same interface as MockTransport but for async usage.
    """

    def __init__(self) -> None:
        self._responses: list[httpx.Response] = []
        self._requests: list[httpx.Request] = []

    def queue_response(self, response: httpx.Response) -> AsyncMockTransport:
        """Queue a raw httpx.Response."""
        self._responses.append(response)
        return self

    def queue_success(self, data: dict[str, Any]) -> AsyncMockTransport:
        """Queue a successful API response with the standard envelope."""
        return self.queue_response(make_success_response(data))

    def queue_error(self, status_code: int, error_code: str, message: str) -> AsyncMockTransport:
        """Queue an error API response with the standard envelope."""
        return self.queue_response(make_error_response(status_code, error_code, message))

    @property
    def last_request(self) -> httpx.Request | None:
        """Get the last recorded request."""
        return self._requests[-1] if self._requests else None

    def get_request(self, index: int) -> httpx.Request | None:
        """Get a recorded request by index."""
        return self._requests[index] if index < len(self._requests) else None

    @property
    def request_count(self) -> int:
        """Number of recorded requests."""
        return len(self._requests)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Handle an httpx request (called by httpx.AsyncClient)."""
        self._requests.append(request)
        if not self._responses:
            raise RuntimeError("AsyncMockTransport: no more queued responses")
        return self._responses.pop(0)


@pytest.fixture
def mock_transport() -> MockTransport:
    """Provide a fresh MockTransport for each test."""
    return MockTransport()


@pytest.fixture
def async_mock_transport() -> AsyncMockTransport:
    """Provide a fresh AsyncMockTransport for each test."""
    return AsyncMockTransport()


@pytest.fixture
def client(mock_transport: MockTransport) -> xident.Xident:
    """Provide a Xident client with mock transport."""
    return xident.Xident(api_key="sk_test_123", transport=mock_transport)


@pytest.fixture
def async_client(async_mock_transport: AsyncMockTransport) -> xident.AsyncXident:
    """Provide an AsyncXident client with mock transport."""
    return xident.AsyncXident(api_key="sk_test_123", transport=async_mock_transport)
