"""Tests for the Verification resource (sync and async)."""

import json

import pytest

import xident

from .conftest import AsyncMockTransport, MockTransport


class TestVerification:
    def test_init_creates_token(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_success(
            {"token": "xit_abc123", "verify_url": "https://verify.xident.io?t=xit_abc123"}
        )
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        result = client.verification.init(callback_url="https://example.com/callback")

        assert result.token == "xit_abc123"
        assert result.verify_url == "https://verify.xident.io?t=xit_abc123"

    def test_init_sends_correct_body(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_success({"token": "xit_x", "verify_url": "https://v.io"})
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        client.verification.init(
            callback_url="https://example.com/cb",
            min_age=18,
            user_id="user_42",
            theme="dark",
        )

        req = mock_transport.last_request
        assert req is not None
        assert req.method == "POST"
        body = json.loads(req.content)
        assert body["callback_url"] == "https://example.com/cb"
        assert body["min_age"] == 18
        assert body["user_id"] == "user_42"
        assert body["theme"] == "dark"

    def test_init_omits_none_values(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_success({"token": "xit_x", "verify_url": "https://v.io"})
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        client.verification.init(callback_url="https://example.com/cb")

        req = mock_transport.last_request
        assert req is not None
        body = json.loads(req.content)
        assert "min_age" not in body
        assert "user_id" not in body
        assert "theme" not in body
        assert body["callback_url"] == "https://example.com/cb"

    def test_init_all_params(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_success({"token": "xit_x", "verify_url": "https://v.io"})
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        client.verification.init(
            callback_url="https://example.com/cb",
            min_age=21,
            success_url="https://example.com/success",
            failed_url="https://example.com/failed",
            user_id="user_99",
            theme="system",
            locale="de",
            metadata="custom_data",
            purpose="age_verification",
            verification_mode="document",
            liveness_difficulty="hard",
        )

        req = mock_transport.last_request
        assert req is not None
        body = json.loads(req.content)
        assert len(body) == 11  # All params present
        assert body["theme"] == "system"
        assert body["purpose"] == "age_verification"
        assert body["verification_mode"] == "document"
        assert body["liveness_difficulty"] == "hard"

    def test_init_sends_purpose(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_success({"token": "xit_x", "verify_url": "https://v.io"})
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        client.verification.init(
            callback_url="https://example.com/cb",
            min_age=0,
            purpose="id_verification",
        )

        req = mock_transport.last_request
        assert req is not None
        body = json.loads(req.content)
        assert body["purpose"] == "id_verification"
        assert body["min_age"] == 0

    def test_init_sends_verification_mode(self, mock_transport: MockTransport) -> None:
        """A pilot's exact call: force the document path regardless of the rule engine."""
        mock_transport.queue_success({"token": "xit_x", "verify_url": "https://v.io"})
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        client.verification.init(
            callback_url="https://example.com/cb",
            verification_mode="document",
        )

        req = mock_transport.last_request
        assert req is not None
        body = json.loads(req.content)
        assert body["verification_mode"] == "document"

    def test_init_sends_liveness_difficulty(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_success({"token": "xit_x", "verify_url": "https://v.io"})
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        client.verification.init(
            callback_url="https://example.com/cb",
            liveness_difficulty="easy",
        )

        req = mock_transport.last_request
        assert req is not None
        body = json.loads(req.content)
        assert body["liveness_difficulty"] == "easy"

    def test_init_omits_verification_mode_and_liveness_difficulty_when_unset(
        self, mock_transport: MockTransport
    ) -> None:
        mock_transport.queue_success({"token": "xit_x", "verify_url": "https://v.io"})
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        client.verification.init(callback_url="https://example.com/cb")

        req = mock_transport.last_request
        assert req is not None
        body = json.loads(req.content)
        assert "verification_mode" not in body
        assert "liveness_difficulty" not in body

    def test_get_result_returns_session(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_success(
            {
                "token": "xtk_abc123",
                "status": "success",
                "verification_mode": "facial",
                "checks": {"age": {"performed": True, "passed": True, "gate": 18}},
                "created_at": "2026-01-01T00:00:00Z",
            }
        )
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        result = client.verification.get_result("xtk_abc123")

        assert result.token == "xtk_abc123"
        assert result.status == xident.SessionStatus.COMPLETED
        assert result.is_verified()
        assert result.age_bracket() == 18
        assert result.method() == "facial"

    def test_get_result_empty_token_raises(self, mock_transport: MockTransport) -> None:
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        with pytest.raises(ValueError, match="Token cannot be empty"):
            client.verification.get_result("")

    def test_get_result_url_encodes_token(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_success({"id": "sess_1", "status": "pending", "created_at": ""})
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        client.verification.get_result("token/with/slashes")

        req = mock_transport.last_request
        assert req is not None
        # Slashes should be encoded in the URL path
        assert "token%2Fwith%2Fslashes" in str(req.url)


class TestAsyncVerification:
    @pytest.mark.asyncio
    async def test_init_creates_token(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_success(
            {"token": "xit_async", "verify_url": "https://verify.xident.io?t=xit_async"}
        )
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)

        result = await client.verification.init(callback_url="https://example.com/cb")

        assert result.token == "xit_async"
        assert result.verify_url == "https://verify.xident.io?t=xit_async"

    @pytest.mark.asyncio
    async def test_init_sends_verification_mode_and_liveness_difficulty(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_success({"token": "xit_x", "verify_url": "https://v.io"})
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)

        await client.verification.init(
            callback_url="https://example.com/cb",
            verification_mode="document",
            liveness_difficulty="hard",
        )

        req = transport.last_request
        assert req is not None
        body = json.loads(req.content)
        assert body["verification_mode"] == "document"
        assert body["liveness_difficulty"] == "hard"

    @pytest.mark.asyncio
    async def test_get_result_returns_session(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_success(
            {"id": "sess_async", "status": "failed", "created_at": "2026-01-01T00:00:00Z"}
        )
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)

        result = await client.verification.get_result("xtk_async123")

        assert result.id == "sess_async"
        assert result.is_failed()

    @pytest.mark.asyncio
    async def test_get_result_empty_token_raises(self) -> None:
        transport = AsyncMockTransport()
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)

        with pytest.raises(ValueError, match="Token cannot be empty"):
            await client.verification.get_result("")
