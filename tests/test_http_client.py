"""Tests for the HTTP client layer."""

import json

import httpx
import pytest

import xident
from xident._config import Config
from xident._http_client import SyncHttpClient, AsyncHttpClient
from xident.errors import (
    AuthenticationError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)

from .conftest import MockTransport, AsyncMockTransport, make_error_response, make_success_response


class TestSyncHttpClient:
    def test_get_request(self) -> None:
        transport = MockTransport()
        transport.queue_success({"key": "value"})
        config = Config(api_key="sk_test_123")
        client = SyncHttpClient(config, transport=transport)

        data = client.get("/test")
        assert data == {"key": "value"}
        assert transport.request_count == 1

        req = transport.last_request
        assert req is not None
        assert req.method == "GET"
        assert "/test" in str(req.url)

    def test_post_request(self) -> None:
        transport = MockTransport()
        transport.queue_success({"id": "123"})
        config = Config(api_key="sk_test_123")
        client = SyncHttpClient(config, transport=transport)

        data = client.post("/create", body={"name": "test"})
        assert data == {"id": "123"}

        req = transport.last_request
        assert req is not None
        assert req.method == "POST"
        body = json.loads(req.content)
        assert body == {"name": "test"}

    def test_patch_request(self) -> None:
        transport = MockTransport()
        transport.queue_success({"updated": True})
        config = Config(api_key="sk_test_123")
        client = SyncHttpClient(config, transport=transport)

        data = client.patch("/update", body={"field": "val"})
        assert data == {"updated": True}

        req = transport.last_request
        assert req is not None
        assert req.method == "PATCH"

    def test_delete_request(self) -> None:
        transport = MockTransport()
        transport.queue_success({})
        config = Config(api_key="sk_test_123")
        client = SyncHttpClient(config, transport=transport)

        data = client.delete("/remove")
        assert data == {}

        req = transport.last_request
        assert req is not None
        assert req.method == "DELETE"

    def test_headers_include_api_key(self) -> None:
        transport = MockTransport()
        transport.queue_success({})
        config = Config(api_key="sk_test_secret_key")
        client = SyncHttpClient(config, transport=transport)

        client.get("/test")
        req = transport.last_request
        assert req is not None
        assert req.headers["x-api-key"] == "sk_test_secret_key"

    def test_headers_include_user_agent(self) -> None:
        transport = MockTransport()
        transport.queue_success({})
        config = Config(api_key="sk_test_123")
        client = SyncHttpClient(config, transport=transport)

        client.get("/test")
        req = transport.last_request
        assert req is not None
        assert "Xident-Python/" in req.headers["user-agent"]

    def test_headers_include_accept(self) -> None:
        transport = MockTransport()
        transport.queue_success({})
        config = Config(api_key="sk_test_123")
        client = SyncHttpClient(config, transport=transport)

        client.get("/test")
        req = transport.last_request
        assert req is not None
        assert req.headers["accept"] == "application/json"

    def test_custom_headers(self) -> None:
        transport = MockTransport()
        transport.queue_success({})
        config = Config(api_key="sk_test_123", headers={"X-Custom": "custom_value"})
        client = SyncHttpClient(config, transport=transport)

        client.get("/test")
        req = transport.last_request
        assert req is not None
        assert req.headers["x-custom"] == "custom_value"

    def test_query_params(self) -> None:
        transport = MockTransport()
        transport.queue_success({})
        config = Config(api_key="sk_test_123")
        client = SyncHttpClient(config, transport=transport)

        client.get("/test", params={"page": 1, "limit": 10})
        req = transport.last_request
        assert req is not None
        assert "page=1" in str(req.url)
        assert "limit=10" in str(req.url)


