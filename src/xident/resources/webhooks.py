"""Webhooks resource -- verify webhook signatures and parse events.

Xident sends webhook events to your configured callback URL when
verification sessions are completed, failed, or expire.

Signature format (Stripe-style):
    X-Xident-Signature: t=1710345600,v1=5257a869abcdef...

HMAC construction matches the Go backend:
    HMAC-SHA256(secret, "{timestamp}.{payload}")

Uses hmac.compare_digest() for constant-time comparison to prevent
timing attacks.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any


class Webhooks:
    """Webhook signature verification and event parsing.

    This class is stateless -- it does not require an HTTP client.

    Usage::

        webhooks = client.webhooks
        event = webhooks.construct_event(payload, signature, secret)
        # or verify only:
        webhooks.verify_signature(payload, signature, secret)
    """

    def construct_event(
        self,
        payload: str | bytes,
        signature: str,
        secret: str,
        *,
        tolerance: int = 300,
    ) -> dict[str, Any]:
        """Verify an incoming webhook signature and parse the event.

        Convenience method that combines verify_signature() + parse_event().

        Args:
            payload: Raw JSON body from the request.
            signature: Value of X-Xident-Signature header.
            secret: Webhook signing secret from dashboard (whsec_xxx).
            tolerance: Maximum age in seconds (default 300 = 5 minutes).

        Returns:
            Parsed event dict with keys: type, data, id, created.

        Raises:
            ValueError: If signature is invalid, malformed, or too old.
        """
        payload_str = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        self.verify_signature(payload_str, signature, secret, tolerance=tolerance)
        return self.parse_event(payload_str)

    def verify_signature(
        self,
        payload: str | bytes,
        signature: str,
        secret: str,
        *,
        tolerance: int = 300,
    ) -> bool:
        """Verify a webhook signature using HMAC-SHA256.

        Args:
            payload: Raw JSON body from the request.
            signature: Value of X-Xident-Signature header.
            secret: Webhook signing secret.
            tolerance: Maximum age in seconds (0 = no replay protection).

        Returns:
            True if signature is valid.

        Raises:
            ValueError: If signature is invalid, malformed, or too old.
        """
        payload_str = payload.decode("utf-8") if isinstance(payload, bytes) else payload

        if not signature:
            raise ValueError("Missing webhook signature")
        if not secret:
            raise ValueError("Missing webhook secret")

        # Parse "t=TIMESTAMP,v1=HMAC_HEX"
        parts: dict[str, str] = {}
        for pair in signature.split(","):
            kv = pair.split("=", 1)
            if len(kv) == 2:
                parts[kv[0]] = kv[1]

        if "t" not in parts or "v1" not in parts:
            raise ValueError("Invalid signature format -- expected t=TIMESTAMP,v1=HMAC")

        timestamp = int(parts["t"])
        expected_sig = parts["v1"]

        # Replay protection
        if tolerance > 0:
            age = int(time.time()) - timestamp
            if age > tolerance:
                raise ValueError(
                    f"Webhook timestamp too old ({age} seconds, tolerance {tolerance})"
                )

        # Compute expected HMAC -- matches Go backend: timestamp + "." + payload
        signed_payload = f"{timestamp}.{payload_str}"
        computed = hmac.new(
            secret.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # Constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(computed, expected_sig):
            raise ValueError("Webhook signature verification failed")

        return True

    @staticmethod
    def parse_event(payload: str | bytes) -> dict[str, Any]:
        """Parse a webhook event body.

        Args:
            payload: Raw JSON body.

        Returns:
            Parsed event dict with keys: type, data, id, created.

        Raises:
            ValueError: If payload is not valid JSON.
        """
        payload_str = payload.decode("utf-8") if isinstance(payload, bytes) else payload

        try:
            decoded = json.loads(payload_str)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError("Invalid webhook payload -- not valid JSON") from exc

        if not isinstance(decoded, dict):
            raise ValueError("Invalid webhook payload -- not a JSON object")

        return {
            "type": str(decoded.get("type", decoded.get("event_type", ""))),
            "data": dict(decoded.get("data", decoded)),
            "id": decoded.get("id", decoded.get("event_id")),
            "created": int(decoded["created"]) if "created" in decoded else None,
        }
