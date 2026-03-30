"""Tests for the Webhooks resource."""

import hashlib
import hmac
import json
import time

import pytest

import xident
from xident.resources.webhooks import Webhooks


class TestWebhooks:
    def _make_signature(
        self, payload: str, secret: str, timestamp: int | None = None
    ) -> str:
        """Helper to create a valid webhook signature."""
        ts = timestamp or int(time.time())
        signed = f"{ts}.{payload}"
        sig = hmac.new(
            secret.encode("utf-8"),
            signed.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"t={ts},v1={sig}"

    def test_verify_valid_signature(self) -> None:
        webhooks = Webhooks()
        payload = '{"type":"session.completed","data":{"id":"sess_1"}}'
        secret = "whsec_test_secret"
        signature = self._make_signature(payload, secret)

        result = webhooks.verify_signature(payload, signature, secret)
        assert result is True

    def test_verify_invalid_signature(self) -> None:
        webhooks = Webhooks()
        payload = '{"type":"session.completed"}'
        secret = "whsec_test_secret"
        # Use a recent timestamp so replay protection doesn't fire first
        ts = int(time.time())
        signature = f"t={ts},v1=invalid_hex"

        with pytest.raises(ValueError, match="signature verification failed"):
            webhooks.verify_signature(payload, signature, secret)

    def test_verify_missing_signature(self) -> None:
        webhooks = Webhooks()
        with pytest.raises(ValueError, match="Missing webhook signature"):
            webhooks.verify_signature("payload", "", "secret")

    def test_verify_missing_secret(self) -> None:
        webhooks = Webhooks()
        with pytest.raises(ValueError, match="Missing webhook secret"):
            webhooks.verify_signature("payload", "t=1,v1=abc", "")

    def test_verify_malformed_signature(self) -> None:
        webhooks = Webhooks()
        with pytest.raises(ValueError, match="Invalid signature format"):
            webhooks.verify_signature("payload", "garbage", "secret")

    def test_verify_missing_v1(self) -> None:
        webhooks = Webhooks()
        with pytest.raises(ValueError, match="Invalid signature format"):
            webhooks.verify_signature("payload", "t=12345", "secret")

    def test_verify_missing_timestamp(self) -> None:
        webhooks = Webhooks()
        with pytest.raises(ValueError, match="Invalid signature format"):
            webhooks.verify_signature("payload", "v1=abc123", "secret")

    def test_verify_expired_signature(self) -> None:
        webhooks = Webhooks()
        payload = '{"type":"test"}'
        secret = "whsec_test"
        old_timestamp = int(time.time()) - 600  # 10 minutes ago
        signature = self._make_signature(payload, secret, timestamp=old_timestamp)

        with pytest.raises(ValueError, match="too old"):
            webhooks.verify_signature(payload, signature, secret, tolerance=300)

    def test_verify_tolerance_zero_skips_replay_check(self) -> None:
        webhooks = Webhooks()
        payload = '{"type":"test"}'
        secret = "whsec_test"
        old_timestamp = int(time.time()) - 3600  # 1 hour ago
        signature = self._make_signature(payload, secret, timestamp=old_timestamp)

        result = webhooks.verify_signature(payload, signature, secret, tolerance=0)
        assert result is True

    def test_verify_bytes_payload(self) -> None:
        webhooks = Webhooks()
        payload = '{"type":"test"}'
        secret = "whsec_test"
        signature = self._make_signature(payload, secret)

        result = webhooks.verify_signature(payload.encode("utf-8"), signature, secret)
        assert result is True

    def test_construct_event(self) -> None:
        webhooks = Webhooks()
        event_data = {
            "type": "session.completed",
            "data": {"id": "sess_123", "status": "completed"},
            "id": "evt_abc",
            "created": 1710345600,
        }
        payload = json.dumps(event_data)
        secret = "whsec_test"
        signature = self._make_signature(payload, secret)

        event = webhooks.construct_event(payload, signature, secret)

        assert event["type"] == "session.completed"
        assert event["data"]["id"] == "sess_123"
        assert event["id"] == "evt_abc"
        assert event["created"] == 1710345600

    def test_construct_event_with_bytes(self) -> None:
        webhooks = Webhooks()
        event_data = {"type": "session.failed", "data": {"id": "sess_456"}}
        payload = json.dumps(event_data)
        secret = "whsec_test"
        signature = self._make_signature(payload, secret)

        event = webhooks.construct_event(payload.encode("utf-8"), signature, secret)
        assert event["type"] == "session.failed"

    def test_construct_event_invalid_signature(self) -> None:
        webhooks = Webhooks()
        payload = '{"type":"test"}'
        with pytest.raises(ValueError):
            webhooks.construct_event(payload, "t=1,v1=bad", "secret")

    def test_parse_event_standard(self) -> None:
        event_data = {
            "type": "session.completed",
            "data": {"id": "sess_1", "status": "completed"},
            "id": "evt_1",
            "created": 1710345600,
        }
        result = Webhooks.parse_event(json.dumps(event_data))
        assert result["type"] == "session.completed"
        assert result["data"]["id"] == "sess_1"
        assert result["id"] == "evt_1"
        assert result["created"] == 1710345600

    def test_parse_event_alternative_keys(self) -> None:
        event_data = {
            "event_type": "verification.done",
            "status": "ok",
            "event_id": "evt_alt",
        }
        result = Webhooks.parse_event(json.dumps(event_data))
        assert result["type"] == "verification.done"
        assert result["id"] == "evt_alt"
        assert result["created"] is None

    def test_parse_event_invalid_json(self) -> None:
        with pytest.raises(ValueError, match="not valid JSON"):
            Webhooks.parse_event("not json")

    def test_parse_event_non_object_json(self) -> None:
        with pytest.raises(ValueError, match="not a JSON object"):
            Webhooks.parse_event('"just a string"')

    def test_parse_event_bytes(self) -> None:
        result = Webhooks.parse_event(b'{"type":"test","data":{}}')
        assert result["type"] == "test"

    def test_client_webhooks_access(self) -> None:
        """Verify webhooks resource is accessible from the client."""
        from .conftest import MockTransport

        transport = MockTransport()
        client = xident.Xident(api_key="sk_test_123", transport=transport)
        assert isinstance(client.webhooks, Webhooks)