class TestErrorMapping:
    """Test that HTTP status codes map to the correct exception types."""

    def _make_client(self, transport: MockTransport) -> SyncHttpClient:
        config = Config(api_key="sk_test_123", max_retries=0)
        return SyncHttpClient(config, transport=transport)

    def test_401_raises_authentication_error(self) -> None:
        transport = MockTransport()
        transport.queue_error(401, "UNAUTHORIZED", "Invalid API key")
        client = self._make_client(transport)

        with pytest.raises(AuthenticationError) as exc_info:
            client.get("/test")
        assert exc_info.value.status_code == 401
        assert exc_info.value.error_code == "UNAUTHORIZED"

    def test_403_raises_authentication_error(self) -> None:
        transport = MockTransport()
        transport.queue_error(403, "FORBIDDEN", "Access denied")
        client = self._make_client(transport)

        with pytest.raises(AuthenticationError):
            client.get("/test")

    def test_400_raises_validation_error(self) -> None:
        transport = MockTransport()
        transport.queue_error(400, "INVALID_REQUEST", "Missing callback_url")
        client = self._make_client(transport)

        with pytest.raises(ValidationError) as exc_info:
            client.post("/test")
        assert exc_info.value.error_code == "INVALID_REQUEST"

    def test_404_raises_not_found_error(self) -> None:
        transport = MockTransport()
        transport.queue_error(404, "NOT_FOUND", "Token not found")
        client = self._make_client(transport)

        with pytest.raises(NotFoundError):
            client.get("/test")

    def test_429_raises_rate_limit_error(self) -> None:
        transport = MockTransport()
        transport.queue_error(429, "RATE_LIMITED", "Too many requests")
        client = self._make_client(transport)

        with pytest.raises(RateLimitError):
            client.get("/test")

    def test_500_raises_server_error(self) -> None:
        transport = MockTransport()
        transport.queue_error(500, "INTERNAL_ERROR", "Internal server error")
        client = self._make_client(transport)

        with pytest.raises(ServerError):
            client.get("/test")

    def test_422_raises_validation_error(self) -> None:
        transport = MockTransport()
        transport.queue_error(422, "UNPROCESSABLE", "Invalid data")
        client = self._make_client(transport)

        with pytest.raises(ValidationError):
            client.get("/test")

    def test_error_includes_request_id(self) -> None:
        transport = MockTransport()
        transport.queue_error(400, "INVALID", "Bad request")
        client = self._make_client(transport)

        with pytest.raises(ValidationError) as exc_info:
            client.get("/test")
        assert exc_info.value.request_id == "req_test_err_456"


class TestRetryLogic:
    def test_retries_on_5xx(self) -> None:
        transport = MockTransport()
        # First two requests return 500, third succeeds
        transport.queue_error(500, "INTERNAL", "Server error")
        transport.queue_error(500, "INTERNAL", "Server error")
        transport.queue_success({"ok": True})

        config = Config(api_key="sk_test_123", max_retries=2)
        client = SyncHttpClient(config, transport=transport)

        data = client.get("/test")
        assert data == {"ok": True}
        assert transport.request_count == 3

    def test_no_retry_on_4xx(self) -> None:
        transport = MockTransport()
        transport.queue_error(400, "INVALID", "Bad request")

        config = Config(api_key="sk_test_123", max_retries=3)
        client = SyncHttpClient(config, transport=transport)

        with pytest.raises(ValidationError):
            client.get("/test")
        assert transport.request_count == 1

    def test_exhausted_retries_raises(self) -> None:
        transport = MockTransport()
        # All retries fail
        transport.queue_error(500, "INTERNAL", "Error 1")
        transport.queue_error(500, "INTERNAL", "Error 2")

        config = Config(api_key="sk_test_123", max_retries=1)
        client = SyncHttpClient(config, transport=transport)

        with pytest.raises(ServerError):
            client.get("/test")
        assert transport.request_count == 2

    def test_no_retries_when_zero(self) -> None:
        transport = MockTransport()
        transport.queue_error(500, "INTERNAL", "Server error")

        config = Config(api_key="sk_test_123", max_retries=0)
        client = SyncHttpClient(config, transport=transport)

        with pytest.raises(ServerError):
            client.get("/test")
        assert transport.request_count == 1

    def test_malformed_json_response(self) -> None:
        transport = MockTransport()
        transport.queue_response(
            httpx.Response(
                status_code=200,
                content=b"not json",
                headers={"content-type": "text/plain"},
            )
        )

        config = Config(api_key="sk_test_123", max_retries=0)
        client = SyncHttpClient(config, transport=transport)

        # Should raise ValidationError due to PARSE_ERROR
        with pytest.raises(ValidationError):
            client.get("/test")


class TestAsyncHttpClient:
    @pytest.mark.asyncio
    async def test_async_get(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_success({"key": "value"})
        config = Config(api_key="sk_test_123")
        client = AsyncHttpClient(config, transport=transport)

        data = await client.get("/test")
        assert data == {"key": "value"}
        assert transport.request_count == 1

    @pytest.mark.asyncio
    async def test_async_post(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_success({"id": "abc"})
        config = Config(api_key="sk_test_123")
        client = AsyncHttpClient(config, transport=transport)

        data = await client.post("/create", body={"name": "test"})
        assert data == {"id": "abc"}

    @pytest.mark.asyncio
    async def test_async_error_mapping(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_error(401, "UNAUTHORIZED", "Invalid key")
        config = Config(api_key="sk_test_123", max_retries=0)
        client = AsyncHttpClient(config, transport=transport)

        with pytest.raises(AuthenticationError):
            await client.get("/test")

    @pytest.mark.asyncio
    async def test_async_retry(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_error(500, "INTERNAL", "Error")
        transport.queue_success({"ok": True})
        config = Config(api_key="sk_test_123", max_retries=1)
        client = AsyncHttpClient(config, transport=transport)

        data = await client.get("/test")
        assert data == {"ok": True}
        assert transport.request_count == 2
