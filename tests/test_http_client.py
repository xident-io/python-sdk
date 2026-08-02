"""Tests for the HTTP client layer."""

from __future__ import annotations

import json

import httpx
import pytest

from xident import _http_client
from xident._config import Config
from xident._http_client import AsyncHttpClient, SyncHttpClient, _retry_delay_seconds
from xident.errors import (
    AuthenticationError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
    XidentError,
)

from .conftest import AsyncMockTransport, MockTransport


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


class _FailingTransport(httpx.BaseTransport):
    """Sync transport that always raises the supplied httpx error.

    Simulates DNS failure / connection refused / TLS error -- the family
    httpx groups under ``httpx.HTTPError``, which the SDK translates into
    :class:`NetworkError`.
    """

    def __init__(self, exc: httpx.HTTPError) -> None:
        self._exc = exc
        self.attempts = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.attempts += 1
        raise self._exc


class _AsyncFailingTransport(httpx.AsyncBaseTransport):
    """Async counterpart of :class:`_FailingTransport`."""

    def __init__(self, exc: httpx.HTTPError) -> None:
        self._exc = exc
        self.attempts = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.attempts += 1
        raise self._exc


class _StubConfig:
    """A Config-shaped stand-in exposing only what the HTTP clients read.

    Used to drive ``max_retries`` values a real :class:`Config` clamps away,
    so the retry loop's defensive exits can be exercised instead of merely
    asserted-about in a comment.
    """

    def __init__(self, max_retries: int) -> None:
        self.api_key = "sk_test_123"
        self.api_url = "https://api.xident.io/verify/v1"
        self.timeout = 30
        self.user_agent = "Xident-Python/stub"
        self.headers: dict[str, str] | None = None
        self.max_retries = max_retries


class _GrowingRetryConfig(_StubConfig):
    """A config whose retry budget grows between reads.

    ``_request`` reads ``max_retries`` twice per pass: once up front to size
    ``range()``, then again inside the loop to decide whether an attempt was
    the last one. A budget that grows in between (a live-reloaded config, an
    operator raising the limit mid-flight) makes the final attempt take the
    ``continue`` path, so the loop runs out with an error still in hand.
    """

    def __init__(self) -> None:
        super().__init__(max_retries=0)
        self._reads = 0

    @property  # type: ignore[override]
    def max_retries(self) -> int:
        self._reads += 1
        # First read sizes the loop: range(0 + 1) -> exactly one attempt.
        # Later reads claim budget remains, so that attempt does not raise.
        return 0 if self._reads == 1 else 99

    @max_retries.setter
    def max_retries(self, value: int) -> None:
        # Swallow the base-class assignment; the property is the real source.
        pass


