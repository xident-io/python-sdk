"""Tests for the Xident and AsyncXident client classes."""

import pytest

import xident
from xident._config import SDK_VERSION
from xident.resources.verification import AsyncVerification, Verification
from xident.resources.webhooks import Webhooks

from .conftest import AsyncMockTransport, MockTransport


class TestXident:
    def test_constructor_with_api_key(self) -> None:
        transport = MockTransport()
        client = xident.Xident(api_key="sk_test_123", transport=transport)
        assert isinstance(client, xident.Xident)

    def test_constructor_with_all_options(self) -> None:
        transport = MockTransport()
        client = xident.Xident(
            api_key="sk_test_123",
            base_url="https://custom.api.io",
            timeout=60,
            max_retries=5,
            headers={"X-Custom": "value"},
            transport=transport,
        )
        assert client.config.base_url == "https://custom.api.io"
        assert client.config.timeout == 60
        assert client.config.max_retries == 5

    def test_empty_api_key_raises(self) -> None:
        with pytest.raises(ValueError, match="API key cannot be empty"):
            xident.Xident(api_key="")

    def test_verification_returns_resource(self) -> None:
        transport = MockTransport()
        client = xident.Xident(api_key="sk_test_123", transport=transport)
        assert isinstance(client.verification, Verification)

    def test_webhooks_returns_resource(self) -> None:
        transport = MockTransport()
        client = xident.Xident(api_key="sk_test_123", transport=transport)
        assert isinstance(client.webhooks, Webhooks)

    def test_resources_are_cached(self) -> None:
        transport = MockTransport()
        client = xident.Xident(api_key="sk_test_123", transport=transport)
        v1 = client.verification
        v2 = client.verification
        assert v1 is v2

    def test_version(self) -> None:
        assert xident.Xident.version() == SDK_VERSION

    def test_config_property(self) -> None:
        transport = MockTransport()
        client = xident.Xident(
            api_key="sk_test_123",
            base_url="https://staging.api.io",
            transport=transport,
        )
        assert client.config.api_key == "sk_test_123"
        assert client.config.base_url == "https://staging.api.io"

    def test_context_manager(self, mock_transport: MockTransport) -> None:
        with xident.Xident(api_key="sk_test_123", transport=mock_transport) as client:
            assert isinstance(client, xident.Xident)

    def test_repr(self) -> None:
        transport = MockTransport()
        client = xident.Xident(api_key="sk_test_1234567890", transport=transport)
        r = repr(client)
        assert "Xident(" in r
        assert "sk_test_..." in r
        assert "localhost" in r

    def test_repr_short_key(self) -> None:
        transport = MockTransport()
        client = xident.Xident(api_key="short", transport=transport)
        r = repr(client)
        assert "***" in r

    def test_transport_injection(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_success(
            {"token": "xit_abc", "verify_url": "https://verify.xident.io?t=xit_abc"}
        )
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)
        result = client.verification.init(callback_url="https://example.com/cb")
        assert result.token == "xit_abc"
        assert mock_transport.request_count == 1


class TestAsyncXident:
    def test_constructor(self) -> None:
        transport = AsyncMockTransport()
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)
        assert isinstance(client, xident.AsyncXident)

    def test_verification_returns_async_resource(self) -> None:
        transport = AsyncMockTransport()
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)
        assert isinstance(client.verification, AsyncVerification)

    def test_webhooks_returns_resource(self) -> None:
        transport = AsyncMockTransport()
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)
        assert isinstance(client.webhooks, Webhooks)

    def test_version(self) -> None:
        assert xident.AsyncXident.version() == SDK_VERSION

    def test_repr(self) -> None:
        transport = AsyncMockTransport()
        client = xident.AsyncXident(api_key="sk_test_1234567890", transport=transport)
        assert "AsyncXident(" in repr(client)

    @pytest.mark.asyncio
    async def test_async_context_manager(self) -> None:
        transport = AsyncMockTransport()
        async with xident.AsyncXident(api_key="sk_test_123", transport=transport) as client:
            assert isinstance(client, xident.AsyncXident)

    @pytest.mark.asyncio
    async def test_transport_injection(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_success(
            {"token": "xit_abc", "verify_url": "https://verify.xident.io?t=xit_abc"}
        )
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)
        result = await client.verification.init(callback_url="https://example.com/cb")
        assert result.token == "xit_abc"
        assert transport.request_count == 1
