"""Tests for the Face2FA resource (sync and async)."""

import json

import pytest

import xident

from .conftest import AsyncMockTransport, MockTransport, make_success_response


class TestFace2FA:
    def test_register_returns_challenge(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_response(
            make_success_response(
                {"challenge_id": "f2fa_abc123", "status": "processing"}, status_code=201
            )
        )
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        challenge = client.face_2fa.register(user_id="user_42", image="aW1hZ2U=")

        assert challenge.challenge_id == "f2fa_abc123"
        assert challenge.status == "processing"

    def test_register_sends_correct_request(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_success({"challenge_id": "f2fa_x", "status": "processing"})
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        client.face_2fa.register(user_id="user_42", image="aW1hZ2U=")

        req = mock_transport.last_request
        assert req is not None
        assert req.method == "POST"
        assert str(req.url).endswith("/2fa/register")
        body = json.loads(req.content)
        assert body == {"user_id": "user_42", "image": "aW1hZ2U="}

    def test_verify_sends_correct_request(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_success({"challenge_id": "f2fa_v", "status": "processing"})
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        challenge = client.face_2fa.verify(user_id="user_42", image="c2VsZmll")

        req = mock_transport.last_request
        assert req is not None
        assert req.method == "POST"
        assert str(req.url).endswith("/2fa/verify")
        body = json.loads(req.content)
        assert body == {"user_id": "user_42", "image": "c2VsZmll"}
        assert challenge.challenge_id == "f2fa_v"

    def test_get_status_completed_pass(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_success(
            {
                "challenge_id": "f2fa_abc123",
                "kind": "verify",
                "status": "completed",
                "passed": True,
                "expires_at": "2026-08-01T00:05:00Z",
                "completed_at": "2026-08-01T00:00:30Z",
            }
        )
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        status = client.face_2fa.get_status("f2fa_abc123")

        req = mock_transport.last_request
        assert req is not None
        assert req.method == "GET"
        assert str(req.url).endswith("/2fa/status/f2fa_abc123")
        assert status.challenge_id == "f2fa_abc123"
        assert status.kind == "verify"
        assert status.status == "completed"
        assert status.passed is True
        assert status.is_passed()
        assert not status.is_processing()
        assert status.failure_reason is None
        assert status.expires_at == "2026-08-01T00:05:00Z"
        assert status.completed_at == "2026-08-01T00:00:30Z"

    def test_get_status_still_processing(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_success(
            {
                "challenge_id": "f2fa_p",
                "kind": "enroll",
                "status": "processing",
                "passed": None,
                "expires_at": "2026-08-01T00:05:00Z",
            }
        )
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        status = client.face_2fa.get_status("f2fa_p")

        assert status.is_processing()
        assert status.passed is None
        assert not status.is_passed()
        assert status.completed_at is None

    def test_get_status_failed_with_reason(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_success(
            {
                "challenge_id": "f2fa_f",
                "kind": "verify",
                "status": "failed",
                "passed": False,
                "failure_reason": "face_mismatch",
                "expires_at": "2026-08-01T00:05:00Z",
                "completed_at": "2026-08-01T00:00:10Z",
            }
        )
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        status = client.face_2fa.get_status("f2fa_f")

        assert status.passed is False
        assert not status.is_passed()
        assert status.failure_reason == "face_mismatch"

    def test_get_status_empty_id_raises(self, mock_transport: MockTransport) -> None:
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        with pytest.raises(ValueError, match="Challenge ID cannot be empty"):
            client.face_2fa.get_status("")

    def test_get_status_url_encodes_id(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_success(
            {"challenge_id": "x", "kind": "verify", "status": "processing", "passed": None}
        )
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        client.face_2fa.get_status("id/with/slashes")

        req = mock_transport.last_request
        assert req is not None
        assert "id%2Fwith%2Fslashes" in str(req.url)

    def test_get_status_not_found(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_error(404, "NOT_FOUND", "challenge not found")
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        with pytest.raises(xident.NotFoundError, match="challenge not found"):
            client.face_2fa.get_status("f2fa_missing")

    def test_register_auth_error(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_error(401, "UNAUTHORIZED", "not authenticated")
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        with pytest.raises(xident.AuthenticationError):
            client.face_2fa.register(user_id="user_42", image="aW1hZ2U=")

    def test_register_validation_error(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_error(400, "VALIDATION_FAILED", "image is required")
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        with pytest.raises(xident.ValidationError) as exc_info:
            client.face_2fa.register(user_id="user_42", image="")
        assert exc_info.value.error_code == "VALIDATION_FAILED"

    def test_get_user_enrolled(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_success(
            {"enrolled": True, "enrolled_at": "2026-07-01T12:00:00Z"}
        )
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        enrollment = client.face_2fa.get_user("user_42")

        req = mock_transport.last_request
        assert req is not None
        assert req.method == "GET"
        assert str(req.url).endswith("/2fa/users/user_42")
        assert enrollment.enrolled is True
        assert enrollment.enrolled_at == "2026-07-01T12:00:00Z"

    def test_get_user_not_enrolled(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_success({"enrolled": False})
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        enrollment = client.face_2fa.get_user("user_none")

        assert enrollment.enrolled is False
        assert enrollment.enrolled_at is None

    def test_get_user_empty_id_raises(self, mock_transport: MockTransport) -> None:
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        with pytest.raises(ValueError, match="User ID cannot be empty"):
            client.face_2fa.get_user("")

    def test_get_user_url_encodes_id(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_success({"enrolled": False})
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        client.face_2fa.get_user("user/42?x=1")

        req = mock_transport.last_request
        assert req is not None
        assert "user%2F42%3Fx%3D1" in str(req.url)

    def test_delete_user(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_success({"deleted": True})
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        deleted = client.face_2fa.delete_user("user_42")

        req = mock_transport.last_request
        assert req is not None
        assert req.method == "DELETE"
        assert str(req.url).endswith("/2fa/users/user_42")
        assert deleted is True

    def test_delete_user_empty_id_raises(self, mock_transport: MockTransport) -> None:
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        with pytest.raises(ValueError, match="User ID cannot be empty"):
            client.face_2fa.delete_user("")

    def test_resource_is_cached(self, mock_transport: MockTransport) -> None:
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        assert client.face_2fa is client.face_2fa


class TestAsyncFace2FA:
    @pytest.mark.asyncio
    async def test_register_returns_challenge(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_success({"challenge_id": "f2fa_async", "status": "processing"})
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)

        challenge = await client.face_2fa.register(user_id="user_42", image="aW1hZ2U=")

        req = transport.last_request
        assert req is not None
        assert req.method == "POST"
        assert str(req.url).endswith("/2fa/register")
        assert json.loads(req.content) == {"user_id": "user_42", "image": "aW1hZ2U="}
        assert challenge.challenge_id == "f2fa_async"
        assert challenge.status == "processing"

    @pytest.mark.asyncio
    async def test_verify_returns_challenge(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_success({"challenge_id": "f2fa_av", "status": "processing"})
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)

        challenge = await client.face_2fa.verify(user_id="user_42", image="c2VsZmll")

        req = transport.last_request
        assert req is not None
        assert str(req.url).endswith("/2fa/verify")
        assert challenge.challenge_id == "f2fa_av"

    @pytest.mark.asyncio
    async def test_get_status_returns_verdict(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_success(
            {
                "challenge_id": "f2fa_async",
                "kind": "verify",
                "status": "completed",
                "passed": True,
                "expires_at": "2026-08-01T00:05:00Z",
                "completed_at": "2026-08-01T00:00:30Z",
            }
        )
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)

        status = await client.face_2fa.get_status("f2fa_async")

        assert status.is_passed()
        assert status.kind == "verify"

    @pytest.mark.asyncio
    async def test_get_status_empty_id_raises(self) -> None:
        transport = AsyncMockTransport()
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)

        with pytest.raises(ValueError, match="Challenge ID cannot be empty"):
            await client.face_2fa.get_status("")

    @pytest.mark.asyncio
    async def test_get_user(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_success({"enrolled": True, "enrolled_at": "2026-07-01T12:00:00Z"})
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)

        enrollment = await client.face_2fa.get_user("user_42")

        assert enrollment.enrolled is True

    @pytest.mark.asyncio
    async def test_get_user_empty_id_raises(self) -> None:
        # Guard client-side: an empty id would otherwise GET /2fa/users/ --
        # a different route -- and burn a round trip to learn nothing.
        transport = AsyncMockTransport()
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)

        with pytest.raises(ValueError, match="User ID cannot be empty"):
            await client.face_2fa.get_user("")

        assert transport.request_count == 0

    @pytest.mark.asyncio
    async def test_delete_user(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_success({"deleted": True})
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)

        deleted = await client.face_2fa.delete_user("user_42")

        req = transport.last_request
        assert req is not None
        assert req.method == "DELETE"
        assert deleted is True

    @pytest.mark.asyncio
    async def test_delete_user_empty_id_raises(self) -> None:
        transport = AsyncMockTransport()
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)

        with pytest.raises(ValueError, match="User ID cannot be empty"):
            await client.face_2fa.delete_user("")

    @pytest.mark.asyncio
    async def test_error_mapping(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_error(404, "NOT_FOUND", "challenge not found")
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)

        with pytest.raises(xident.NotFoundError):
            await client.face_2fa.get_status("f2fa_missing")