@pytest.fixture
def no_backoff_sleep(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Record which attempts slept, and make the sleeps instant.

    Returns the list of attempt numbers passed to the backoff helper, so a
    test can assert the SDK backed off before each retry (and did NOT sleep
    before the first attempt) without paying real seconds for it.
    """
    slept: list[int] = []

    def fake_delay(attempt: int) -> float:
        slept.append(attempt)
        return 0.0

    monkeypatch.setattr(_http_client, "_retry_delay_seconds", fake_delay)
    return slept


class TestRetryBackoff:
    """The backoff schedule itself: exponential, jittered, bounded."""

    def test_delay_grows_exponentially_within_the_jitter_band(self) -> None:
        # base = 2**(attempt-1), returned delay is base*0.5 .. base*1.0.
        for attempt, low, high in [(1, 0.5, 1.0), (2, 1.0, 2.0), (3, 2.0, 4.0)]:
            samples = [_retry_delay_seconds(attempt) for _ in range(200)]
            assert all(low <= s <= high for s in samples), f"attempt {attempt} out of band"
            midpoint = (low + high) / 2
            # Jitter must actually spread, otherwise the thundering-herd
            # protection this function exists for is not happening.
            assert min(samples) < midpoint < max(samples)

    def test_delay_returns_a_float_not_an_int(self) -> None:
        assert isinstance(_retry_delay_seconds(1), float)


class TestEnvelopeParsing:
    def test_json_array_body_is_rejected_as_parse_error(self) -> None:
        # Valid JSON, wrong shape. Every API response is an object envelope;
        # a bare array would make body.get(...) blow up with AttributeError,
        # so it is normalised into a PARSE_ERROR envelope instead.
        transport = MockTransport()
        transport.queue_response(
            httpx.Response(
                status_code=200,
                json=[{"not": "an envelope"}],
                headers={"content-type": "application/json"},
            )
        )
        config = Config(api_key="sk_test_123", max_retries=0)
        client = SyncHttpClient(config, transport=transport)

        with pytest.raises(ValidationError) as exc_info:
            client.get("/test")

        assert exc_info.value.error_code == "PARSE_ERROR"
        assert exc_info.value.message == "Failed to parse API response"
        assert exc_info.value.status_code == 200
        assert exc_info.value.request_id is None

    def test_non_json_body_is_rejected_as_parse_error(self) -> None:
        transport = MockTransport()
        transport.queue_response(
            httpx.Response(
                status_code=200,
                content=b"<html>502 Bad Gateway</html>",
                headers={"content-type": "text/html"},
            )
        )
        config = Config(api_key="sk_test_123", max_retries=0)
        client = SyncHttpClient(config, transport=transport)

        with pytest.raises(ValidationError) as exc_info:
            client.get("/test")

        assert exc_info.value.error_code == "PARSE_ERROR"
        assert exc_info.value.message == "Failed to parse API response"

    def test_success_envelope_without_data_returns_empty_dict(self) -> None:
        # `data: null` on a success envelope must not leak None to a caller
        # that is about to subscript it.
        transport = MockTransport()
        transport.queue_response(
            httpx.Response(
                status_code=200,
                json={"success": True, "data": None},
                headers={"content-type": "application/json"},
            )
        )
        config = Config(api_key="sk_test_123", max_retries=0)
        client = SyncHttpClient(config, transport=transport)

        assert client.get("/test") == {}


class TestSyncNetworkErrors:
    def test_connection_error_retries_then_raises_network_error(
        self, no_backoff_sleep: list[int]
    ) -> None:
        boom = httpx.ConnectError("failed to resolve api.xident.io")
        transport = _FailingTransport(boom)
        config = Config(api_key="sk_test_123", max_retries=2)
        client = SyncHttpClient(config, transport=transport)

        with pytest.raises(NetworkError) as exc_info:
            client.get("/test")

        assert type(exc_info.value) is NetworkError
        assert str(exc_info.value) == "Connection error: failed to resolve api.xident.io"
        # The original httpx error is chained, not swallowed.
        assert exc_info.value.__cause__ is boom
        # Initial attempt + 2 retries, with a backoff before each retry only.
        assert transport.attempts == 3
        assert no_backoff_sleep == [1, 2]

    def test_connection_error_without_retries_raises_on_first_attempt(
        self, no_backoff_sleep: list[int]
    ) -> None:
        transport = _FailingTransport(httpx.ConnectTimeout("timed out"))
        config = Config(api_key="sk_test_123", max_retries=0)
        client = SyncHttpClient(config, transport=transport)

        with pytest.raises(NetworkError, match="Connection error: timed out"):
            client.get("/test")

        assert transport.attempts == 1
        assert no_backoff_sleep == []

    def test_network_error_recovers_when_a_retry_succeeds(
        self, no_backoff_sleep: list[int]
    ) -> None:
        # One flaky connection then a good one: the call must succeed, not
        # surface the transient failure.
        class _FlakyTransport(httpx.BaseTransport):
            def __init__(self) -> None:
                self.attempts = 0

            def handle_request(self, request: httpx.Request) -> httpx.Response:
                self.attempts += 1
                if self.attempts == 1:
                    raise httpx.ConnectError("connection reset")
                return httpx.Response(
                    status_code=200,
                    json={"success": True, "data": {"ok": True}},
                    headers={"content-type": "application/json"},
                )

        transport = _FlakyTransport()
        config = Config(api_key="sk_test_123", max_retries=1)
        client = SyncHttpClient(config, transport=transport)

        assert client.get("/test") == {"ok": True}
        assert transport.attempts == 2
        assert no_backoff_sleep == [1]

    def test_network_error_is_a_xident_error(self) -> None:
        transport = _FailingTransport(httpx.ConnectError("nope"))
        config = Config(api_key="sk_test_123", max_retries=0)
        client = SyncHttpClient(config, transport=transport)

        with pytest.raises(XidentError):
            client.get("/test")


class TestSyncRetryLoopExits:
    """The two defensive exits below the retry loop.

    A real Config clamps ``max_retries`` to >= 0 and the loop then always
    leaves by return or raise -- so these are reached only by handing the
    client a config that does not behave like one. They still matter: both
    guarantee the method never falls off the end returning ``None``, which a
    resource class would immediately dereference.
    """

    def test_empty_retry_budget_raises_network_error(self) -> None:
        transport = MockTransport()
        client = SyncHttpClient(_StubConfig(max_retries=-1), transport=transport)  # type: ignore[arg-type]

        with pytest.raises(NetworkError) as exc_info:
            client.get("/test")

        assert str(exc_info.value) == "Request failed after retries"
        assert transport.request_count == 0

    def test_loop_falling_through_reraises_the_last_error(
        self, no_backoff_sleep: list[int]
    ) -> None:
        transport = _FailingTransport(httpx.ConnectError("upstream down"))
        client = SyncHttpClient(_GrowingRetryConfig(), transport=transport)  # type: ignore[arg-type]

        with pytest.raises(NetworkError) as exc_info:
            client.get("/test")

        # The error from the last attempt, not the generic fallback message.
        assert str(exc_info.value) == "Connection error: upstream down"
        assert transport.attempts == 1


class TestAsyncHttpClientExtras:
    @pytest.mark.asyncio
    async def test_custom_headers_are_sent(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_success({})
        config = Config(api_key="sk_test_123", headers={"X-Tenant": "acme"})
        client = AsyncHttpClient(config, transport=transport)

        await client.get("/test")

        req = transport.last_request
        assert req is not None
        assert req.headers["x-tenant"] == "acme"
        # Custom headers must not displace the auth/UA defaults.
        assert req.headers["x-api-key"] == "sk_test_123"
        assert "Xident-Python/" in req.headers["user-agent"]

    @pytest.mark.asyncio
    async def test_custom_header_can_override_a_default(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_success({})
        config = Config(api_key="sk_test_123", headers={"Accept": "application/vnd.xident+json"})
        client = AsyncHttpClient(config, transport=transport)

        await client.get("/test")

        req = transport.last_request
        assert req is not None
        assert req.headers["accept"] == "application/vnd.xident+json"

    @pytest.mark.asyncio
    async def test_patch_sends_method_and_body(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_success({"updated": True})
        config = Config(api_key="sk_test_123")
        client = AsyncHttpClient(config, transport=transport)

        data = await client.patch("/update", body={"field": "val"})

        assert data == {"updated": True}
        req = transport.last_request
        assert req is not None
        assert req.method == "PATCH"
        assert json.loads(req.content) == {"field": "val"}

    @pytest.mark.asyncio
    async def test_delete_sends_method(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_success({"deleted": True})
        config = Config(api_key="sk_test_123")
        client = AsyncHttpClient(config, transport=transport)

        data = await client.delete("/remove")

        assert data == {"deleted": True}
        req = transport.last_request
        assert req is not None
        assert req.method == "DELETE"

    @pytest.mark.asyncio
    async def test_get_envelope_preserves_meta(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_success({"rows": []})
        config = Config(api_key="sk_test_123")
        client = AsyncHttpClient(config, transport=transport)

        envelope = await client.get_envelope("/list")

        assert envelope["success"] is True
        assert envelope["data"] == {"rows": []}
        assert envelope["meta"] == {"request_id": "req_test_123"}

    @pytest.mark.asyncio
    async def test_aclose_closes_the_underlying_client(self) -> None:
        transport = AsyncMockTransport()
        config = Config(api_key="sk_test_123")
        client = AsyncHttpClient(config, transport=transport)

        await client.aclose()

        assert client._client.is_closed is True


class TestAsyncNetworkErrors:
    @pytest.mark.asyncio
    async def test_connection_error_retries_then_raises_network_error(
        self, no_backoff_sleep: list[int]
    ) -> None:
        boom = httpx.ConnectError("failed to resolve api.xident.io")
        transport = _AsyncFailingTransport(boom)
        config = Config(api_key="sk_test_123", max_retries=2)
        client = AsyncHttpClient(config, transport=transport)

        with pytest.raises(NetworkError) as exc_info:
            await client.get("/test")

        assert type(exc_info.value) is NetworkError
        assert str(exc_info.value) == "Connection error: failed to resolve api.xident.io"
        assert exc_info.value.__cause__ is boom
        assert transport.attempts == 3
        assert no_backoff_sleep == [1, 2]

    @pytest.mark.asyncio
    async def test_connection_error_without_retries_raises_on_first_attempt(
        self, no_backoff_sleep: list[int]
    ) -> None:
        transport = _AsyncFailingTransport(httpx.ReadTimeout("read timed out"))
        config = Config(api_key="sk_test_123", max_retries=0)
        client = AsyncHttpClient(config, transport=transport)

        with pytest.raises(NetworkError, match="Connection error: read timed out"):
            await client.get("/test")

        assert transport.attempts == 1
        assert no_backoff_sleep == []


class TestAsyncRetryLoopExits:
    """Async mirror of :class:`TestSyncRetryLoopExits`."""

    @pytest.mark.asyncio
    async def test_empty_retry_budget_raises_network_error(self) -> None:
        transport = AsyncMockTransport()
        client = AsyncHttpClient(_StubConfig(max_retries=-1), transport=transport)  # type: ignore[arg-type]

        with pytest.raises(NetworkError) as exc_info:
            await client.get("/test")

        assert str(exc_info.value) == "Request failed after retries"
        assert transport.request_count == 0

    @pytest.mark.asyncio
    async def test_loop_falling_through_reraises_the_last_error(
        self, no_backoff_sleep: list[int]
    ) -> None:
        transport = _AsyncFailingTransport(httpx.ConnectError("upstream down"))
        client = AsyncHttpClient(_GrowingRetryConfig(), transport=transport)  # type: ignore[arg-type]

        with pytest.raises(NetworkError) as exc_info:
            await client.get("/test")

        assert str(exc_info.value) == "Connection error: upstream down"
        assert transport.attempts == 1


class TestSyncClientLifecycle:
    def test_close_closes_the_underlying_client(self) -> None:
        transport = MockTransport()
        config = Config(api_key="sk_test_123")
        client = SyncHttpClient(config, transport=transport)

        client.close()

        assert client._client.is_closed is True

    def test_get_envelope_preserves_meta(self) -> None:
        transport = MockTransport()
        transport.queue_success({"rows": []})
        config = Config(api_key="sk_test_123")
        client = SyncHttpClient(config, transport=transport)

        envelope = client.get_envelope("/list")

        assert envelope["success"] is True
        assert envelope["meta"] == {"request_id": "req_test_123"}

    def test_base_url_prefixes_every_request(self) -> None:
        transport = MockTransport()
        transport.queue_success({})
        config = Config(api_key="sk_test_123", base_url="https://staging.xident.io")
        client = SyncHttpClient(config, transport=transport)

        client.get("/result/xtk_1")

        req = transport.last_request
        assert req is not None
        assert str(req.url) == "https://staging.xident.io/verify/v1/result/xtk_1"
