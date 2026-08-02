"""Tests for the Blacklist resource (sync and async)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

import xident

from .conftest import AsyncMockTransport, MockTransport, make_success_response


def make_list_response(
    rows: list[dict[str, Any]],
    *,
    page: int = 1,
    per_page: int = 20,
    total: int | None = None,
    total_pages: int = 1,
) -> httpx.Response:
    """Build a mock list response with pagination in meta (as the API does)."""
    envelope = {
        "success": True,
        "data": rows,
        "meta": {
            "request_id": "req_test_123",
            "timestamp": "2026-08-01T00:00:00Z",
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total if total is not None else len(rows),
                "total_pages": total_pages,
            },
        },
    }
    return httpx.Response(
        status_code=200,
        json=envelope,
        headers={"content-type": "application/json"},
    )


class TestBlacklist:
    def test_list_returns_page(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_response(
            make_list_response(
                [
                    {
                        "id": 7,
                        "reason": "chargeback fraud",
                        "source": "session",
                        "session_id": 1234,
                        "created_at": "2026-07-30T10:00:00Z",
                    },
                    {
                        "id": 9,
                        "reason": "fake document",
                        "source": "image",
                        "created_at": "2026-07-31T11:00:00Z",
                    },
                ],
                page=1,
                per_page=20,
                total=42,
                total_pages=3,
            )
        )
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        result = client.blacklist.list()

        req = mock_transport.last_request
        assert req is not None
        assert req.method == "GET"
        assert req.url.path.endswith("/blacklist")

        assert len(result) == 2
        first, second = list(result)
        assert first.id == 7
        assert first.reason == "chargeback fraud"
        assert first.source == "session"
        assert first.session_id == 1234
        assert first.created_at == "2026-07-30T10:00:00Z"
        assert second.id == 9
        assert second.session_id is None

        assert result.page == 1
        assert result.per_page == 20
        assert result.total == 42
        assert result.total_pages == 3
        assert result.has_more

    def test_list_sends_pagination_params(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_response(make_list_response([], page=2, per_page=50, total_pages=2))
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        client.blacklist.list(page=2, per_page=50)

        req = mock_transport.last_request
        assert req is not None
        assert req.url.params["page"] == "2"
        assert req.url.params["per_page"] == "50"

    def test_list_omits_none_params(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_response(make_list_response([]))
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        client.blacklist.list()

        req = mock_transport.last_request
        assert req is not None
        assert "page" not in req.url.params
        assert "per_page" not in req.url.params

    def test_list_empty(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_response(make_list_response([], total=0, total_pages=0))
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        result = client.blacklist.list()

        assert len(result) == 0
        assert result.entries == []
        assert result.total == 0
        assert not result.has_more

    def test_add_by_session(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_response(
            make_success_response({"status": "processing"}, status_code=201)
        )
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        status = client.blacklist.add_by_session(
            session_token="xtk_abc123", reason="chargeback fraud"
        )

        req = mock_transport.last_request
        assert req is not None
        assert req.method == "POST"
        assert str(req.url).endswith("/blacklist/session")
        body = json.loads(req.content)
        assert body == {"session_token": "xtk_abc123", "reason": "chargeback fraud"}
        assert status == "processing"

    def test_add_by_session_not_found(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_error(404, "NOT_FOUND", "session not found")
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        with pytest.raises(xident.NotFoundError, match="session not found"):
            client.blacklist.add_by_session(session_token="xtk_missing", reason="fraud")

    def test_add_by_session_conflict_when_in_progress(
        self, mock_transport: MockTransport
    ) -> None:
        # 409 (session not terminal yet) maps onto ValidationError, the
        # catch-all for non-401/404/429/5xx API errors.
        mock_transport.queue_error(
            409, "CONFLICT", "session is still in progress — blacklist after it completes"
        )
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        with pytest.raises(xident.ValidationError) as exc_info:
            client.blacklist.add_by_session(session_token="xtk_live", reason="fraud")
        assert exc_info.value.status_code == 409
        assert exc_info.value.error_code == "CONFLICT"

    def test_add_by_image(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_response(
            make_success_response({"status": "processing"}, status_code=201)
        )
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        status = client.blacklist.add_by_image(image="aW1hZ2U=", reason="fake document")

        req = mock_transport.last_request
        assert req is not None
        assert req.method == "POST"
        assert str(req.url).endswith("/blacklist/image")
        body = json.loads(req.content)
        assert body == {"image": "aW1hZ2U=", "reason": "fake document"}
        assert status == "processing"

    def test_add_by_image_validation_error(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_error(400, "VALIDATION_FAILED", "reason is required")
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        with pytest.raises(xident.ValidationError) as exc_info:
            client.blacklist.add_by_image(image="aW1hZ2U=", reason="")
        assert exc_info.value.error_code == "VALIDATION_FAILED"

    def test_remove(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_success({"message": "blacklist entry removed"})
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        result = client.blacklist.remove(42)

        req = mock_transport.last_request
        assert req is not None
        assert req.method == "DELETE"
        assert str(req.url).endswith("/blacklist/42")
        assert result is None

    @pytest.mark.parametrize("bad_id", [0, -1, -42])
    def test_remove_invalid_id_raises(
        self, mock_transport: MockTransport, bad_id: int
    ) -> None:
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        with pytest.raises(ValueError, match="Entry ID must be a positive integer"):
            client.blacklist.remove(bad_id)
        assert mock_transport.request_count == 0

    def test_remove_not_found(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_error(404, "NOT_FOUND", "blacklist entry not found")
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        with pytest.raises(xident.NotFoundError, match="blacklist entry not found"):
            client.blacklist.remove(999)

    def test_list_auth_error(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_error(401, "UNAUTHORIZED", "not authenticated")
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        with pytest.raises(xident.AuthenticationError):
            client.blacklist.list()

    def test_resource_is_cached(self, mock_transport: MockTransport) -> None:
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        assert client.blacklist is client.blacklist


class TestAsyncBlacklist:
    @pytest.mark.asyncio
    async def test_list_returns_page(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_response(
            make_list_response(
                [
                    {
                        "id": 3,
                        "reason": "async fraud",
                        "source": "image",
                        "created_at": "2026-08-01T09:00:00Z",
                    }
                ],
                page=1,
                per_page=20,
                total=1,
                total_pages=1,
            )
        )
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)

        result = await client.blacklist.list(page=1, per_page=20)

        req = transport.last_request
        assert req is not None
        assert req.method == "GET"
        assert req.url.params["page"] == "1"
        assert len(result) == 1
        assert result.entries[0].id == 3
        assert result.entries[0].source == "image"
        assert not result.has_more

    @pytest.mark.asyncio
    async def test_add_by_session(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_success({"status": "processing"})
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)

        status = await client.blacklist.add_by_session(
            session_token="xtk_async", reason="fraud"
        )

        req = transport.last_request
        assert req is not None
        assert str(req.url).endswith("/blacklist/session")
        assert json.loads(req.content) == {"session_token": "xtk_async", "reason": "fraud"}
        assert status == "processing"

    @pytest.mark.asyncio
    async def test_add_by_image(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_success({"status": "processing"})
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)

        status = await client.blacklist.add_by_image(image="aW1hZ2U=", reason="fraud")

        req = transport.last_request
        assert req is not None
        assert str(req.url).endswith("/blacklist/image")
        assert status == "processing"

    @pytest.mark.asyncio
    async def test_remove(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_success({"message": "blacklist entry removed"})
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)

        result = await client.blacklist.remove(7)

        req = transport.last_request
        assert req is not None
        assert req.method == "DELETE"
        assert str(req.url).endswith("/blacklist/7")
        assert result is None

    @pytest.mark.asyncio
    async def test_remove_invalid_id_raises(self) -> None:
        transport = AsyncMockTransport()
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)

        with pytest.raises(ValueError, match="Entry ID must be a positive integer"):
            await client.blacklist.remove(0)
        assert transport.request_count == 0

    @pytest.mark.asyncio
    async def test_error_mapping(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_error(404, "NOT_FOUND", "blacklist entry not found")
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)

        with pytest.raises(xident.NotFoundError):
            await client.blacklist.remove(999)
